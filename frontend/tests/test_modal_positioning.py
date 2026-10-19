import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from frontend.models import Category, Person, Product


def css_block(css, selector):
    match = re.search(
        re.escape(selector) + r'\s*\{(?P<body>[^}]*)\}',
        css,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f'CSS block not found: {selector}')
    return match.group('body')


class ModalContainingBlockCssTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.motion = (Path(settings.BASE_DIR) / 'static' / 'css' / 'motion.css').read_text()
        cls.components = (Path(settings.BASE_DIR) / 'static' / 'css' / 'components.css').read_text()

    def test_page_animation_ends_without_a_transform(self):
        main = css_block(self.motion, '.main')
        self.assertIn('animation: pageFadeIn 150ms var(--ease-out) both;', main)

        keyframes = re.search(
            r'@keyframes pageFadeIn\s*\{(?P<body>.*?)\n\}',
            self.motion,
            re.DOTALL,
        ).group('body')
        self.assertIn('transform: translateY(4px);', keyframes)
        self.assertIn('transform: none;', keyframes)
        self.assertIsNone(
            re.search(r'to\s*\{[^}]*translate', keyframes, re.DOTALL),
        )

    def test_reduced_motion_removes_the_animation_and_transform(self):
        self.assertIn(
            '.main { animation: none; opacity: 1; transform: none; }',
            self.motion,
        )
        data_motion = self.motion.split('[data-motion="reduced"] .main,', 1)[1]
        data_motion = data_motion.split('animation: none !important;', 1)[1]
        data_motion = data_motion.split('}', 1)[0]
        self.assertIn('transform: none !important;', data_motion)

    def test_shared_overlays_are_viewport_fixed_and_centered(self):
        for selector in ('.modal-overlay', '.confirm-overlay'):
            block = css_block(self.components, selector)
            self.assertIn('position: fixed;', block)
            self.assertIn('inset: 0;', block)
            self.assertIn('align-items: center;', block)
            self.assertIn('justify-content: center;', block)
            self.assertIn('padding: var(--space-4);', block)

    def test_modal_content_stays_inside_the_viewport(self):
        content = css_block(self.components, '.modal-content')
        self.assertIn('max-height: 90vh;', content)
        self.assertIn('max-width: 500px;', content)
        self.assertIn('overflow-y: auto;', content)

    def test_modal_lifecycle_locks_and_restores_body_scroll(self):
        main_js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js').read_text()
        open_modal = main_js.split('window.openModal = function(modalId)', 1)[1]
        open_modal = open_modal.split('window.closeModal', 1)[0]
        close_modal = main_js.split('window.closeModal = function(modalId)', 1)[1]
        close_modal = close_modal.split('// Close on overlay click', 1)[0]

        self.assertIn("document.body.style.overflow = 'hidden';", open_modal)
        self.assertIn("document.body.style.overflow = '';", close_modal)


class ProductModalMarkupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='modal-manager',
            email='modal@example.com',
            password='test-pass-123',
        )
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Modal category')
        self.product = Product.objects.create(
            name='Modal product',
            code='MODAL-1',
            category=self.category,
            price=Decimal('10.00'),
            stock_quantity=5,
        )

    def test_new_product_overlay_markup(self):
        response = self.client.get(reverse('frontend:products'))
        html = response.content.decode()

        self.assertIn('<div class="modal-overlay" id="product-modal">', html)
        self.assertIn(
            'class="modal-content" role="dialog" aria-modal="true" '
            'aria-labelledby="product-modal-title"',
            html,
        )

    def test_edit_product_uses_the_same_overlay_markup(self):
        response = self.client.get(
            reverse('frontend:product_edit', args=[self.product.pk])
        )
        html = response.content.decode()

        self.assertIn('<div class="modal-overlay" id="product-edit-modal">', html)
        self.assertIn(
            'class="modal-content" role="dialog" aria-modal="true" '
            'aria-labelledby="product-edit-title"',
            html,
        )

    def test_people_edit_modal_uses_the_shared_overlay_class(self):
        person = Person.objects.create(name='Modal person', person_type='STUDENT')
        response = self.client.get(
            reverse('frontend:person_edit', args=[person.pk])
        )
        html = response.content.decode()

        self.assertIn('<div class="modal-overlay" id="person-edit-modal">', html)

    def test_shared_confirmation_overlays_render_outside_main(self):
        html = self.client.get(reverse('frontend:dashboard')).content.decode()

        self.assertIn('class="confirm-overlay" id="logoutDialog"', html)
        self.assertIn('class="confirm-overlay" id="destructiveConfirmDialog"', html)
        after_main = html.split('</main>', 1)[1]
        self.assertIn('id="logoutDialog"', after_main)
        self.assertIn('id="destructiveConfirmDialog"', after_main)
