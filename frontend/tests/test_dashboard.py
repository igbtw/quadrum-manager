"""Dashboard KPI truthfulness: values come from the database and the
comparison/status labels never claim activity that did not happen.

Dates are always derived from the current local date, never hardcoded.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from frontend.models import AccountReceivable, Category, Person, Product, Sale, SaleItem


def local_noon(day):
    return timezone.make_aware(datetime.combine(day, time(12, 0)))


class DashboardTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dash-user', password='test-pass-123')
        self.client.force_login(self.user)
        self.url = reverse('frontend:dashboard')
        self.today = timezone.localdate()
        self.yesterday = self.today - timedelta(days=1)
        self.category = Category.objects.create(name='Bebidas')
        self.product = Product.objects.create(
            name='Suco', code='SUCO1', category=self.category,
            price=Decimal('10.00'), stock_quantity=20, minimum_stock=5,
        )

    def make_sale(self, day, total='10.00', status='COMPLETED', quantity=1):
        sale = Sale.objects.create(
            responsible=self.user,
            status=status, subtotal=Decimal(total), total=Decimal(total),
        )
        SaleItem.objects.create(
            sale=sale, product=self.product,
            quantity=quantity, unit_price=Decimal(total) / quantity,
        )
        Sale.objects.filter(pk=sale.pk).update(created_at=local_noon(day))
        return sale

    def get_stats(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode(), response.context['stats']

    def assert_delta(self, delta, value, label, css_class):
        self.assertEqual(delta['value'], value)
        self.assertEqual(delta['label'], label)
        self.assertEqual(delta['class'], css_class)


class EmptyOperationalDatabaseTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.product.delete()

    def test_empty_database_shows_zeros_and_neutral_labels(self):
        html, stats = self.get_stats()
        self.assertEqual(stats['sales_today'], 0)
        self.assertEqual(stats['daily_revenue'], Decimal('0.00'))
        self.assertEqual(stats['receivables_total'], Decimal('0.00'))
        self.assertEqual(stats['receivables_open_count'], 0)
        self.assertEqual(stats['low_stock_count'], 0)
        self.assertEqual(stats['low_inventory_meta'], {'text': 'no products', 'warn': False})
        self.assert_delta(stats['sales_delta'], '—', 'no activity in either period', '')
        self.assert_delta(stats['revenue_delta'], '—', 'no activity in either period', '')

        self.assertIn('R$ 0.00', html)
        self.assertIn('no open accounts', html)
        self.assertIn('no products', html)
        self.assertEqual(html.count('no activity in either period'), 2)
        self.assertNotIn('needs attention', html)
        self.assertNotIn('kpi-sub-warn', html)
        self.assertNotIn('+12%', html)
        self.assertNotIn('+8.4%', html)
        self.assertNotIn('vs. yesterday', html)
        self.assertNotIn('open account', html.replace('no open accounts', ''))

    def test_empty_database_chart_is_all_zero_units(self):
        html, stats = self.get_stats()
        chart = stats['sales_chart']
        self.assertEqual(len(chart['labels']), 7)
        self.assertEqual(chart['units'], [0, 0, 0, 0, 0, 0, 0])
        self.assertIn('id="sales-chart-data"', html)


class NoSalesInEitherPeriodTests(DashboardTestCase):
    def test_neutral_comparison_when_both_days_are_empty(self):
        html, stats = self.get_stats()
        self.assertEqual(stats['sales_today'], 0)
        self.assert_delta(stats['sales_delta'], '—', 'no activity in either period', '')
        self.assert_delta(stats['revenue_delta'], '—', 'no activity in either period', '')
        self.assertEqual(html.count('no activity in either period'), 2)
        self.assertNotIn('vs. yesterday', html)
        self.assertNotIn('kpi-delta-up', html)
        self.assertNotIn('kpi-delta-down', html)


class NoReceivablesTests(DashboardTestCase):
    def test_no_receivables_shows_zero_and_no_open_accounts(self):
        self.make_sale(self.today, total='25.00')
        html, stats = self.get_stats()
        self.assertEqual(stats['receivables_total'], Decimal('0.00'))
        self.assertEqual(stats['receivables_open_count'], 0)
        self.assertEqual(stats['overdue_total'], Decimal('0.00'))
        self.assertIn('R$ 0.00', html)
        self.assertIn('no open accounts', html)


class NoProductsTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.product.delete()

    def test_no_products_means_no_low_inventory_claims(self):
        html, stats = self.get_stats()
        self.assertEqual(stats['low_stock_count'], 0)
        self.assertEqual(stats['low_inventory_meta'], {'text': 'no products', 'warn': False})
        self.assertIn('no products', html)
        self.assertNotIn('needs attention', html)
        self.assertNotIn('kpi-sub-warn', html)
        self.assertNotIn('Stock OK', html)


class SalesTodayTests(DashboardTestCase):
    def test_today_sales_and_revenue_are_real_and_comparison_is_not_invented(self):
        self.make_sale(self.today, total='20.00', quantity=3)
        self.make_sale(self.today, total='30.00', quantity=2)
        self.make_sale(self.today, total='99.00', quantity=7, status='CANCELLED')

        html, stats = self.get_stats()
        self.assertEqual(stats['sales_today'], 2)
        self.assertEqual(stats['daily_revenue'], Decimal('50.00'))
        self.assert_delta(stats['sales_delta'], 'New', 'no sales yesterday', 'kpi-delta-up')
        self.assert_delta(stats['revenue_delta'], 'New', 'no revenue yesterday', 'kpi-delta-up')

        self.assertIn('R$ 50.00', html)
        self.assertIn('no sales yesterday', html)
        self.assertIn('no revenue yesterday', html)
        self.assertIn('kpi-delta-up', html)
        self.assertNotIn('kpi-delta-down', html)
        self.assertNotIn('+12%', html)

    def test_chart_units_count_completed_sales_only(self):
        self.make_sale(self.today, total='20.00', quantity=3)
        self.make_sale(self.today, total='30.00', quantity=2)
        self.make_sale(self.today, total='99.00', quantity=7, status='CANCELLED')

        _, stats = self.get_stats()
        units = stats['sales_chart']['units']
        self.assertEqual(units[-1], 5)
        self.assertEqual(units[:-1], [0, 0, 0, 0, 0, 0])


class SalesYesterdayOnlyTests(DashboardTestCase):
    def test_yesterday_activity_gives_negative_hundred_percent(self):
        self.make_sale(self.yesterday, total='40.00', quantity=4)

        html, stats = self.get_stats()
        self.assertEqual(stats['sales_today'], 0)
        self.assertEqual(stats['daily_revenue'], Decimal('0.00'))
        self.assert_delta(stats['sales_delta'], '-100%', 'vs. yesterday', 'kpi-delta-down')
        self.assert_delta(stats['revenue_delta'], '-100%', 'vs. yesterday', 'kpi-delta-down')

        self.assertIn('R$ 0.00', html)
        self.assertIn('kpi-delta-down', html)
        self.assertNotIn('kpi-delta-up', html)
        self.assertIn('vs. yesterday', html)

    def test_chart_shows_yesterday_units(self):
        self.make_sale(self.yesterday, total='40.00', quantity=4)

        _, stats = self.get_stats()
        units = stats['sales_chart']['units']
        self.assertEqual(units[-2], 4)
        self.assertEqual(units[-1], 0)


class PercentComparisonTests(DashboardTestCase):
    def test_valid_percentages_use_real_previous_day_as_denominator(self):
        self.make_sale(self.yesterday, total='40.00')
        self.make_sale(self.yesterday, total='40.00')
        self.make_sale(self.today, total='30.00')
        self.make_sale(self.today, total='40.00')
        self.make_sale(self.today, total='30.00')

        html, stats = self.get_stats()
        self.assertEqual(stats['sales_today'], 3)
        self.assertEqual(stats['daily_revenue'], Decimal('100.00'))
        self.assert_delta(stats['sales_delta'], '+50%', 'vs. yesterday', 'kpi-delta-up')
        self.assert_delta(stats['revenue_delta'], '+25%', 'vs. yesterday', 'kpi-delta-up')
        self.assertIn('+50%', html)
        self.assertIn('+25%', html)
        self.assertIn('vs. yesterday', html)
        self.assertNotIn('no activity in either period', html)

    def test_flat_comparison_is_neutral_zero_percent(self):
        self.make_sale(self.yesterday, total='10.00')
        self.make_sale(self.today, total='10.00')

        html, stats = self.get_stats()
        self.assert_delta(stats['sales_delta'], '0%', 'vs. yesterday', '')
        self.assert_delta(stats['revenue_delta'], '0%', 'vs. yesterday', '')
        self.assertNotIn('kpi-delta-up', html)
        self.assertNotIn('kpi-delta-down', html)


class ReceivablesAndInventoryTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.person = Person.objects.create(name='Maria Souza', person_type='STUDENT')

        def make_receivable(amount, status):
            """Receivable reachable from a sale owned by the signed-in user."""
            sale = Sale.objects.create(
                responsible=self.user, status='COMPLETED', payment_method='ON_ACCOUNT',
            )
            return AccountReceivable.objects.create(
                person=self.person, sale=sale, original_amount=amount,
                due_date='2030-01-01', status=status,
            )

        make_receivable(Decimal('30.00'), 'PENDING')
        make_receivable(Decimal('20.00'), 'PARTIAL')
        make_receivable(Decimal('50.00'), 'OVERDUE')
        make_receivable(Decimal('99.00'), 'CANCELLED')
        Product.objects.create(
            name='Baixo', code='LOW1', category=self.category,
            price=Decimal('1.00'), stock_quantity=3, minimum_stock=5,
        )
        Product.objects.create(
            name='Zerado', code='OUT1', category=self.category,
            price=Decimal('1.00'), stock_quantity=0, minimum_stock=5,
        )
        Product.objects.create(
            name='Normal', code='NORM1', category=self.category,
            price=Decimal('1.00'), stock_quantity=10, minimum_stock=5,
        )
        Product.objects.create(
            name='Inativo', code='INACT1', category=self.category,
            price=Decimal('1.00'), stock_quantity=1, minimum_stock=5, active=False,
        )

    def test_open_receivables_are_counted_truthfully(self):
        html, stats = self.get_stats()
        self.assertEqual(stats['receivables_total'], Decimal('100.00'))
        self.assertEqual(stats['receivables_open_count'], 3)
        self.assertEqual(stats['overdue_total'], Decimal('50.00'))
        self.assertIn('3 open accounts', html)
        self.assertIn('Overdue', html)
        self.assertIn('R$ 50.00', html)
        self.assertNotIn('no open accounts', html)

    def test_low_inventory_counts_real_qualifying_products(self):
        html, stats = self.get_stats()
        self.assertEqual(stats['low_stock_count'], 2)
        self.assertEqual(stats['low_inventory_meta'], {'text': 'needs attention', 'warn': True})
        self.assertIn('needs attention', html)
        self.assertIn('kpi-sub-warn', html)
        self.assertIn('kpi-value">2</div>', html)

    def test_single_open_account_uses_singular_label(self):
        AccountReceivable.objects.filter(original_amount__in=[Decimal('20.00'), Decimal('50.00')]).delete()
        AccountReceivable.objects.filter(original_amount=Decimal('99.00')).delete()
        html, stats = self.get_stats()
        self.assertEqual(stats['receivables_open_count'], 1)
        self.assertIn('1 open account<', html)


class LowStockCountNotPreviewSliceTests(DashboardTestCase):
    def test_kpi_count_is_the_full_count_not_the_five_row_preview(self):
        for index in range(6):
            Product.objects.create(
                name=f'Baixo {index}', code=f'LOW{index}', category=self.category,
                price=Decimal('1.00'), stock_quantity=1, minimum_stock=5,
            )

        html, stats = self.get_stats()
        self.assertEqual(stats['low_stock_count'], 6)
        self.assertEqual(len(stats['low_stock_products']), 5)
        self.assertIn('kpi-value">6</div>', html)
