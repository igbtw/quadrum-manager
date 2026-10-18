from django.test import TestCase
from decimal import Decimal
from frontend.forms import ProductForm, PersonForm, PaymentForm
from frontend.models import Category, Product, Person, AccountReceivable


class FormTests(TestCase):
    def test_product_form_valid(self):
        cat = Category.objects.create(name='C')
        form = ProductForm(data={'name': 'X', 'code': 'X1', 'category': cat.pk, 'price': '10', 'stock_quantity': '5', 'minimum_stock': '2', 'active': True})
        self.assertTrue(form.is_valid())

    def test_product_form_negative_price(self):
        cat = Category.objects.create(name='C')
        form = ProductForm(data={'name': 'X', 'category': cat.pk, 'price': '-1', 'stock_quantity': '1'})
        self.assertFalse(form.is_valid())

    def test_person_form_valid(self):
        form = PersonForm(data={'name': 'Jo', 'doc_id': 'D', 'person_type': 'STUDENT'})
        self.assertTrue(form.is_valid())

    def test_payment_form_over_balance(self):
        from frontend.models import register_payment
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='STUDENT')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('10'), due_date='2030-01-01', status='PENDING')
        form = PaymentForm(data={'account_receivable': rc.pk, 'amount': '100', 'method': 'CASH'})
        self.assertFalse(form.is_valid())

    def test_payment_form_valid(self):
        pers = Person.objects.create(name='Jo', doc_id='D', person_type='STUDENT')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('100'), due_date='2030-01-01', status='PENDING')
        form = PaymentForm(data={'account_receivable': rc.pk, 'amount': '30', 'method': 'CASH'})
        self.assertTrue(form.is_valid())

    def test_payment_form_excludes_cancelled_receivables(self):
        pers = Person.objects.create(name='Jo', doc_id='D2', person_type='STUDENT')
        cancelled = AccountReceivable.objects.create(
            person=pers, original_amount=Decimal('50'), due_date='2030-01-01',
            status='CANCELLED',
        )
        open_rc = AccountReceivable.objects.create(
            person=pers, original_amount=Decimal('50'), due_date='2030-01-01',
            status='PENDING',
        )
        queryset = PaymentForm().fields['account_receivable'].queryset
        self.assertNotIn(cancelled, queryset)
        self.assertIn(open_rc, queryset)

        form = PaymentForm(data={'account_receivable': cancelled.pk, 'amount': '10', 'method': 'CASH'})
        self.assertFalse(form.is_valid())
        self.assertIn('account_receivable', form.errors)

        form = PaymentForm(data={'account_receivable': open_rc.pk, 'amount': '10', 'method': 'CASH'})
        self.assertTrue(form.is_valid())
