from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from frontend.models import AccountReceivable, Category, Payment, Person, Product, Sale
from frontend.search import DOC_TOPICS


class InventoryPageRenderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inv-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Bebidas')
        self.normal = Product.objects.create(
            name='Normal Item', code='N1', category=self.category,
            price=Decimal('2.00'), stock_quantity=10, minimum_stock=5,
        )
        self.low = Product.objects.create(
            name='Low Item', code='L1', category=self.category,
            price=Decimal('3.00'), stock_quantity=3, minimum_stock=5,
        )
        self.out = Product.objects.create(
            name='Out Item', code='O1', category=self.category,
            price=Decimal('4.00'), stock_quantity=0, minimum_stock=5,
        )
        self.inactive = Product.objects.create(
            name='Inactive Item', code='I1', category=self.category,
            price=Decimal('5.00'), stock_quantity=8, minimum_stock=5, active=False,
        )

    def get_html(self):
        return self.client.get(reverse('frontend:inventory')).content.decode()

    def test_single_status_column_uses_correct_states(self):
        html = self.get_html()
        self.assertEqual(html.count('<th>Status</th>'), 1)
        self.assertEqual(html.count('<th>Action</th>'), 1)
        self.assertIn('data-status="NORMAL"', html)
        self.assertIn('data-status="LOW"', html)
        self.assertIn('data-status="OUT_OF_STOCK"', html)
        self.assertIn('data-status="INACTIVE"', html)
        self.assertIn('badge-status-normal">Normal', html)
        self.assertIn('badge-status-low">Low', html)
        self.assertIn('badge-status-out-of-stock">Out of Stock', html)
        self.assertIn('badge-status-inactive">Inactive', html)
        self.assertNotIn('>Active<', html)

    def test_status_and_category_filters_match_row_data(self):
        html = self.get_html()
        self.assertIn('<option value="OUT_OF_STOCK">Out of Stock</option>', html)
        self.assertNotIn('value="OUT OF STOCK"', html)
        self.assertIn(f'<option value="{self.category.pk}">Bebidas</option>', html)
        self.assertIn(f'data-category="{self.category.pk}"', html)

    def test_stats_use_active_products_and_rendered_values(self):
        html = self.get_html()
        self.assertIn('<div class="stat-value" id="total-items">3</div>', html)
        self.assertIn('R$ 29.00', html)
        self.assertIn('<div class="stat-value" id="low-stock">1</div>', html)
        self.assertIn('<div class="stat-value" id="out-of-stock">1</div>', html)

    def test_inactive_rows_have_no_adjust_action(self):
        html = self.get_html()
        self.assertIn('aria-label="Adjust inventory for Normal Item"', html)
        self.assertNotIn('aria-label="Adjust inventory for Inactive Item"', html)
        self.assertIn('id="stockProductSelect" class="select"', html)
        self.assertIn('id="stockQtyInput" class="input"', html)
        self.assertIn('class="input stock-adjust-reason"', html)


class FinancePageRenderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fin-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.person = Person.objects.create(
            name='Maria Souza', doc_id='DOC-9', person_type='STUDENT',
        )
        self.sale = Sale.objects.create(
            customer=self.person, responsible=self.user, status='COMPLETED',
            payment_method='ON_ACCOUNT',
            total=Decimal('12.50'), notes='Monthly meal plan',
        )
        self.receivable = AccountReceivable.objects.create(
            person=self.person, sale=self.sale, original_amount=Decimal('12.50'),
            due_date='2030-01-15', status='PENDING',
        )
        Payment.objects.create(
            account_receivable=self.receivable, amount=Decimal('2.50'), method='CASH',
        )

    def get_html(self):
        return self.client.get(reverse('frontend:finance')).content.decode()

    def test_receivable_rows_render_real_values(self):
        html = self.get_html()
        self.assertIn('<td>Maria Souza</td>', html)
        self.assertIn('R$ 12.50', html)
        self.assertIn('01/15/2030', html)
        self.assertIn('Monthly meal plan', html)
        self.assertIn('Pending', html)
        self.assertIn('R$ 2.50', html)
        self.assertIn('Cash', html)
        self.assertNotIn('<td class="numeric">R$ </td>', html)

    def test_action_button_is_named_and_uses_lucide(self):
        html = self.get_html()
        self.assertIn('aria-label="Register payment for Maria Souza"', html)
        self.assertIn('data-lucide="banknote"', html)
        self.assertIn('onclick="registerPayment(', html)

    def test_payment_form_controls_have_theme_classes_and_bounded_textarea(self):
        html = self.get_html()
        self.assertIn('name="account_receivable" class="select"', html)
        self.assertIn('name="amount" class="input"', html)
        self.assertIn('name="method" class="select"', html)
        self.assertIn('class="textarea"', html)
        self.assertIn('rows="3"', html)
        self.assertNotIn('AccountReceivable object', html)

    def test_receivable_string_is_human_readable(self):
        value = str(self.receivable)
        self.assertIn('Maria Souza', value)
        self.assertIn('12.50', value)
        self.assertNotIn('AccountReceivable object', value)

    def test_payment_form_has_neutral_placeholder_option(self):
        html = self.get_html()
        self.assertIn('>Select an account</option>', html)
        self.assertNotIn('>---------</option>', html)


class PeoplePageBalanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ppl-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.debtor = Person.objects.create(name='Ana Lima', doc_id='DOC-1', person_type='STUDENT')
        self.paid_person = Person.objects.create(name='Bruno Reis', doc_id='DOC-2', person_type='TEACHER')
        self.sale = Sale.objects.create(
            customer=self.debtor, responsible=self.user, status='COMPLETED',
            payment_method='ON_ACCOUNT', total=Decimal('12.50'),
        )
        self.account = AccountReceivable.objects.create(
            person=self.debtor, sale=self.sale, original_amount=Decimal('12.50'),
            due_date='2030-01-15', status='PENDING',
        )
        Payment.objects.create(
            account_receivable=self.account, amount=Decimal('2.50'), method='CASH',
        )

    def get_html(self):
        return self.client.get(reverse('frontend:people')).content.decode()

    def test_balance_shows_signed_remaining_amount(self):
        html = self.get_html()
        self.assertIn('R$ -10.00', html)
        self.assertIn('R$ 0.00', html)
        self.assertNotIn('R$ </span>', html)

    def test_paid_accounts_are_excluded_from_balance(self):
        self.account.status = 'PAID'
        self.account.save(update_fields=['status'])
        html = self.get_html()
        self.assertIn('R$ 0.00', html)
        self.assertNotIn('R$ -10.00', html)


class MoneyFormattingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='money-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.person = Person.objects.create(name='Carla Dias', doc_id='DOC-3', person_type='STAFF')
        self.category = Category.objects.create(name='Bebidas')
        self.product = Product.objects.create(
            name='Suco', code='S1', category=self.category, price=Decimal('5'),
            stock_quantity=4, minimum_stock=1,
        )
        self.sale = Sale.objects.create(
            customer=self.person, responsible=self.user, status='COMPLETED',
            payment_method='CASH', total=Decimal('5'),
        )

    def test_dashboard_and_product_money_render_two_decimals(self):
        dashboard = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('R$ 5.00', dashboard)
        self.assertNotIn('R$ 5<', dashboard)
        products = self.client.get(reverse('frontend:products')).content.decode()
        self.assertIn('R$ 5.00', products)
        self.assertNotIn('R$ 5<', products)
        sales = self.client.get(reverse('frontend:sales_list')).content.decode()
        self.assertIn('R$ 5.00', sales)
        self.assertNotIn('R$ 5<', sales)


class ProductBrandingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='brand-ui', password='test-pass-123')

    def test_auth_pages_show_generic_product_descriptor(self):
        for name in ['login', 'register']:
            html = self.client.get(reverse(f'frontend:{name}')).content.decode()
            self.assertIn('Simple Management System', html)
            self.assertNotIn('cafeteria', html.lower())

    def test_operational_pages_have_no_cafeteria_branding(self):
        self.client.force_login(self.user)
        for name in ['dashboard', 'sales_list', 'point_of_sale', 'products',
                     'inventory', 'people', 'finance', 'reports']:
            html = self.client.get(reverse(f'frontend:{name}')).content.decode()
            self.assertNotIn('cafeteria', html.lower(), msg=name)


class BrandMarkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='brand-mark', password='test-pass-123')

    def test_sidebar_uses_lucide_squares_intersect(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('class="sidebar-logo-mark" aria-hidden="true"', html)
        self.assertIn('data-lucide="squares-intersect"', html)
        self.assertEqual(html.count('squares-intersect'), 1)
        self.assertIn('<span class="sidebar-logo-text">quadrum</span>', html)
        self.assertIn('aria-label="quadrum — Dashboard"', html)
        self.assertNotIn('viewBox="0 0 28 28"', html)

    def test_auth_pages_use_lucide_squares_intersect(self):
        for name in ['login', 'register']:
            html = self.client.get(reverse(f'frontend:{name}')).content.decode()
            self.assertIn('class="auth-brand-mark" aria-hidden="true"', html)
            self.assertIn('data-lucide="squares-intersect"', html)
            self.assertEqual(html.count('squares-intersect'), 1, name)
            self.assertIn('<span class="auth-brand-wordmark">quadrum</span>', html)
            self.assertNotIn('viewBox="0 0 28 28"', html)

    def test_auth_pages_load_lucide_and_initialize(self):
        for name in ['login', 'register']:
            html = self.client.get(reverse(f'frontend:{name}')).content.decode()
            self.assertIn('unpkg.com/lucide@0.496.0/dist/umd/lucide.min.js', html)
            self.assertIn('lucide.createIcons()', html)


class FaviconTests(TestCase):
    def get_svg(self):
        return (Path(settings.BASE_DIR) / 'static' / 'favicon.svg').read_text()

    def test_favicon_uses_intersecting_squares_mark(self):
        svg = self.get_svg()
        self.assertIn('viewBox="0 0 32 32"', svg)
        self.assertIn('<svg', svg)
        self.assertIn('</svg>', svg)
        self.assertIn('M8 10a2 2 0 0 1 2-2h5a1 1 0 0 1 1 1v5a2 2 0 0 1-2 2H9a1 1 0 0 1-1-1z', svg)
        self.assertIn('M14 2a2 2 0 0 1 2 2', svg)
        self.assertIn('M10 22a2 2 0 0 1-2-2', svg)

    def test_favicon_is_vector_only_with_dark_tile_and_light_strokes(self):
        svg = self.get_svg()
        self.assertNotIn('<text', svg)
        self.assertIn('fill="#171717"', svg)
        self.assertIn('stroke="#f5f5f5"', svg)

    def test_pages_reference_the_shared_favicon(self):
        anonymous_html = self.client.get(reverse('frontend:login')).content.decode()
        self.assertIn('favicon.svg', anonymous_html)
        self.assertNotIn('data:image/svg+xml,', anonymous_html)

        user = User.objects.create_user(username='favicon-ui', password='test-pass-123')
        self.client.force_login(user)
        dashboard_html = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('favicon.svg', dashboard_html)
        self.assertNotIn('data:image/svg+xml,', dashboard_html)


class DocumentationPortalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='docs-ui', password='test-pass-123')
        self.client.force_login(self.user)

    def topic_url(self, slug):
        return reverse('frontend:documentation_topic', args=[slug])

    def test_index_renders_cards_search_and_groups(self):
        html = self.client.get(reverse('frontend:documentation')).content.decode()
        self.assertIn('role="search"', html)
        self.assertIn('id="docSearchInput"', html)
        self.assertIn('id="docSearchEmpty" hidden', html)
        self.assertIn('id="docIndex"', html)
        self.assertEqual(html.count('class="doc-card"'), len(DOC_TOPICS))
        self.assertIn('End-user guides', html)
        self.assertIn('Developer references', html)
        for topic in DOC_TOPICS:
            self.assertIn(f'href="{self.topic_url(topic["slug"])}"', html, topic['slug'])
            self.assertIn(f'data-doc-keywords="{topic["keywords"]}"', html, topic['slug'])

    def test_index_does_not_embed_topic_bodies(self):
        html = self.client.get(reverse('frontend:documentation')).content.decode()
        for phrase in [
            'append-only audit trail',
            'Idempotency key not authorized',
            'stock_non_negative',
        ]:
            self.assertNotIn(phrase, html, msg=phrase)

    def test_index_keeps_replay_action_and_repo_note(self):
        html = self.client.get(reverse('frontend:documentation')).content.decode()
        self.assertIn(f'action="{reverse("frontend:onboarding_restart")}"', html)
        self.assertIn('Show getting started guide', html)
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertIn('README.md', html)

    def test_every_topic_has_a_distinct_page_with_breadcrumb(self):
        seen_titles = set()
        for topic in DOC_TOPICS:
            resp = self.client.get(self.topic_url(topic['slug']))
            with self.subTest(topic=topic['slug']):
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, topic['title'])
                self.assertContains(resp, topic['description'])
                html = resp.content.decode()
                self.assertIn(f'href="{reverse("frontend:documentation")}"', html)
                self.assertIn('doc-breadcrumb', html)
                self.assertIn('aria-current="page"', html)
                seen_titles.add(topic['title'])
        self.assertEqual(len(seen_titles), len(DOC_TOPICS))

    def test_prev_next_links_follow_registry_order(self):
        first = self.client.get(self.topic_url(DOC_TOPICS[0]['slug'])).content.decode()
        self.assertIn('rel="next"', first)
        self.assertNotIn('rel="prev"', first)
        self.assertIn(
            f'href="{self.topic_url(DOC_TOPICS[1]["slug"])}"', first,
        )

        middle = self.client.get(self.topic_url(DOC_TOPICS[3]['slug'])).content.decode()
        self.assertIn('rel="prev"', middle)
        self.assertIn('rel="next"', middle)
        self.assertIn(f'href="{self.topic_url(DOC_TOPICS[2]["slug"])}"', middle)
        self.assertIn(f'href="{self.topic_url(DOC_TOPICS[4]["slug"])}"', middle)

        last = self.client.get(self.topic_url(DOC_TOPICS[-1]['slug'])).content.decode()
        self.assertIn('rel="prev"', last)
        self.assertNotIn('rel="next"', last)

    def test_unknown_topic_slugs_return_404(self):
        for slug in ['does-not-exist', 'doc-api', 'search-help']:
            resp = self.client.get(f'/documentation/{slug}/')
            self.assertEqual(resp.status_code, 404, msg=slug)

    def test_topic_pages_are_login_required(self):
        self.client.logout()
        resp = self.client.get(self.topic_url('api'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_topic_content_reuses_repository_facts(self):
        api = self.client.get(self.topic_url('api')).content.decode()
        for phrase in ['/api/pos/calculate/', '/api/pos/finalize/', '/api/search/', 'X-CSRFToken']:
            self.assertIn(phrase, api, msg=phrase)
        finance = self.client.get(self.topic_url('finance')).content.decode()
        for phrase in ['On Account', 'remaining balance', 'Cancelled']:
            self.assertIn(phrase, finance, msg=phrase)

    def test_templates_stay_escaped_and_static(self):
        templates = Path(settings.BASE_DIR) / 'frontend' / 'templates' / 'frontend'
        sources = [templates / 'documentation.html']
        sources += sorted((templates / 'documentation').rglob('*.html'))
        self.assertGreaterEqual(len(sources), 11)
        for source in sources:
            text = source.read_text()
            with self.subTest(template=source.name):
                self.assertNotIn('|safe', text)
                self.assertNotIn('autoescape off', text)
                self.assertNotIn('markdown', text.lower())


class SearchPaletteLayoutTests(TestCase):
    """Source-level checks: the enlarged palette is CSS-only, so its geometry
    is verified statically here (a real browser is not available in tests)."""

    def css(self):
        return (Path(settings.BASE_DIR) / 'static' / 'css' / 'components.css').read_text()

    def test_palette_is_wider_and_taller(self):
        css = self.css()
        self.assertIn('#searchPalette .command-panel', css)
        self.assertIn('max-width: min(800px', css)
        self.assertIn('max-height: min(80vh', css)
        self.assertIn('#searchPalette .command-results', css)
        self.assertIn('min-height: min(44vh', css)

    def test_narrow_viewport_rules_exist(self):
        css = self.css()
        self.assertIn('max-width: 480px', css)
        self.assertIn('100dvh', css)
        self.assertIn('#searchPalette .command-item-meta', css)

    def test_preferences_panel_keeps_its_own_size(self):
        css = self.css()
        self.assertIn('.preferences-panel', css)
        self.assertIn('max-height: min(80vh, 640px)', css)

    def test_docs_portal_css_covers_index_and_topics(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'pages.css').read_text()
        for selector in ['.doc-index', '.doc-card', '.doc-body', '.doc-breadcrumb', '.doc-pager']:
            self.assertIn(selector, css, msg=selector)
        self.assertIn('.doc-card[hidden]', css)
