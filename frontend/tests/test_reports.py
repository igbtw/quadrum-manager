"""Tests for the Reports analytics module.

All fixtures use dynamically calculated local dates (never hardcoded
calendar dates) so they stay correct regardless of when the suite runs.
``Sale.created_at`` and ``Payment.payment_date`` are auto stamps; tests
backdate them through queryset ``.update()`` calls.
"""
import csv
import io
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from frontend.models import (
    AccountReceivable, Category, Payment, Person, Product, Sale, SaleItem,
)


def local(day, hour=12, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class ReportTestBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user('resp', password='pw')
        self.other = User.objects.create_user('other', password='pw')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat_a = Category.objects.create(name='Salgados')
        self.cat_b = Category.objects.create(name='Bebidas')
        self.p_a = Product.objects.create(
            name='Coxinha', code='A1', category=self.cat_a,
            price=Decimal('10.00'), cost_price=Decimal('4.00'), stock_quantity=100,
        )
        self.p_b = Product.objects.create(
            name='Refrigerante', code='B1', category=self.cat_b,
            price=Decimal('5.00'), cost_price=Decimal('2.00'), stock_quantity=100,
        )
        self.p_nocost = Product.objects.create(
            name='Sem Custo', code='C1', category=self.cat_b,
            price=Decimal('8.00'), cost_price=None, stock_quantity=100,
        )
        self.person = Person.objects.create(name='Cliente Aluno', person_type='STUDENT')

    def make_sale(self, when, status='COMPLETED', method='CASH', responsible=None,
                  customer=None, items=(), discount=Decimal('0.00')):
        subtotal = sum((product.price * quantity for product, quantity in items), Decimal('0.00'))
        sale = Sale.objects.create(
            customer=customer, responsible=responsible if responsible is not None else self.user,
            status=status, payment_method=method,
            subtotal=subtotal, discount=discount, total=subtotal - discount,
            completed_at=when if status == 'COMPLETED' else None,
        )
        for product, quantity in items:
            SaleItem.objects.create(
                sale=sale, product=product, quantity=quantity, unit_price=product.price,
            )
        Sale.objects.filter(pk=sale.pk).update(created_at=when)
        return sale

    def make_receivable(self, original, due_date, status='PENDING', sale=None):
        if sale is None:
            sale = Sale.objects.create(
                responsible=self.user, status='COMPLETED', payment_method='ON_ACCOUNT',
                subtotal=original, total=original,
            )
        return AccountReceivable.objects.create(
            person=self.person, sale=sale, original_amount=original,
            due_date=due_date, status=status,
        )

    def add_payment(self, receivable, amount, payment_date, method='CASH'):
        payment = Payment.objects.create(
            account_receivable=receivable, amount=amount, method=method,
        )
        Payment.objects.filter(pk=payment.pk).update(
            payment_date=payment_date, created_at=local(payment_date),
        )
        return payment

    def get_report(self, **params):
        response = self.client.get(reverse('frontend:reports'), params)
        self.assertEqual(response.status_code, 200)
        return response


class EmptyDatasetTests(ReportTestBase):
    def test_empty_report_renders_neutral_summary(self):
        response = self.get_report()
        summary = response.context['summary']
        self.assertEqual(summary['revenue'], Decimal('0.00'))
        self.assertEqual(summary['transactions'], 0)
        self.assertIsNone(summary['avg_ticket'])
        self.assertEqual(summary['units'], 0)
        self.assertEqual(summary['discounts'], Decimal('0.00'))
        self.assertEqual(summary['cancelled_count'], 0)
        self.assertEqual(summary['revenue_delta']['value'], '—')
        self.assertEqual(summary['transactions_delta']['label'], 'no activity in either period')
        self.assertEqual(summary['total_rows'], 0)
        trend = response.context['trend']
        self.assertFalse(trend['has_data'])
        self.assertFalse(response.context['products']['has_data'])
        self.assertFalse(response.context['products']['margin']['available'])
        self.assertFalse(response.context['payment_mix']['has_data'])
        finance = response.context['finance']
        self.assertEqual(finance['outstanding_total'], Decimal('0.00'))
        self.assertEqual(finance['received_total'], Decimal('0.00'))
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        html = response.content.decode()
        self.assertIn('No completed sales', html)
        self.assertIn('No transactions match these filters', html)

    def test_empty_csv_is_valid_with_headers_only(self):
        response = self.client.get(reverse('frontend:reports_export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="quadrum-sales-report-', response['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'Code')


class SalesSummaryTests(ReportTestBase):
    def test_presets_scope_the_window(self):
        self.make_sale(local(self.today, 10), items=[(self.p_a, 1)])
        self.make_sale(local(self.today - timedelta(days=1), 10), items=[(self.p_a, 1)])
        self.make_sale(local(self.today - timedelta(days=3), 10), items=[(self.p_a, 1)])
        self.make_sale(local(self.today - timedelta(days=10), 10), items=[(self.p_a, 1)])
        self.make_sale(local(self.today - timedelta(days=40), 10), items=[(self.p_a, 1)])

        self.assertEqual(self.get_report(preset='today').context['summary']['transactions'], 1)
        self.assertEqual(self.get_report(preset='yesterday').context['summary']['transactions'], 1)
        self.assertEqual(self.get_report(preset='7d').context['summary']['transactions'], 3)
        self.assertEqual(self.get_report(preset='30d').context['summary']['transactions'], 4)
        month_expected = 0
        for offset in (0, 1, 3, 10, 40):
            day = self.today - timedelta(days=offset)
            if day >= self.today.replace(day=1):
                month_expected += 1
        self.assertEqual(
            self.get_report(preset='month').context['summary']['transactions'], month_expected,
        )

    def test_average_ticket_uses_completed_only(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 2)], discount=Decimal('5.00'))
        self.make_sale(local(self.today, 10), items=[(self.p_a, 1)])
        self.make_sale(local(self.today, 11), items=[(self.p_a, 5)], status='CANCELLED')
        self.make_sale(local(self.today, 12), status='PENDING')

        summary = self.get_report(preset='today').context['summary']
        self.assertEqual(summary['revenue'], Decimal('25.00'))
        self.assertEqual(summary['transactions'], 2)
        self.assertEqual(summary['avg_ticket'], Decimal('12.50'))
        self.assertEqual(summary['units'], 3)
        self.assertEqual(summary['discounts'], Decimal('5.00'))

    def test_cancelled_and_pending_are_separate_from_revenue(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 1)])
        cancelled = self.make_sale(
            local(self.today, 10), items=[(self.p_a, 2)], status='CANCELLED',
        )
        self.make_sale(local(self.today, 11), status='PENDING')

        summary = self.get_report(preset='today').context['summary']
        self.assertEqual(summary['revenue'], Decimal('10.00'))
        self.assertEqual(summary['units'], 1)
        self.assertEqual(summary['cancelled_count'], 1)
        self.assertEqual(summary['cancelled_amount'], cancelled.total)
        rows = {row['value']: row for row in summary['status_rows']}
        self.assertEqual(rows['COMPLETED']['count'], 1)
        self.assertEqual(rows['CANCELLED']['count'], 1)
        self.assertEqual(rows['PENDING']['count'], 1)

    def test_status_filter_scopes_everything_consistently(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 1)])
        self.make_sale(local(self.today, 10), items=[(self.p_a, 2)], status='CANCELLED')

        response = self.get_report(preset='today', status='CANCELLED')
        summary = response.context['summary']
        self.assertEqual(summary['revenue'], Decimal('0.00'))
        self.assertEqual(summary['transactions'], 0)
        self.assertEqual(summary['units'], 0)
        self.assertEqual(summary['cancelled_count'], 1)
        rows = {row['value']: row for row in summary['status_rows']}
        self.assertEqual(rows['COMPLETED']['count'], 0)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertIn('Cancelled', response.content.decode())

    def test_delta_is_new_when_previous_period_is_empty(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 1)])
        summary = self.get_report(preset='today').context['summary']
        self.assertEqual(summary['revenue_delta']['value'], 'New')
        self.assertEqual(summary['revenue_delta']['class'], 'kpi-delta-up')
        self.assertIn('no revenue in previous 1 day', summary['revenue_delta']['label'])

    def test_delta_computes_change_with_matching_windows(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 2)])
        self.make_sale(local(self.today - timedelta(days=1), 9), items=[(self.p_a, 1)])
        summary = self.get_report(preset='today').context['summary']
        self.assertEqual(summary['revenue_delta']['value'], '+100%')
        self.assertEqual(summary['revenue_delta']['class'], 'kpi-delta-up')


class TimezoneBoundaryTests(ReportTestBase):
    def test_late_evening_yesterday_counts_as_yesterday(self):
        self.make_sale(local(self.today - timedelta(days=1), 23, 30), items=[(self.p_a, 1)])
        self.assertEqual(
            self.get_report(preset='yesterday').context['summary']['transactions'], 1,
        )
        self.assertEqual(self.get_report(preset='today').context['summary']['transactions'], 0)

    def test_early_morning_today_counts_as_today(self):
        self.make_sale(local(self.today, 0, 10), items=[(self.p_a, 1)])
        self.assertEqual(self.get_report(preset='today').context['summary']['transactions'], 1)
        self.assertEqual(
            self.get_report(preset='yesterday').context['summary']['transactions'], 0,
        )

    def test_custom_range_uses_inclusive_local_days(self):
        self.make_sale(local(self.today - timedelta(days=5), 23, 45), items=[(self.p_a, 1)])
        start = (self.today - timedelta(days=5)).isoformat()
        end = (self.today - timedelta(days=5)).isoformat()
        response = self.get_report(preset='custom', date_from=start, date_to=end)
        self.assertEqual(response.context['summary']['transactions'], 1)


class ChartTrendTests(ReportTestBase):
    def test_daily_buckets_are_zero_filled(self):
        self.make_sale(local(self.today, 10), items=[(self.p_a, 2)])
        trend = self.get_report(preset='7d').context['trend']
        self.assertEqual(trend['granularity'], 'day')
        self.assertEqual(len(trend['labels']), 7)
        self.assertEqual(len(trend['prev_labels']), 7)
        self.assertEqual(trend['units'][:-1], [0, 0, 0, 0, 0, 0])
        self.assertEqual(trend['units'][-1], 2)
        self.assertEqual(trend['transactions'][-1], 1)
        self.assertTrue(trend['has_data'])

    def test_default_buckets_use_daily_for_30_days(self):
        trend = self.get_report(preset='30d').context['trend']
        self.assertEqual(trend['granularity'], 'day')
        self.assertEqual(len(trend['labels']), 30)

    def test_weekly_buckets_are_compatible_between_periods(self):
        for offset in (0, 3, 6, 8, 15, 22, 33, 39):
            self.make_sale(
                local(self.today - timedelta(days=offset), 10), items=[(self.p_a, 1)],
            )
        start = (self.today - timedelta(days=39)).isoformat()
        end = self.today.isoformat()
        response = self.get_report(preset='custom', date_from=start, date_to=end)
        trend = response.context['trend']
        summary = response.context['summary']
        self.assertEqual(trend['granularity'], 'week')
        self.assertEqual(trend['bucket_count'], 6)
        self.assertEqual(len(trend['labels']), len(trend['prev_labels']))
        self.assertEqual(sum(trend['units']), summary['units'])
        self.assertEqual(sum(trend['transactions']), summary['transactions'])
        self.assertAlmostEqual(sum(trend['revenue']), float(summary['revenue']), places=2)

    def test_partial_final_week_bucket_includes_last_day(self):
        self.make_sale(local(self.today, 10), items=[(self.p_a, 3)])
        start = (self.today - timedelta(days=39)).isoformat()
        end = self.today.isoformat()
        trend = self.get_report(preset='custom', date_from=start, date_to=end).context['trend']
        self.assertEqual(trend['units'][-1], 3)
        self.assertEqual(sum(trend['units'][:-1]), 0)

    def test_previous_series_uses_previous_window(self):
        self.make_sale(local(self.today - timedelta(days=8), 10), items=[(self.p_a, 4)])
        trend = self.get_report(preset='7d').context['trend']
        self.assertEqual(sum(trend['units']), 0)
        self.assertEqual(sum(trend['revenue_prev']), float(Decimal('40.00')))
        self.assertFalse(trend['has_data'])


class FilterTests(ReportTestBase):
    def test_payment_method_filter(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 1)], method='PIX')
        self.make_sale(local(self.today, 10), items=[(self.p_a, 1)], method='CASH')
        response = self.get_report(preset='today', payment_method='PIX')
        self.assertEqual(response.context['summary']['transactions'], 1)
        self.assertEqual(response.context['summary']['revenue'], Decimal('10.00'))

    def test_responsible_param_cannot_broaden_an_ordinary_users_view(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 1)], responsible=self.other)
        mine = self.make_sale(local(self.today, 10), items=[(self.p_a, 1)], responsible=self.user)
        unassigned = self.make_sale(local(self.today, 11), items=[(self.p_a, 1)])
        Sale.objects.filter(pk=unassigned.pk).update(responsible=None)

        response = self.get_report(preset='today', responsible=self.other.pk)
        self.assertEqual(response.context['summary']['transactions'], 1)
        self.assertEqual(
            [sale.code for sale in response.context['page_obj'].object_list], [mine.code],
        )
        self.assertIsNone(response.context['report'].filters.responsible_id)
        self.assertNotIn('report-responsible', response.content.decode())

    def test_category_filter_never_duplicates_sale_totals(self):
        mixed = self.make_sale(
            local(self.today, 9), items=[(self.p_a, 1), (self.p_b, 2)],
        )
        self.assertEqual(mixed.total, Decimal('20.00'))
        self.make_sale(local(self.today, 10), items=[(self.p_a, 1)])
        self.make_sale(local(self.today, 11), items=[(self.p_b, 3)])

        response = self.get_report(preset='today', category=self.cat_a.pk)
        summary = response.context['summary']
        self.assertEqual(summary['revenue'], Decimal('30.00'))
        self.assertEqual(summary['transactions'], 2)
        self.assertEqual(summary['units'], 2)

        products = response.context['products']
        names = [row['name'] for row in products['by_units']]
        self.assertEqual(names, ['Coxinha'])
        self.assertEqual(products['by_units'][0]['units'], 2)
        self.assertEqual(products['total_item_revenue'], Decimal('20.00'))

        categories = response.context['products']['categories']
        self.assertEqual([row['name'] for row in categories], ['Salgados'])

    def test_custom_range_validation_rejects_reversed_dates(self):
        from frontend.reporting import resolve_report
        start = (self.today - timedelta(days=2)).isoformat()
        end = (self.today - timedelta(days=5)).isoformat()
        response = self.get_report(preset='custom', date_from=start, date_to=end)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.context['report'].filters.preset, '30d')
        request = response.wsgi_request
        resolved = resolve_report(request)
        self.assertEqual(resolved.start, self.today - timedelta(days=29))

    def test_custom_range_validation_rejects_excessive_span(self):
        start = (self.today - timedelta(days=400)).isoformat()
        end = self.today.isoformat()
        response = self.get_report(preset='custom', date_from=start, date_to=end)
        self.assertIn('limited to 366 days', response.content.decode())
        self.assertEqual(response.context['report'].filters.preset, '30d')

    def test_custom_range_requires_both_dates(self):
        response = self.get_report(
            preset='custom', date_from=(self.today - timedelta(days=5)).isoformat(),
        )
        self.assertTrue(response.context['form'].errors)

    def test_dates_without_custom_preset_are_rejected(self):
        response = self.get_report(
            preset='30d', date_from=(self.today - timedelta(days=5)).isoformat(),
        )
        self.assertTrue(response.context['form'].errors)
        self.assertIn('Custom range', response.content.decode())

    def test_unknown_category_is_a_form_error_not_a_crash(self):
        response = self.get_report(preset='today', category='999999')
        self.assertTrue(response.context['form'].errors)
        self.assertIsNone(response.context['report'].filters.category_id)

    def test_malformed_date_is_a_form_error(self):
        response = self.get_report(preset='custom', date_from='not-a-date', date_to='also-bad')
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.context['report'].filters.preset, '30d')

    def test_filter_chips_show_active_filters(self):
        response = self.get_report(preset='today', status='COMPLETED', payment_method='PIX')
        labels = [chip['label'] for chip in response.context['filter_chips']]
        self.assertIn('Status: Completed', labels)
        self.assertIn('Payment: PIX', labels)


class ProductRankingTests(ReportTestBase):
    def test_rankings_use_distinct_metrics(self):
        expensive = Product.objects.create(
            name='Bolo Caro', code='D1', category=self.cat_a,
            price=Decimal('30.00'), cost_price=Decimal('10.00'), stock_quantity=50,
        )
        self.make_sale(local(self.today, 9), items=[(self.p_a, 2)])
        self.make_sale(local(self.today, 10), items=[(expensive, 1)])

        products = self.get_report(preset='today').context['products']
        self.assertEqual(products['by_units'][0]['name'], 'Coxinha')
        self.assertEqual(products['by_units'][0]['units'], 2)
        self.assertEqual(products['by_revenue'][0]['name'], 'Bolo Caro')
        self.assertEqual(products['by_revenue'][0]['revenue'], Decimal('30.00'))
        self.assertEqual(products['by_units'][0]['transactions'], 1)

    def test_ties_break_deterministically_by_name(self):
        first = Product.objects.create(
            name='AAA', code='E1', category=self.cat_a,
            price=Decimal('5.00'), stock_quantity=10,
        )
        second = Product.objects.create(
            name='ZZZ', code='E2', category=self.cat_a,
            price=Decimal('5.00'), stock_quantity=10,
        )
        self.make_sale(local(self.today, 9), items=[(first, 1), (second, 1)])
        products = self.get_report(preset='today').context['products']
        self.assertEqual(
            [row['name'] for row in products['by_units']], ['AAA', 'ZZZ'],
        )
        self.assertEqual(
            [row['name'] for row in products['by_revenue']], ['AAA', 'ZZZ'],
        )

    def test_share_percentage_uses_total_item_revenue(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 3), (self.p_b, 2)])
        products = self.get_report(preset='today').context['products']
        rows = {row['name']: row for row in products['by_revenue']}
        self.assertEqual(products['total_item_revenue'], Decimal('40.00'))
        self.assertEqual(rows['Coxinha']['share_pct'], Decimal('75.0'))
        self.assertEqual(rows['Refrigerante']['share_pct'], Decimal('25.0'))

    def test_category_breakdown_totals(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 3), (self.p_b, 2)])
        categories = self.get_report(preset='today').context['products']['categories']
        rows = {row['name']: row for row in categories}
        self.assertEqual(rows['Salgados']['revenue'], Decimal('30.00'))
        self.assertEqual(rows['Salgados']['units'], 3)
        self.assertEqual(rows['Bebidas']['revenue'], Decimal('10.00'))
        self.assertEqual(rows['Salgados']['share_pct'], Decimal('75.0'))


class MarginEstimateTests(ReportTestBase):
    def test_margin_uses_recorded_cost_and_excludes_missing_cost(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 2), (self.p_nocost, 1)])
        margin = self.get_report(preset='today').context['products']['margin']
        self.assertTrue(margin['available'])
        self.assertEqual(margin['revenue'], Decimal('20.00'))
        self.assertEqual(margin['cost'], Decimal('8.00'))
        self.assertEqual(margin['margin'], Decimal('12.00'))
        self.assertEqual(margin['margin_pct'], Decimal('60.0'))
        self.assertEqual(margin['excluded_lines'], 1)
        self.assertEqual(margin['excluded_revenue'], Decimal('8.00'))

    def test_margin_unavailable_without_recorded_cost(self):
        self.make_sale(local(self.today, 9), items=[(self.p_nocost, 1)])
        margin = self.get_report(preset='today').context['products']['margin']
        self.assertFalse(margin['available'])
        self.assertIsNone(margin['margin'])


class FinancialTests(ReportTestBase):
    def test_received_in_period_counts_actual_payments(self):
        receivable = self.make_receivable(Decimal('100.00'), self.today + timedelta(days=10))
        self.add_payment(receivable, Decimal('40.00'), self.today, method='PIX')
        self.add_payment(
            receivable, Decimal('10.00'), self.today - timedelta(days=45), method='CASH',
        )
        finance = self.get_report(preset='30d').context['finance']
        self.assertEqual(finance['received_total'], Decimal('40.00'))
        self.assertEqual(finance['received_count'], 1)
        methods = [row['label'] for row in finance['received_by_method']]
        self.assertEqual(methods, ['PIX'])

    def test_outstanding_uses_remaining_balance(self):
        receivable = self.make_receivable(Decimal('100.00'), self.today + timedelta(days=5))
        self.add_payment(receivable, Decimal('40.00'), self.today, method='CASH')
        receivable.refresh_from_db()
        self.assertEqual(receivable.status, 'PARTIAL')
        finance = self.get_report(preset='today').context['finance']
        self.assertEqual(finance['outstanding_total'], Decimal('60.00'))
        self.assertEqual(finance['open_count'], 1)
        rows = {row['value']: row for row in finance['status_rows']}
        self.assertEqual(rows['PARTIAL']['count'], 1)
        self.assertEqual(rows['PARTIAL']['balance'], Decimal('60.00'))

    def test_overdue_and_aging_buckets(self):
        recently_overdue = self.make_receivable(
            Decimal('50.00'), self.today - timedelta(days=10),
        )
        recently_overdue.status = 'OVERDUE'
        recently_overdue.save(update_fields=['status'])
        long_overdue = self.make_receivable(
            Decimal('25.00'), self.today - timedelta(days=70),
        )
        long_overdue.status = 'OVERDUE'
        long_overdue.save(update_fields=['status'])
        self.make_receivable(Decimal('30.00'), self.today + timedelta(days=7))
        paid = self.make_receivable(Decimal('99.00'), self.today + timedelta(days=7), status='PAID')
        cancelled = self.make_receivable(
            Decimal('88.00'), self.today + timedelta(days=7), status='CANCELLED',
        )

        finance = self.get_report(preset='today').context['finance']
        # The PAID row above has no payments, so its balance is real money:
        # the snapshot must keep it visible instead of trusting the label.
        self.assertEqual(finance['outstanding_total'], Decimal('204.00'))
        self.assertEqual(finance['open_count'], 4)
        self.assertEqual(finance['overdue_count'], 2)
        self.assertEqual(finance['overdue_total'], Decimal('75.00'))
        aging = {row['key']: row for row in finance['aging_rows']}
        self.assertEqual(aging['current']['count'], 2)
        self.assertEqual(aging['current']['balance'], Decimal('129.00'))
        self.assertEqual(aging['1-30']['count'], 1)
        self.assertEqual(aging['1-30']['balance'], Decimal('50.00'))
        self.assertEqual(aging['31-60']['count'], 0)
        self.assertEqual(aging['61+']['count'], 1)
        self.assertEqual(aging['61+']['balance'], Decimal('25.00'))
        rows = {row['value']: row for row in finance['status_rows']}
        self.assertEqual(rows['PAID']['balance'], Decimal('99.00'))
        self.assertNotIn('CANCELLED', [row['value'] for row in finance['status_rows']])
        self.assertIsNotNone(paid.pk)
        self.assertIsNotNone(cancelled.pk)

    def test_fully_paid_account_leaves_no_outstanding(self):
        receivable = self.make_receivable(Decimal('80.00'), self.today + timedelta(days=5))
        self.add_payment(receivable, Decimal('80.00'), self.today)
        receivable.refresh_from_db()
        self.assertEqual(receivable.status, 'PAID')
        finance = self.get_report(preset='today').context['finance']
        self.assertEqual(finance['outstanding_total'], Decimal('0.00'))
        self.assertEqual(finance['open_count'], 0)

    def test_revenue_and_received_are_tracked_separately(self):
        sale = self.make_sale(local(self.today, 9), items=[(self.p_a, 2)], method='ON_ACCOUNT')
        receivable = self.make_receivable(
            Decimal('20.00'), self.today + timedelta(days=5), sale=sale,
        )
        self.add_payment(receivable, Decimal('20.00'), self.today)
        summary = self.get_report(preset='today').context['summary']
        finance = self.get_report(preset='today').context['finance']
        self.assertEqual(summary['revenue'], Decimal('20.00'))
        self.assertEqual(finance['received_total'], Decimal('20.00'))
        self.assertEqual(finance['outstanding_total'], Decimal('0.00'))


class TransactionTableTests(ReportTestBase):
    def test_pagination_preserves_active_filters(self):
        for index in range(25):
            self.make_sale(local(self.today, 9, index % 60), items=[(self.p_a, 1)])
        response = self.get_report(preset='today', status='COMPLETED', sort='total', dir='asc')
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 25)
        self.assertEqual(page_obj.paginator.num_pages, 2)
        html = response.content.decode()
        self.assertIn('page=2', html)
        self.assertIn('preset=today', html)
        self.assertIn('status=COMPLETED', html)
        self.assertIn('sort=total', html)

    def test_sort_links_are_canonical_and_drop_invalid_values(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 1)])
        response = self.get_report(preset='30d', date_from='garbage')
        html = response.content.decode()
        self.assertIn('?preset=30d&amp;sort=code&amp;dir=asc', html)
        self.assertNotIn('date_from=garbage', response.context['params'])

    def test_missing_customer_and_responsible_render_gracefully(self):
        sale = self.make_sale(local(self.today, 9), items=[(self.p_a, 1)])
        Sale.objects.filter(pk=sale.pk).update(responsible=None)
        admin = User.objects.create_superuser('report-admin', password='pw')
        self.client.force_login(admin)
        response = self.get_report(preset='today')
        html = response.content.decode()
        self.assertIn('Walk-in', html)

    def test_pending_sale_has_zero_items_and_units(self):
        self.make_sale(local(self.today, 9), status='PENDING')
        response = self.get_report(preset='today')
        sale = response.context['page_obj'].object_list[0]
        self.assertEqual(sale.items_count, 0)
        self.assertEqual(sale.units, 0)


class CsvExportTests(ReportTestBase):
    def test_csv_respects_filters_and_matches_table_scope(self):
        completed = self.make_sale(local(self.today, 9), items=[(self.p_a, 2)])
        cancelled = self.make_sale(local(self.today, 10), items=[(self.p_b, 1)], status='CANCELLED')

        response = self.client.get(
            reverse('frontend:reports_export'), {'preset': 'today', 'status': 'COMPLETED'},
        )
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], [
            'Code', 'Date/Time', 'Customer', 'Responsible', 'Items', 'Units',
            'Payment Method', 'Status', 'Discount (R$)', 'Total (R$)',
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], completed.code)
        self.assertNotIn(cancelled.code, [row[0] for row in rows])
        self.assertEqual(rows[1][4], '1')
        self.assertEqual(rows[1][5], '2')
        self.assertEqual(rows[1][9], '20.00')

    def test_csv_ignores_page_param_and_uses_full_filtered_set(self):
        for index in range(25):
            self.make_sale(local(self.today, 9, index % 60), items=[(self.p_a, 1)])
        response = self.client.get(
            reverse('frontend:reports_export'), {'preset': 'today', 'page': '2'},
        )
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows) - 1, 25)

    def test_report_and_export_require_login(self):
        anonymous = Client()
        for name in ('reports', 'reports_export'):
            response = anonymous.get(reverse(f'frontend:{name}'))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response['Location'])


class ChartExpandTests(ReportTestBase):
    CANVAS_LABELS = (
        ('revenueChart', 'Expand Revenue chart'),
        ('volumeChart', 'Expand Volume chart'),
        ('paymentMixChart', 'Expand Payment Mix chart'),
    )

    def test_every_chart_card_has_an_expand_control(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 2)], method='CASH')
        response = self.get_report(preset='today')
        html = response.content.decode()
        for canvas_id, label in self.CANVAS_LABELS:
            self.assertIn(f'data-chart-expand="{canvas_id}"', html, msg=canvas_id)
            self.assertIn(f'aria-label="{label}"', html, msg=canvas_id)
            self.assertIn(f'id="{canvas_id}"', html, msg=canvas_id)
        self.assertIn('aria-haspopup="dialog"', html)
        self.assertIn('title="Expand chart"', html)

    def test_expanded_chart_dialog_is_present_and_accessibly_labelled(self):
        self.make_sale(local(self.today, 9), items=[(self.p_a, 2)], method='CASH')
        html = self.get_report(preset='today').content.decode()
        self.assertIn('id="chartExpandDialog"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('aria-labelledby="chartExpandTitle"', html)
        self.assertIn('id="chartExpandBody"', html)
        self.assertIn('id="chartExpandCloseBtn"', html)

    def test_empty_dataset_renders_no_expand_controls(self):
        html = self.get_report().content.decode()
        self.assertNotIn('data-chart-expand', html)
        self.assertIn('id="chartExpandDialog"', html)


class ChartExpandStaticTests(TestCase):
    """Source-level checks: the expanded chart view is CSS/JS only, so its
    geometry and wiring are verified statically (a real browser is not
    available in tests)."""

    def test_dialog_geometry_is_large_and_bounded(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'components.css').read_text()
        self.assertIn('.chart-expand-panel', css)
        self.assertIn('width: min(92vw', css)
        self.assertIn('height: min(90vh', css)
        self.assertIn('.chart-expand-body .chart-area', css)
        self.assertIn('.chart-area-placeholder', css)

    def test_expand_behavior_reuses_the_single_chart_instance(self):
        js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js').read_text()
        self.assertIn('function initChartExpand()', js)
        self.assertIn('chartExpandState', js)
        self.assertIn("canvas.closest('.chart-area')", js)
        self.assertIn('Chart.getChart(canvas)', js)
        self.assertIn('chart.resize()', js)
        self.assertNotIn('new Chart(', js)
