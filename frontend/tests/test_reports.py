from django.test import TestCase
from django.db.models import Sum
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from frontend.models import Category, Product, Person, Sale, SaleItem, AccountReceivable, Payment


class TestReportDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rd', password='t')
        self.cat = Category.objects.create(name='R')
        self.prod = Product.objects.create(name='RProd', code='RP1', category=self.cat, price=Decimal('10'), stock_quantity=5)
        self.pers = Person.objects.create(name='Jo', doc_id='1', person_type='ALUNO')

    def test_dashboard_sales_today(self):
        Sale.objects.create(customer=self.pers, responsible=self.user, status='COMPLETED', payment_method='DINHEIRO', total=Decimal('20'))
        agg = Sale.objects.filter(status='COMPLETED').aggregate(s=Sum('total'))['s'] or Decimal('0')
        self.assertEqual(agg, Decimal('20.00'))

    def test_report_low_stock(self):
        low = Product.objects.filter(active=True, stock_quantity__lte=5).count()
        self.assertGreaterEqual(low, 1)

    def test_report_receivable_open(self):
        rc = AccountReceivable.objects.create(person=self.pers, original_amount=Decimal('30'), due_date='2030-01-01', status='PENDING')
        total = AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).aggregate(s=Sum('original_amount'))['s'] or Decimal('0')
        self.assertEqual(total, Decimal('30.00'))

    def test_report_best_selling(self):
        sale = Sale.objects.create(customer=self.pers, responsible=self.user, status='COMPLETED', payment_method='DINHEIRO', total=Decimal('10'))
        SaleItem.objects.create(sale=sale, product=self.prod, quantity=2, unit_price=Decimal('5'))
        best = SaleItem.objects.filter(sale__status='COMPLETED').values('product__name').annotate(q=Sum('quantity')).order_by('-q')
        names = [b['product__name'] for b in best]
        self.assertIn('RProd', names)

    def test_report_empty_dataset(self):
        total = Sale.objects.filter(status='COMPLETED').aggregate(s=Sum('total'))['s']
        self.assertIsNone(total)
