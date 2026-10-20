"""Regression tests for the P1 frontend accessibility and delivery fixes."""
import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from frontend.models import Category, Person, Product, Sale, SaleItem


def _read_template(name):
    return (
        Path(settings.BASE_DIR) / 'frontend' / 'templates' / 'frontend' / name
    ).read_text(encoding='utf-8')


def _block_tokens(css, selector):
    match = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
    if not match:
        raise AssertionError(f'CSS block not found: {selector}')
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', match.group(1)))


def _hex_luminance(value):
    value = value.strip().lstrip('#')
    if len(value) != 6:
        raise AssertionError(f'Expected a six-digit hex color, got {value!r}')
    channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.03928
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground, background):
    first, second = sorted(
        (_hex_luminance(foreground), _hex_luminance(background)),
        reverse=True,
    )
    return (first + 0.05) / (second + 0.05)


class ContrastTokenTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        css = (
            Path(settings.BASE_DIR) / 'static' / 'css' / 'variables.css'
        ).read_text(encoding='utf-8')
        light = _block_tokens(css, ':root')
        dark = _block_tokens(css, '[data-theme="dark"]')
        high_light = _block_tokens(css, ':root[data-contrast="high"]')
        high_dark = _block_tokens(
            css, ':root[data-theme="dark"][data-contrast="high"]',
        )
        cls.themes = {
            'light': light,
            'dark': {**light, **dark},
            'high contrast light': {**light, **high_light},
            'high contrast dark': {**light, **dark, **high_dark},
        }

    def test_text_tokens_meet_wcag_aa_on_backgrounds(self):
        for theme, tokens in self.themes.items():
            for text_token in (
                '--color-text', '--color-text-secondary', '--color-text-muted',
            ):
                for background_token in ('--color-bg', '--color-surface'):
                    with self.subTest(theme=theme, token=text_token,
                                      background=background_token):
                        ratio = _contrast_ratio(
                            tokens[text_token], tokens[background_token],
                        )
                        self.assertGreaterEqual(
                            ratio, 4.5,
                            f'{theme}: {text_token} on {background_token} '
                            f'is {ratio:.2f}:1',
                        )

    def test_semantic_status_tokens_meet_wcag_aa(self):
        for theme, tokens in self.themes.items():
            for status in ('success', 'warning', 'danger', 'info'):
                foreground = tokens[f'--color-{status}']
                background = tokens[f'--color-{status}-bg']
                with self.subTest(theme=theme, status=status):
                    ratio = _contrast_ratio(foreground, background)
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f'{theme}: {status} text is {ratio:.2f}:1',
                    )


class ChartAccessibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('charts-a11y', password='test-pass-123')
        self.client.force_login(self.user)
        category = Category.objects.create(name='Bebidas')
        product = Product.objects.create(
            name='Suco', code='SUCO-1', category=category,
            price=Decimal('10.00'), stock_quantity=20,
        )
        sale = Sale.objects.create(
            responsible=self.user, status='COMPLETED', payment_method='CASH',
            subtotal=Decimal('30.00'), total=Decimal('30.00'),
            completed_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale, product=product, quantity=3, unit_price=product.price,
        )

    def test_dashboard_chart_has_a_text_equivalent(self):
        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('id="salesChart"', html)
        self.assertIn('aria-describedby="sales-chart-summary"', html)
        summary = re.search(
            r'<div class="sr-only" id="sales-chart-summary">(.*?)</div>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(summary)
        self.assertIn('<td>3</td>', summary.group(1))

    def test_reports_charts_have_text_equivalents(self):
        html = self.client.get(reverse('frontend:reports')).content.decode()
        for canvas_id, summary_id in (
            ('revenueChart', 'revenue-chart-summary'),
            ('volumeChart', 'volume-chart-summary'),
            ('paymentMixChart', 'payment-mix-chart-summary'),
        ):
            with self.subTest(chart=canvas_id):
                self.assertIn(f'id="{canvas_id}"', html)
                self.assertIn(f'aria-describedby="{summary_id}"', html)
                self.assertIn(f'id="{summary_id}"', html)
        revenue_summary = re.search(
            r'<div class="sr-only" id="revenue-chart-summary">(.*?)</div>',
            html, re.DOTALL,
        ).group(1)
        payment_summary = re.search(
            r'<div class="sr-only" id="payment-mix-chart-summary">(.*?)</div>',
            html, re.DOTALL,
        ).group(1)
        self.assertIn('R$ 30.00', revenue_summary)
        self.assertIn('100.0%', payment_summary)

    def test_chart_scripts_use_theme_palette_and_wait_for_dom(self):
        dashboard = _read_template('dashboard.html')
        reports = _read_template('reports.html')
        for template in (dashboard, reports):
            with self.subTest(template=template[:20]):
                self.assertIn('quadrum.chartPalette()', template)
                self.assertIn("quadrum:themechange", template)
                self.assertIn("DOMContentLoaded", template)


class AssetDeliveryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = _read_template('base.html')
        cls.auth_base = _read_template('auth_base.html')

    def test_lucide_is_pinned_and_deferred(self):
        self.assertIn('lucide@0.496.0', self.base)
        self.assertIn('lucide@0.496.0', self.auth_base)
        self.assertNotIn('lucide@latest', self.base)
        self.assertNotIn('lucide@latest', self.auth_base)
        self.assertRegex(
            self.base,
            r'<script defer src="https://unpkg\.com/lucide@0\.496\.0/',
        )

    def test_chartjs_is_limited_to_chart_pages(self):
        self.assertNotIn('chart.js', self.base)
        self.assertIn('{% block extra_head %}', self.base)
        for name in ('dashboard.html', 'reports.html'):
            with self.subTest(template=name):
                template = _read_template(name)
                head = template.split('{% block extra_head %}', 1)[1]
                head = head.split('{% endblock %}', 1)[0]
                self.assertIn('chart.js@4.4.1', head)
                self.assertIn('defer', head)


class ClientSideEscapingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_js = (
            Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js'
        ).read_text(encoding='utf-8')
        cls.pos = _read_template('point_of_sale.html')

    def test_toast_content_uses_text_nodes(self):
        self.assertIn('notificationTitle.textContent', self.main_js)
        self.assertIn('notificationMessage.textContent', self.main_js)
        self.assertNotIn('notification.innerHTML', self.main_js)

    def test_cart_rows_use_text_nodes_instead_of_html_interpolation(self):
        self.assertIn('nameCell.textContent = item.name', self.pos)
        self.assertNotIn('tr.innerHTML', self.pos)
        self.assertNotIn('${item.name}', self.pos)

class PosUiAccessibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('pos-a11y', password='test-pass-123')
        self.user.profile.language = 'pt-br'
        self.user.profile.save(update_fields=['language'])
        self.client.force_login(self.user)
        category = Category.objects.create(name='Bebidas')
        self.product = Product.objects.create(
            name='Suco Natural', code='SUCO-2', category=category,
            price=Decimal('10.50'), stock_quantity=20,
        )
        self.person = Person.objects.create(name='Maria Cliente', person_type='STUDENT')

    def test_pos_renders_customer_selector_and_raw_price(self):
        html = self.client.get(reverse('frontend:point_of_sale')).content.decode()
        self.assertIn('id="selected-customer"', html)
        self.assertIn('Maria Cliente', html)
        self.assertIn('data-price="10.50"', html)
        self.assertIn('R$ 10,50', html)
        self.assertIn('data-category-id=""', html)
        self.assertIn('<button type="button" class="product-card', html)
        self.assertNotIn('onclick="filterByCategory', html)

    def test_main_javascript_has_no_duplicate_pos_filter(self):
        main_js = (
            Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js'
        ).read_text(encoding='utf-8')
        self.assertNotIn('function initFilters', main_js)
        self.assertNotIn('window.filterByCategory', main_js)
