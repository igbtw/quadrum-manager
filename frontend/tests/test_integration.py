from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
from frontend.models import Category, Product, Person, Sale, SaleItem, StockMovement, AccountReceivable, Payment
from frontend.services import cancel_sale, finalize_sale, create_sale_items, reduce_stock
from frontend.models import register_payment

class PhaseCIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='int', password='t')
        self.cat = Category.objects.create(name='Int')
        self.prod = Product.objects.create(name='IntProd', code='IP1', category=self.cat, price=Decimal('5'), stock_quantity=20)
        self.pers = Person.objects.create(name='IntPers', doc_id='99', person_type='ALUNO')

    # A. Product and inventory
    def test_product_and_inventory_flow(self):
        from frontend.services import adjust_stock
        adjust_stock(self.prod, 10, reason='Entrada', user=self.user)
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 30)
        self.assertTrue(StockMovement.objects.filter(product=self.prod, movement_type='ADJUSTMENT').exists())

    # B. Sale confirmation with items
    def test_sale_confirm_items_and_stock(self):
        from frontend.services import finalize_sale, create_sale_items
        sale = Sale.objects.create(customer=self.pers, responsible=self.user, status='PENDING', payment_method='DINHEIRO')
        create_sale_items(sale, [{'product_id': self.prod.pk, 'quantity': 3}], user=self.user)
        finalize_sale(sale, user=self.user)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'COMPLETED')
        self.assertEqual(SaleItem.objects.filter(sale=sale).count(), 1)
        self.assertEqual(SaleItem.objects.get(sale=sale).unit_price, Decimal('5'))
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 17)

    # C. Receivable partial and complete
    def test_receivable_partial_and_complete(self):
        from frontend.models import register_payment
        rc = AccountReceivable.objects.create(person=self.pers, original_amount=Decimal('100'), due_date='2030-01-01', status='PENDING')
        register_payment(rc, Decimal('40'))
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PARTIAL')
        self.assertEqual(rc.remaining_balance, Decimal('60'))
        register_payment(rc, Decimal('60'))
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PAID')

    # D. Cancellation and idempotency (existing Phase A policy)
    def test_cancel_idempotent_and_rejected_with_payments(self):
        sale = Sale.objects.create(customer=self.pers, responsible=self.user, status='COMPLETED', payment_method='DINHEIRO', total=Decimal('10'))
        item = SaleItem.objects.create(sale=sale, product=self.prod, quantity=2, unit_price=Decimal('5'))
        from frontend.services import reduce_stock, cancel_sale
        reduce_stock(self.prod, 2, user=self.user, sale=sale)
        cancel_sale(sale, user=self.user)
        self.assertEqual(Sale.objects.get(pk=sale.pk).status, 'CANCELLED')
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 20)
        cancel_sale(sale, user=self.user)  # idempotent
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, 20)
        # With payments: reject
        rc = AccountReceivable.objects.create(person=self.pers, sale=sale, original_amount=Decimal('10'), due_date='2030-01-01', status='PENDING')
        register_payment(rc, Decimal('5'))
        # Create new completed sale for rejection test
        sale2 = Sale.objects.create(customer=self.pers, responsible=self.user, status='COMPLETED', payment_method='A_PRAZO', total=Decimal('20'))
        SaleItem.objects.create(sale=sale2, product=self.prod, quantity=1, unit_price=Decimal('20'))
        rc2 = AccountReceivable.objects.create(person=self.pers, sale=sale2, original_amount=Decimal('20'), due_date='2030-01-01', status='PENDING')
        register_payment(rc2, Decimal('10'))
        with self.assertRaises(ValueError):
            cancel_sale(sale2)

    # E. Validation / authorization / failure rollback
    def test_failed_inventory_does_not_partial_update(self):
        from frontend.services import adjust_stock
        initial = Product.objects.get(pk=self.prod.pk).stock_quantity
        # Non-existent product should raise; nothing should change
        with self.assertRaises(Exception):
            adjust_stock(Product(pk=99999), 10, reason='bad')
        self.assertEqual(Product.objects.get(pk=self.prod.pk).stock_quantity, initial)

    # Security: unauthorized actions not tested via client auth here; server requires login via decorator
    def test_duplicate_payment_blocked(self):
        rc = AccountReceivable.objects.create(person=self.pers, original_amount=Decimal('50'), due_date='2030-01-01', status='PENDING')
        from frontend.models import register_payment, Payment
        register_payment(rc, Decimal('20'))
        # Second registration over balance should raise
        with self.assertRaises(ValueError):
            register_payment(rc, Decimal('40'))

    def test_invalid_payment_rejected(self):
        rc = AccountReceivable.objects.create(person=self.pers, original_amount=Decimal('50'), due_date='2030-01-01', status='PENDING')
        from frontend.models import Payment
        p = Payment(account_receivable=rc, amount=Decimal('100'), method='DINHEIRO')
        with self.assertRaises(Exception):
            p.full_clean()
