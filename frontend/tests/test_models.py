from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from frontend.models import Category, Product, Person, Sale, SaleItem, StockMovement, AccountReceivable, Payment


class ModelTests(TestCase):
    def test_category_create(self):
        c = Category.objects.create(name='Bebidas', description='test')
        self.assertEqual(c.name, 'Bebidas')
        self.assertTrue(c.active)

    def test_category_unique_name(self):
        Category.objects.create(name='Dup')
        with self.assertRaises(Exception):
            Category.objects.create(name='Dup')

    def test_product_create_and_constraints(self):
        cat = Category.objects.create(name='C')
        p = Product.objects.create(name='P', code='P1', category=cat, price=Decimal('5.50'), stock_quantity=10)
        self.assertEqual(p.stock_quantity, 10)
        self.assertTrue(p.active)

    def test_product_negative_stock_check_constraint(self):
        cat = Category.objects.create(name='C')
        p = Product.objects.create(name='P', code='P2', category=cat, price=Decimal('1'), stock_quantity=0)
        # DB check constraint prevents negative via save; test via direct SQL would need DB
        with self.assertRaises(Exception):
            p.stock_quantity = -1
            p.save()

    def test_person_types(self):
        for t, label in Person.PERSON_TYPES:
            p = Person.objects.create(name='X', doc_id=t, person_type=t)
            self.assertEqual(p.person_type, t)

    def test_sale_code_generated_from_pk(self):
        pers = Person.objects.create(name='Jo', doc_id='1', person_type='STUDENT')
        sale = Sale.objects.create(customer=pers, status='PENDING', payment_method='CASH')
        self.assertTrue(sale.code.startswith('VEN-'))
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")
        sale.status = 'COMPLETED'
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.code, f"VEN-{sale.pk:06d}")  # preserved

    def test_sale_item_subtotal_computation(self):
        cat = Category.objects.create(name='C')
        prod = Product.objects.create(name='P', code='P3', category=cat, price=Decimal('5'))
        pers = Person.objects.create(name='Jo', doc_id='1', person_type='STUDENT')
        sale = Sale.objects.create(customer=pers, status='PENDING', payment_method='CASH', total=Decimal('0'))
        item = SaleItem.objects.create(sale=sale, product=prod, quantity=3, unit_price=Decimal('5'))
        self.assertEqual(item.subtotal, Decimal('15.00'))

    def test_stock_movement_types(self):
        cat = Category.objects.create(name='C')
        prod = Product.objects.create(name='P', code='P4', category=cat, price=Decimal('1'), stock_quantity=10)
        sm = StockMovement.objects.create(product=prod, movement_type='SALE', quantity=-2, reason='v')
        self.assertEqual(sm.movement_type, 'SALE')

    def test_payment_clean_rejects_over_balance(self):
        pers = Person.objects.create(name='Jo', doc_id='1', person_type='STUDENT')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('50'), due_date='2030-01-01', status='PENDING')
        p = Payment(account_receivable=rc, amount=Decimal('100'), method='CASH')
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_payment_amount_positive(self):
        pers = Person.objects.create(name='Jo', doc_id='1', person_type='STUDENT')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('50'), due_date='2030-01-01', status='PENDING')
        p = Payment(account_receivable=rc, amount=Decimal('0.01'), method='CASH')
        p.full_clean()
        self.assertTrue(True)
