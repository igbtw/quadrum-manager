from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from frontend.models import Category, Product, Person, Sale, SaleItem, StockMovement, AccountReceivable, Payment
from frontend.services import cancel_sale, finalize_sale, create_sale_items, reduce_stock
from frontend.models import register_payment
from django.db import IntegrityError


class PhaseARegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='t')

    def test_sale_code_format_from_pk(self):
        from frontend.models import Person
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='ALUNO')
        sale = Sale.objects.create(customer=pers, responsible=self.user, status='PENDING', payment_method='DINHEIRO')
        self.assertTrue(sale.code.startswith('VEN-'))
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")
        sale.status = 'COMPLETED'
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")

    def test_cancel_sale_idempotent_and_reversal(self):
        from frontend.models import Person
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='ALUNO')
        cat = Category.objects.create(name='C')
        prod = Product.objects.create(name='P', code='P1', category=cat, price=Decimal('10'), stock_quantity=10)
        sale = Sale.objects.create(customer=pers, responsible=self.user, status='COMPLETED', payment_method='DINHEIRO', total=Decimal('20'))
        SaleItem.objects.create(sale=sale, product=prod, quantity=2, unit_price=Decimal('10'))
        reduce_stock(prod, 2, user=self.user, sale=sale)
        cancel_sale(sale, user=self.user)
        self.assertEqual(Sale.objects.get(pk=sale.pk).status, 'CANCELLED')
        self.assertEqual(Product.objects.get(pk=prod.pk).stock_quantity, 10)
        self.assertTrue(StockMovement.objects.filter(sale=sale, movement_type='RETURN').exists())
        cancel_sale(sale, user=self.user)
        self.assertEqual(Product.objects.get(pk=prod.pk).stock_quantity, 10)

    def test_cancel_rejected_if_payments_exist(self):
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='ALUNO')
        cat = Category.objects.create(name='C')
        prod = Product.objects.create(name='P', code='P1', category=cat, price=Decimal('10'), stock_quantity=10)
        sale = Sale.objects.create(customer=pers, responsible=self.user, status='COMPLETED', payment_method='A_PRAZO', total=Decimal('20'))
        SaleItem.objects.create(sale=sale, product=prod, quantity=1, unit_price=Decimal('20'))
        reduce_stock(prod, 1, user=self.user, sale=sale)
        rc = AccountReceivable.objects.create(person=pers, sale=sale, original_amount=Decimal('20'), due_date='2030-01-01', status='PENDING')
        register_payment(rc, Decimal('10'))
        with self.assertRaises(ValueError) as ctx:
            cancel_sale(sale)
        self.assertIn('pagamentos', str(ctx.exception).lower())
        self.assertTrue(Sale.objects.filter(pk=sale.pk).exists())
        # Preserve receivable and payment records after rejection
        rc = AccountReceivable.objects.filter(sale=sale).first()
        self.assertIsNotNone(rc)
        self.assertTrue(Payment.objects.filter(account_receivable=rc).exists())

    def test_api_pdv_calcular_real_product(self):
        from frontend.models import Product
        prod = Product.objects.create(name='APIProd', code='AP', category=Category.objects.create(name='API'), price=Decimal('5'), stock_quantity=10)
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pdv_calcular'), data='{"itens":[{"produto_id":%d,"quantidade":2}]}' % prod.pk, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 200)

    def test_api_pdv_calcular_bad_id(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pdv_calcular'), data='{"itens":[{"produto_id":99999,"quantidade":1}]}', content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertIn(resp.status_code, [400, 404])

    def test_payment_service_recalculates(self):
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='ALUNO')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('100'), due_date='2030-01-01', status='PENDING')
        register_payment(rc, Decimal('30'))
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PARTIAL')
        self.assertEqual(rc.remaining_balance, Decimal('70'))

    def test_api_pdv_requires_login_and_ignores_client_price(self):
        """Regression: anonymous users must not finalize sales or manipulate prices."""
        cat = Category.objects.create(name='RegC')
        prod = Product.objects.create(name='RegP', code='RP', category=cat, price=Decimal('99.99'), stock_quantity=50)
        # Anonymous access must be denied
        resp = self.client.post(reverse('frontend:api_pdv_finalizar'),
            data='{"itens":[{"produto_id":%d,"quantidade":1,"preco_unitario":"0.01"}],"forma_pagamento":"DINHEIRO","idempotency_key":"ANON-01"}' % prod.pk,
            content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 302)  # redirect to login
        # Authenticated user cannot under-price item
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pdv_finalizar'),
            data='{"itens":[{"produto_id":%d,"quantidade":2,"preco_unitario":"1.00"}],"forma_pagamento":"DINHEIRO","idempotency_key":"PRICE-01"}' % prod.pk,
            content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 200)
        sale = Sale.objects.filter(status='COMPLETED').latest('id')
        item = sale.items.first()
        self.assertEqual(item.unit_price, Decimal('99.99'))
        self.assertEqual(sale.total, Decimal('199.98'))

    def test_duplicate_finalization_idempotent(self):
        """Same session + same payload should not create second sale."""
        cat = Category.objects.create(name='DupC')
        prod = Product.objects.create(name='DupP', code='DP', category=cat, price=Decimal('5'), stock_quantity=10)
        self.client.force_login(self.user)
        payload = '{"itens":[{"produto_id":%d,"quantidade":1}],"forma_pagamento":"DINHEIRO","idempotency_key":"KEY-001"}' % prod.pk
        resp1 = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp1.status_code, 200)
        sale1 = Sale.objects.filter(status='COMPLETED').latest('id')
        # Repeat with same session
        resp2 = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp2.status_code, 200)
        # Must not create second completed sale
        self.assertEqual(Sale.objects.filter(status='COMPLETED').count(), 1)
        # Inventory decremented exactly once
        self.assertEqual(Product.objects.get(pk=prod.pk).stock_quantity, 9)

    def test_idempotency_ownership_and_conflict(self):
        """Same key different user => 403; different fingerprint => 409; same => 200."""
        from frontend.models import Sale
        cat = Category.objects.create(name='OwnC')
        prod = Product.objects.create(name='OwnP', code='OW', category=cat, price=Decimal('10'), stock_quantity=10)
        u1 = User.objects.create_user('ow1', password='t')
        u2 = User.objects.create_user('ow2', password='t')
        self.client.force_login(u1)
        payload = '{"itens":[{"produto_id":%d,"quantidade":1}],"forma_pagamento":"DINHEIRO","idempotency_key":"OWN-01"}' % prod.pk
        resp1 = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp1.status_code, 200)
        self.client.force_login(u2)
        resp2 = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp2.status_code, 403)
        self.client.force_login(u1)
        resp3 = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp3.status_code, 200)
        payload_bad = '{"itens":[{"produto_id":%d,"quantidade":99}],"forma_pagamento":"DINHEIRO","idempotency_key":"OWN-01"}' % prod.pk
        resp4 = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload_bad, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp4.status_code, 409)
        self.assertEqual(Sale.objects.filter(idempotency_key='OWN-01', status='COMPLETED').count(), 1)

    def test_integrityerror_without_matching_record_returns_500(self):
        """IntegrityError without a corresponding sale must return generic 500, not 400 conflict."""
        from unittest.mock import patch
        cat = Category.objects.create(name='IEC')
        prod = Product.objects.create(name='IEP', code='IE', category=cat, price=Decimal('10'), stock_quantity=10)
        self.client.force_login(self.user)
        payload = '{"itens":[{"produto_id":%d,"quantidade":1}],"forma_pagamento":"DINHEIRO","idempotency_key":"IE-01"}' % prod.pk
        with patch('frontend.views.Sale.objects.create', side_effect=IntegrityError('simulated')):
            resp = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertNotIn('simulated', str(data.get('error', '')))
        self.assertIn('Erro interno', data.get('error', ''))

    def test_unexpected_exception_returns_generic_500(self):
        from unittest.mock import patch
        cat = Category.objects.create(name='ErrC')
        prod = Product.objects.create(name='ErrP', code='ER', category=cat, price=Decimal('1'), stock_quantity=10)
        self.client.force_login(self.user)
        payload = '{"itens":[{"produto_id":%d,"quantidade":1}],"forma_pagamento":"DINHEIRO","idempotency_key":"ERR-01"}' % prod.pk
        with patch('frontend.views.Sale.objects.create', side_effect=RuntimeError('internal simulated failure')):
            resp = self.client.post(reverse('frontend:api_pdv_finalizar'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertNotIn('internal simulated failure', str(data.get('error', '')))
        self.assertIn('Erro interno', data.get('error', ''))

    def test_missing_fingerprint_returns_409(self):
        """Legacy completed sale with key but no fingerprint must not return success."""
        cat = Category.objects.create(name='LegacyC')
        prod = Product.objects.create(name='LegacyP', code='LG', category=cat, price=Decimal('10'), stock_quantity=10)
        pers = Person.objects.create(name='L', doc_id='L', person_type='ALUNO')
        sale = Sale.objects.create(
            customer=pers, responsible=self.user, status='COMPLETED',
            payment_method='DINHEIRO', total=Decimal('10'),
            idempotency_key='LEGACY-01', request_fingerprint=None,
        )
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pdv_finalizar'),
            data='{"itens":[{"produto_id":%d,"quantidade":1}],"forma_pagamento":"DINHEIRO","idempotency_key":"LEGACY-01"}' % prod.pk,
            content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 409)
