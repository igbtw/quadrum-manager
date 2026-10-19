from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from frontend.models import Category, Product, Person, Sale, SaleItem, AccountReceivable, StockMovement, Payment


class AuthSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='authtest', password='t')
        self.cat = Category.objects.create(name='AuthC')
        self.prod = Product.objects.create(name='AuthP', code='AP1', category=self.cat, price=Decimal('1'), stock_quantity=10)
        self.pers = Person.objects.create(name='Jo', doc_id='1', person_type='STUDENT')

    def test_login_logout(self):
        resp = self.client.post(reverse('frontend:login'), {'username': 'authtest', 'password': 't'})
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(reverse('frontend:dashboard'))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse('frontend:logout'))
        self.assertEqual(resp.status_code, 405)
        resp = self.client.post(reverse('frontend:logout'))
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(reverse('frontend:products'))
        self.assertEqual(resp.status_code, 302)

    def test_login_wrong_password(self):
        resp = self.client.post(reverse('frontend:login'), {'username': 'authtest', 'password': 'bad'})
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_pos_blocked(self):
        resp = self.client.get(reverse('frontend:point_of_sale'))
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_finance_post_blocked(self):
        resp = self.client.post(reverse('frontend:finance'), {'account_receivable': 1, 'amount': 10, 'method': 'CASH'})
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_pos_access(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('frontend:point_of_sale'))
        self.assertEqual(resp.status_code, 200)

    def test_csrf_missing_on_form_post(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        resp = client.post(reverse('frontend:products'), {'name': 'X', 'category': self.cat.pk, 'price': '1', 'stock_quantity': '1'})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_product_id_in_api(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pos_calculate'), data='{"items":[{"product_id":99999,"quantity":1}]}', content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertIn(resp.status_code, [400, 404])

    def test_anonymous_products_post_blocked(self):
        resp = self.client.post(reverse('frontend:products'), {'name': 'AnonP', 'category': self.cat.pk, 'price': '1', 'stock_quantity': '1'})
        self.assertEqual(resp.status_code, 302)

    def test_auth_products_post_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:products'), {'name': 'AuthP', 'code': '', 'category': self.cat.pk, 'price': '2', 'stock_quantity': '5', 'minimum_stock': '5'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Product.objects.filter(name='AuthP').exists())

    def test_anonymous_people_post_blocked(self):
        resp = self.client.post(reverse('frontend:people'), {'name': 'AnonPers', 'doc_id': '1', 'person_type': 'STUDENT'})
        self.assertEqual(resp.status_code, 302)

    def test_auth_people_post_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:people'), {'name': 'AuthPers', 'doc_id': '2', 'person_type': 'TEACHER'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Person.objects.filter(name='AuthPers').exists())

    def test_xss_safe_output_in_template_context(self):
        p = Product.objects.create(name='<script>alert(1)</script>', code='XSS1', category=self.cat, price=Decimal('1'), stock_quantity=5)
        self.assertIn('<script>', p.name)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='flowuser', password='FlowPass!123')
        self.login_url = reverse('frontend:login')

    def test_login_success_redirects_to_dashboard(self):
        resp = self.client.post(self.login_url, {'username': 'flowuser', 'password': 'FlowPass!123'})
        self.assertRedirects(resp, reverse('frontend:dashboard'))

    def test_login_failure_is_generic(self):
        resp = self.client.post(self.login_url, {'username': 'flowuser', 'password': 'wrong'})
        self.assertEqual(resp.status_code, 200)
        errors = [str(e).lower() for e in resp.context['form'].non_field_errors()]
        self.assertEqual(len(errors), 1)
        self.assertIn('correct username and password', errors[0])

    def test_unknown_user_and_wrong_password_have_same_error(self):
        r1 = self.client.post(self.login_url, {'username': 'nobody', 'password': 'whatever'})
        r2 = self.client.post(self.login_url, {'username': 'flowuser', 'password': 'wrong'})
        self.assertEqual(
            [str(e) for e in r1.context['form'].non_field_errors()],
            [str(e) for e in r2.context['form'].non_field_errors()],
        )

    def test_login_honors_safe_next(self):
        client = Client()
        resp = client.post(self.login_url + '?next=/sales/', {'username': 'flowuser', 'password': 'FlowPass!123'})
        self.assertRedirects(resp, '/sales/')
        client = Client()
        resp = client.post(self.login_url, {'username': 'flowuser', 'password': 'FlowPass!123', 'next': '/products/'})
        self.assertRedirects(resp, '/products/')

    def test_login_rejects_unsafe_next(self):
        for bad in ['https://evil.example.com/', '//evil.example.com/', 'http://evil.example.com/']:
            client = Client()
            resp = client.post(self.login_url, {'username': 'flowuser', 'password': 'FlowPass!123', 'next': bad})
            self.assertRedirects(resp, reverse('frontend:dashboard'))

    def test_unsafe_next_is_not_rendered_on_login_page(self):
        resp = self.client.get(self.login_url + '?next=https://evil.example.com/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'evil.example.com')

    def test_login_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        resp = client.post(self.login_url, {'username': 'flowuser', 'password': 'FlowPass!123'})
        self.assertEqual(resp.status_code, 403)

    def test_authenticated_visitor_redirected_from_auth_pages(self):
        self.client.force_login(self.user)
        for url in [self.login_url, reverse('frontend:register')]:
            self.assertRedirects(self.client.get(url), reverse('frontend:dashboard'))
        resp = self.client.post(self.login_url, {'username': 'flowuser', 'password': 'FlowPass!123'})
        self.assertRedirects(resp, reverse('frontend:dashboard'))


class OperationalAuthorizationTests(TestCase):
    def test_anonymous_dashboard_and_sales_redirect_to_login(self):
        for path in ['/dashboard/', '/sales/', '/']:
            resp = self.client.get(path)
            self.assertRedirects(resp, '/login/?next=%s' % path)

    def test_authenticated_dashboard_and_sales_allowed(self):
        user = User.objects.create_user(username='opuser', password='OpPass!123')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)
        self.assertEqual(self.client.get('/sales/').status_code, 200)


class AuthPageSeparationTests(TestCase):
    DASHBOARD_MARKERS = [
        'id="sidebar"',
        'id="logoutForm"',
        'id="searchPalette"',
        'id="preferencesDialog"',
        'id="notificationPanel"',
        'chart.umd.min.js',
        'js/main.js',
    ]

    def test_anonymous_auth_pages_have_no_dashboard_shell(self):
        for name in ['frontend:login', 'frontend:register']:
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 200)
            for marker in self.DASHBOARD_MARKERS:
                self.assertNotContains(resp, marker)
            # The brand mark is the only Lucide placeholder allowed on auth pages.
            html = resp.content.decode()
            self.assertEqual(html.count('data-lucide'), 1)
            self.assertIn('data-lucide="squares-intersect"', html)

    def test_auth_pages_reuse_theme_boot_and_auth_stylesheet(self):
        for name in ['frontend:login', 'frontend:register']:
            resp = self.client.get(reverse(name))
            self.assertContains(resp, 'quadrum.preferences.v1')
            self.assertContains(resp, 'css/auth.css')
