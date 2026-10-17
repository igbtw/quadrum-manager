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
        self.assertEqual(resp.status_code, 302)

    def test_login_wrong_password(self):
        resp = self.client.post(reverse('frontend:login'), {'username': 'authtest', 'password': 'bad'})
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_pdv_blocked(self):
        resp = self.client.get(reverse('frontend:pdv'))
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_finance_post_blocked(self):
        resp = self.client.post(reverse('frontend:financeiro'), {'account_receivable': 1, 'amount': 10, 'method': 'CASH'})
        self.assertEqual(resp.status_code, 302)

    def test_authenticated_pdv_access(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('frontend:pdv'))
        self.assertEqual(resp.status_code, 200)

    def test_csrf_missing_on_form_post(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        resp = client.post(reverse('frontend:produtos'), {'name': 'X', 'category': self.cat.pk, 'price': '1', 'stock_quantity': '1'})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_product_id_in_api(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pdv_calcular'), data='{"items":[{"product_id":99999,"quantity":1}]}', content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertIn(resp.status_code, [400, 404])

    def test_anonymous_produtos_post_blocked(self):
        resp = self.client.post(reverse('frontend:produtos'), {'name': 'AnonP', 'category': self.cat.pk, 'price': '1', 'stock_quantity': '1'})
        self.assertEqual(resp.status_code, 302)

    def test_auth_produtos_post_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:produtos'), {'name': 'AuthP', 'code': '', 'category': self.cat.pk, 'price': '2', 'stock_quantity': '5', 'minimum_stock': '5'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Product.objects.filter(name='AuthP').exists())

    def test_anonymous_pessoas_post_blocked(self):
        resp = self.client.post(reverse('frontend:pessoas'), {'name': 'AnonPers', 'doc_id': '1', 'person_type': 'STUDENT'})
        self.assertEqual(resp.status_code, 302)

    def test_auth_pessoas_post_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:pessoas'), {'name': 'AuthPers', 'doc_id': '2', 'person_type': 'TEACHER'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Person.objects.filter(name='AuthPers').exists())

    def test_xss_safe_output_in_template_context(self):
        p = Product.objects.create(name='<script>alert(1)</script>', code='XSS1', category=self.cat, price=Decimal('1'), stock_quantity=5)
        self.assertIn('<script>', p.name)
