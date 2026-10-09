from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
from frontend.models import Category, Product, Person, Sale, SaleItem, StockMovement, AccountReceivable, Payment
from frontend.services import cancel_sale, finalize_sale, create_sale_items, reduce_stock
from frontend.models import register_payment

class PhaseARegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='t')
        self.cat = Category.objects.create(name='Test')
        self.prod = Product.objects.create(name='P', code='P1', category=self.cat, price=Decimal('10'), stock_quantity=10)
        self.pers = Person.objects.create(name='Jo', doc_id='1', person_type='ALUNO')

    # Rule 3: code format VEN-000123 from saved PK, never overwritten, never count/MAX
    def test_sale_code_format_from_pk(self):
        sale = Sale.objects.create(customer=self.pers, responsible=self.user, status='PENDING', payment_method='DINHEIRO')
        self.assertTrue(sale.code.startswith('VEN-'))
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")
        sale.status = 'COMPLETED'
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")  # preserved

    # Rule 2: cancellation is idempotent; restores stock once; creates RETURN movement
    def test_cancel_sale_idempotent_and_reversal(self):
        sale = Sale.objects.create(customer=self.pers, responsible=self.user, status='COMPLETED', payment_method='DINHEIRO', total=Decimal('20'))
        item = SaleItem.objects.create(sale=sale, product=self.prod, quantity=2, unit_price=Decimal('10'))
        reduce_stock(self.prod, 2, user=self.user, sale=sale)
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 8)
        cancel_sale(sale, user=self.user)
        self.assertEqual(Sale.objects.get(pk=sale.pk).status, 'CANCELLED')
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 10)
        self.assertTrue(StockMovement.objects.filter(sale=sale, movement_type='RETURN').exists())
        # Idempotent retry
        cancel_sale(sale, user=self.user)
        # Stock must not increase twice
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 10)

    # Rule 1: cancellation rejected when payments exist; receivable preserved
    def test_cancel_rejected_if_payments_exist(self):
        sale = Sale.objects.create(customer=self.pers, responsible=self.user, status='COMPLETED', payment_method='A_PRAZO', total=Decimal('100'))
        SaleItem.objects.create(sale=sale, product=self.prod, quantity=1, unit_price=Decimal('100'))
        reduce_stock(self.prod, 1, user=self.user, sale=sale)
        rc = AccountReceivable.objects.create(person=self.pers, sale=sale, original_amount=Decimal('100'), due_date='2025-01-01', status='PENDING')
        register_payment(rc, Decimal('50'))
        with self.assertRaises(ValueError) as ctx:
            cancel_sale(sale)
        self.assertIn('pagamentos', str(ctx.exception).lower())
        # Preserved records
        self.assertTrue(Sale.objects.filter(pk=sale.pk).exists())
        self.assertTrue(AccountReceivable.objects.filter(pk=rc.pk).exists())
        self.assertTrue(Payment.objects.filter(account_receivable=rc).exists())

    # Rule 4: payment service recalculates; save hook guarded
    def test_payment_service_recalculates(self):
        rc = AccountReceivable.objects.create(person=self.pers, original_amount=Decimal('100'), due_date='2030-01-01', status='PENDING')
        p = register_payment(rc, Decimal('30'))
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PARTIAL')
        self.assertEqual(rc.remaining_balance, Decimal('70'))

    # Rule 5: API fix regression
    def test_api_pdv_calcular_real_product(self):
        client = Client()
        client.force_login(self.user)
        from frontend.models import Product
        resp = client.post('/api/pdv/calcular/', data='{"itens":[{"produto_id":%d,"quantidade":2}]}' % self.prod.pk, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        import json
        data = json.loads(resp.content)
        self.assertIn('total', data)
        self.assertEqual(float(data['total']), 20.0)

    def test_api_pdv_calcular_bad_id(self):
        client = Client()
        client.force_login(self.user)
        resp = client.post('/api/pdv/calcular/', data='{"itens":[{"produto_id":9999,"quantidade":1}]}', content_type='application/json')
        self.assertEqual(resp.status_code, 404)
