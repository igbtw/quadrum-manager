import json
from unittest.mock import patch
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
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='STUDENT')
        sale = Sale.objects.create(customer=pers, responsible=self.user, status='PENDING', payment_method='CASH')
        self.assertTrue(sale.code.startswith('VEN-'))
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")
        sale.status = 'COMPLETED'
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")

    def test_cancel_sale_idempotent_and_reversal(self):
        from frontend.models import Person
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='STUDENT')
        cat = Category.objects.create(name='C')
        prod = Product.objects.create(name='P', code='P1', category=cat, price=Decimal('10'), stock_quantity=10)
        sale = Sale.objects.create(customer=pers, responsible=self.user, status='COMPLETED', payment_method='CASH', total=Decimal('20'))
        SaleItem.objects.create(sale=sale, product=prod, quantity=2, unit_price=Decimal('10'))
        reduce_stock(prod, 2, user=self.user, sale=sale)
        cancel_sale(sale, user=self.user)
        self.assertEqual(Sale.objects.get(pk=sale.pk).status, 'CANCELLED')
        self.assertEqual(Product.objects.get(pk=prod.pk).stock_quantity, 10)
        self.assertTrue(StockMovement.objects.filter(sale=sale, movement_type='RETURN').exists())
        cancel_sale(sale, user=self.user)
        self.assertEqual(Product.objects.get(pk=prod.pk).stock_quantity, 10)

    def test_cancel_rejected_if_payments_exist(self):
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='STUDENT')
        cat = Category.objects.create(name='C')
        prod = Product.objects.create(name='P', code='P1', category=cat, price=Decimal('10'), stock_quantity=10)
        sale = Sale.objects.create(customer=pers, responsible=self.user, status='COMPLETED', payment_method='ON_ACCOUNT', total=Decimal('20'))
        SaleItem.objects.create(sale=sale, product=prod, quantity=1, unit_price=Decimal('20'))
        reduce_stock(prod, 1, user=self.user, sale=sale)
        rc = AccountReceivable.objects.create(person=pers, sale=sale, original_amount=Decimal('20'), due_date='2030-01-01', status='PENDING')
        register_payment(rc, Decimal('10'))
        with self.assertRaises(ValueError) as ctx:
            cancel_sale(sale)
        self.assertIn('recorded payments', str(ctx.exception).lower())
        self.assertTrue(Sale.objects.filter(pk=sale.pk).exists())
        # Preserve receivable and payment records after rejection
        rc = AccountReceivable.objects.filter(sale=sale).first()
        self.assertIsNotNone(rc)
        self.assertTrue(Payment.objects.filter(account_receivable=rc).exists())

    def test_api_pdv_calcular_real_product(self):
        from frontend.models import Product
        prod = Product.objects.create(name='APIProd', code='AP', category=Category.objects.create(name='API'), price=Decimal('5'), stock_quantity=10)
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pos_calculate'), data='{"items":[{"product_id":%d,"quantity":2}]}' % prod.pk, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 200)

    def test_api_pdv_calcular_bad_id(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pos_calculate'), data='{"items":[{"product_id":99999,"quantity":1}]}', content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertIn(resp.status_code, [400, 404])

    def test_payment_service_recalculates(self):
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='STUDENT')
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
        resp = self.client.post(reverse('frontend:api_pos_finalize'),
            data='{"items":[{"product_id":%d,"quantity":1,"unit_price":"0.01"}],"payment_method":"CASH","idempotency_key":"ANON-01"}' % prod.pk,
            content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 302)  # redirect to login
        # Authenticated user cannot under-price item
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pos_finalize'),
            data='{"items":[{"product_id":%d,"quantity":2,"unit_price":"1.00"}],"payment_method":"CASH","idempotency_key":"PRICE-01"}' % prod.pk,
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
        payload = '{"items":[{"product_id":%d,"quantity":1}],"payment_method":"CASH","idempotency_key":"KEY-001"}' % prod.pk
        resp1 = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp1.status_code, 200)
        sale1 = Sale.objects.filter(status='COMPLETED').latest('id')
        # Repeat with same session
        resp2 = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
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
        payload = '{"items":[{"product_id":%d,"quantity":1}],"payment_method":"CASH","idempotency_key":"OWN-01"}' % prod.pk
        resp1 = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp1.status_code, 200)
        self.client.force_login(u2)
        resp2 = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp2.status_code, 403)
        self.client.force_login(u1)
        resp3 = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp3.status_code, 200)
        payload_bad = '{"items":[{"product_id":%d,"quantity":99}],"payment_method":"CASH","idempotency_key":"OWN-01"}' % prod.pk
        resp4 = self.client.post(reverse('frontend:api_pos_finalize'), data=payload_bad, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp4.status_code, 409)
        self.assertEqual(Sale.objects.filter(idempotency_key='OWN-01', status='COMPLETED').count(), 1)

    def test_integrityerror_without_matching_record_returns_500(self):
        """IntegrityError without a corresponding sale must return generic 500, not 400 conflict."""
        from unittest.mock import patch
        cat = Category.objects.create(name='IEC')
        prod = Product.objects.create(name='IEP', code='IE', category=cat, price=Decimal('10'), stock_quantity=10)
        self.client.force_login(self.user)
        payload = '{"items":[{"product_id":%d,"quantity":1}],"payment_method":"CASH","idempotency_key":"IE-01"}' % prod.pk
        with patch('frontend.views.Sale.objects.create', side_effect=IntegrityError('simulated')):
            resp = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertNotIn('simulated', str(data.get('error', '')))
        self.assertIn('Internal error', data.get('error', ''))

    def test_unexpected_exception_returns_generic_500(self):
        from unittest.mock import patch
        cat = Category.objects.create(name='ErrC')
        prod = Product.objects.create(name='ErrP', code='ER', category=cat, price=Decimal('1'), stock_quantity=10)
        self.client.force_login(self.user)
        payload = '{"items":[{"product_id":%d,"quantity":1}],"payment_method":"CASH","idempotency_key":"ERR-01"}' % prod.pk
        with patch('frontend.views.Sale.objects.create', side_effect=RuntimeError('internal simulated failure')):
            resp = self.client.post(reverse('frontend:api_pos_finalize'), data=payload, content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertNotIn('internal simulated failure', str(data.get('error', '')))
        self.assertIn('Internal error', data.get('error', ''))
        # Unexpected failures must also roll back every checkout write.
        self.assertEqual(Product.objects.get(pk=prod.pk).stock_quantity, 10)
        self.assertFalse(Sale.objects.filter(idempotency_key='ERR-01').exists())
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.filter(product=prod).count(), 0)
        self.assertEqual(AccountReceivable.objects.count(), 0)

    def test_missing_fingerprint_returns_409(self):
        """Legacy completed sale with key but no fingerprint must not return success."""
        cat = Category.objects.create(name='LegacyC')
        prod = Product.objects.create(name='LegacyP', code='LG', category=cat, price=Decimal('10'), stock_quantity=10)
        pers = Person.objects.create(name='L', doc_id='L', person_type='STUDENT')
        sale = Sale.objects.create(
            customer=pers, responsible=self.user, status='COMPLETED',
            payment_method='CASH', total=Decimal('10'),
            idempotency_key='LEGACY-01', request_fingerprint=None,
        )
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_pos_finalize'),
            data='{"items":[{"product_id":%d,"quantity":1}],"payment_method":"CASH","idempotency_key":"LEGACY-01"}' % prod.pk,
            content_type='application/json', HTTP_X_CSRFTOKEN='fake')
        self.assertEqual(resp.status_code, 409)


class PosApiValidationTests(TestCase):
    """F1/F2/F10: strict POS input validation and safe calculation errors."""

    def setUp(self):
        self.user = User.objects.create_user(username='posval', password='t')
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name='POSVal')
        self.prod = Product.objects.create(
            name='POSValProd', code='PV1', category=self.cat,
            price=Decimal('7.50'), stock_quantity=20,
        )
        self.person = Person.objects.create(name='Cust', doc_id='C1', person_type='STUDENT')

    def _calc(self, payload):
        return self.client.post(
            reverse('frontend:api_pos_calculate'), data=json.dumps(payload),
            content_type='application/json', HTTP_X_CSRFTOKEN='fake',
        )

    def _finalize(self, payload):
        return self.client.post(
            reverse('frontend:api_pos_finalize'), data=json.dumps(payload),
            content_type='application/json', HTTP_X_CSRFTOKEN='fake',
        )

    def _db_state(self):
        return {
            'sales': Sale.objects.count(),
            'items': SaleItem.objects.count(),
            'stock': Product.objects.get(pk=self.prod.pk).stock_quantity,
            'movements': StockMovement.objects.count(),
            'receivables': AccountReceivable.objects.count(),
        }

    # --- Calculation endpoint (F1/F10) ---

    def test_calculate_valid_total(self):
        resp = self._calc({'items': [{'product_id': self.prod.pk, 'quantity': 3}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total'], '22.50')

    def test_calculate_ignores_client_price(self):
        resp = self._calc({'items': [{'product_id': self.prod.pk, 'quantity': 3, 'unit_price': '0.01'}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total'], '22.50')

    def test_calculate_rejects_invalid_quantities(self):
        for bad in [-5, 0, 2.5, 2.0, True, '2', '2.5', None]:
            with self.subTest(quantity=bad):
                resp = self._calc({'items': [{'product_id': self.prod.pk, 'quantity': bad}]})
                self.assertEqual(resp.status_code, 400)

    def test_calculate_rejects_missing_quantity(self):
        resp = self._calc({'items': [{'product_id': self.prod.pk}]})
        self.assertEqual(resp.status_code, 400)

    def test_calculate_rejects_invalid_product_ids(self):
        for bad in ['1', 2.5, True, None, 0, -3]:
            with self.subTest(product_id=bad):
                resp = self._calc({'items': [{'product_id': bad, 'quantity': 1}]})
                self.assertEqual(resp.status_code, 400)

    def test_calculate_rejects_malformed_items(self):
        for items in [[5], 'not-a-list', [{'product_id': self.prod.pk, 'quantity': 1}, 7]]:
            with self.subTest(items=items):
                resp = self._calc({'items': items})
                self.assertEqual(resp.status_code, 400)

    def test_calculate_missing_product_returns_404(self):
        resp = self._calc({'items': [{'product_id': 999999, 'quantity': 1}]})
        self.assertEqual(resp.status_code, 404)
        self.assertIn('not found', resp.json()['error'])

    def test_calculate_unexpected_error_hides_internal_details(self):
        with patch('frontend.views.Product.objects.get', side_effect=RuntimeError('db secret 42')):
            resp = self._calc({'items': [{'product_id': self.prod.pk, 'quantity': 1}]})
        self.assertEqual(resp.status_code, 400)
        body = json.dumps(resp.json())
        self.assertNotIn('db secret', body)
        self.assertEqual(resp.json()['error'], 'Calculation error')

    def test_calculate_malformed_json_returns_controlled_error(self):
        resp = self.client.post(
            reverse('frontend:api_pos_calculate'), data='{not json',
            content_type='application/json', HTTP_X_CSRFTOKEN='fake',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('not json', json.dumps(resp.json()))

    # --- Finalization endpoint (F1/F2) ---

    def _assert_no_writes(self, before):
        self.assertEqual(self._db_state(), before)

    def test_finalize_rejects_invalid_quantities_without_writes(self):
        before = self._db_state()
        for idx, bad in enumerate([-5, 0, 2.5, 2.0, True, '2', '2.5', None]):
            with self.subTest(quantity=bad):
                resp = self._finalize({
                    'items': [{'product_id': self.prod.pk, 'quantity': bad}],
                    'payment_method': 'CASH', 'idempotency_key': f'BADQ-{idx}',
                })
                self.assertEqual(resp.status_code, 400)
        self._assert_no_writes(before)

    def test_finalize_rejects_missing_quantity_without_writes(self):
        before = self._db_state()
        resp = self._finalize({
            'items': [{'product_id': self.prod.pk}],
            'payment_method': 'CASH', 'idempotency_key': 'MISSQ-01',
        })
        self.assertEqual(resp.status_code, 400)
        self._assert_no_writes(before)

    def test_finalize_rejects_invalid_product_ids_without_writes(self):
        before = self._db_state()
        for idx, bad in enumerate(['1', 2.5, True, None, 0, -3]):
            with self.subTest(product_id=bad):
                resp = self._finalize({
                    'items': [{'product_id': bad, 'quantity': 1}],
                    'payment_method': 'CASH', 'idempotency_key': f'BADPID-{idx}',
                })
                self.assertEqual(resp.status_code, 400)
        self._assert_no_writes(before)

    def test_finalize_rejects_invalid_payment_methods_without_writes(self):
        before = self._db_state()
        for idx, bad in enumerate(['cash', 'CASH ', ' ON_ACCOUNT', 'CASH\t', 'BOGUS', '', None, 123, [], {}]):
            with self.subTest(payment_method=bad):
                resp = self._finalize({
                    'items': [{'product_id': self.prod.pk, 'quantity': 1}],
                    'customer_id': self.person.pk,
                    'payment_method': bad, 'idempotency_key': f'BADPM-{idx}',
                })
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.json()['error'], 'Invalid payment method')
        self._assert_no_writes(before)

    def test_finalize_accepts_all_declared_payment_methods(self):
        codes = [code for code, _ in Sale.PAYMENT_METHODS]
        self.assertEqual(codes, ['CASH', 'DEBIT', 'CREDIT', 'PIX', 'ON_ACCOUNT'])
        for idx, code in enumerate(codes):
            payload = {
                'items': [{'product_id': self.prod.pk, 'quantity': 1}],
                'payment_method': code, 'idempotency_key': f'OKPM-{idx}',
            }
            if code == 'ON_ACCOUNT':
                payload['customer_id'] = self.person.pk
            resp = self._finalize(payload)
            self.assertEqual(resp.status_code, 200, msg=f'{code}: {resp.content!r}')
            sale = Sale.objects.get(idempotency_key=f'OKPM-{idx}')
            self.assertEqual(sale.payment_method, code)
            self.assertEqual(sale.status, 'COMPLETED')
            if code == 'ON_ACCOUNT':
                self.assertTrue(AccountReceivable.objects.filter(sale=sale).exists())

    def test_finalize_fingerprint_not_truncated(self):
        # A fractional quantity must not be truncated to 2 and persisted as 2.
        before = self._db_state()
        resp = self._finalize({
            'items': [{'product_id': self.prod.pk, 'quantity': 2.5}],
            'payment_method': 'CASH', 'idempotency_key': 'TRUNC-01',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Sale.objects.filter(idempotency_key='TRUNC-01').exists())
        self._assert_no_writes(before)

    def test_finalize_float_replay_not_treated_as_equivalent(self):
        # Persisted value (int 2) and a float 2.0 must not be treated as the
        # same request: the float is rejected before fingerprinting.
        resp = self._finalize({
            'items': [{'product_id': self.prod.pk, 'quantity': 2}],
            'payment_method': 'CASH', 'idempotency_key': 'FP-01',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SaleItem.objects.get(sale__idempotency_key='FP-01').quantity, 2)
        resp = self._finalize({
            'items': [{'product_id': self.prod.pk, 'quantity': 2.0}],
            'payment_method': 'CASH', 'idempotency_key': 'FP-01',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Sale.objects.filter(status='COMPLETED').count(), 1)
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 18)


class PosFinalizationStockTests(TestCase):
    """F4: insufficient stock is a 409 conflict that rolls back every write."""

    def setUp(self):
        self.user = User.objects.create_user(username='posstock', password='t')
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name='POSStock')
        self.prod = Product.objects.create(
            name='StockProd', code='SP1', category=self.cat,
            price=Decimal('5.00'), stock_quantity=2,
        )

    def _finalize(self, payload):
        return self.client.post(
            reverse('frontend:api_pos_finalize'), data=json.dumps(payload),
            content_type='application/json', HTTP_X_CSRFTOKEN='fake',
        )

    def _assert_no_writes(self, before):
        self.assertEqual(Sale.objects.count(), before['sales'])
        self.assertEqual(SaleItem.objects.count(), before['items'])
        self.assertEqual(StockMovement.objects.count(), before['movements'])
        self.assertEqual(AccountReceivable.objects.count(), before['receivables'])
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, before['stock'])

    def _db_state(self):
        return {
            'sales': Sale.objects.count(),
            'items': SaleItem.objects.count(),
            'stock': Product.objects.get(pk=self.prod.pk).stock_quantity,
            'movements': StockMovement.objects.count(),
            'receivables': AccountReceivable.objects.count(),
        }

    def test_finalize_insufficient_stock_returns_409_and_rolls_back(self):
        before = self._db_state()
        resp = self._finalize({
            'items': [{'product_id': self.prod.pk, 'quantity': 3}],
            'payment_method': 'CASH', 'idempotency_key': 'STOCK-01',
        })
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['error'], 'Insufficient stock')
        self.assertNotIn('Negative stock', resp.content.decode())
        self.assertFalse(Sale.objects.filter(idempotency_key='STOCK-01').exists())
        self._assert_no_writes(before)

    def test_finalize_duplicate_lines_exceeding_stock_rolls_back(self):
        before = self._db_state()
        resp = self._finalize({
            'items': [
                {'product_id': self.prod.pk, 'quantity': 2},
                {'product_id': self.prod.pk, 'quantity': 1},
            ],
            'payment_method': 'CASH', 'idempotency_key': 'STOCK-02',
        })
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['error'], 'Insufficient stock')
        self.assertFalse(Sale.objects.filter(idempotency_key='STOCK-02').exists())
        self._assert_no_writes(before)

    def test_finalize_sufficient_stock_still_succeeds(self):
        resp = self._finalize({
            'items': [{'product_id': self.prod.pk, 'quantity': 2}],
            'payment_method': 'CASH', 'idempotency_key': 'STOCK-03',
        })
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertTrue(resp.json()['success'])
        sale = Sale.objects.get(idempotency_key='STOCK-03')
        self.assertEqual(sale.status, 'COMPLETED')
        self.assertEqual(SaleItem.objects.get(sale=sale).quantity, 2)
        self.assertEqual(
            StockMovement.objects.filter(sale=sale, movement_type='SALE').count(), 1
        )
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 0)
