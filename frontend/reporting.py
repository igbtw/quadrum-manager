"""Operational reporting for the Reports page.

This module is the single source of truth for the Reports view, the CSV
export, and the tests. All numbers are derived from database queries.

Metric definitions
==================

Revenue (completed sales revenue)
    ``SUM(Sale.total)`` over sales with ``status='COMPLETED'`` whose
    ``created_at`` falls inside the selected local-time window.
    Pending (draft POS) and cancelled sales are never revenue.

Transactions
    Count of sales matching the active filters and the COMPLETED status
    requirement. The transaction table itself lists every status that
    passes the filters.

Average ticket
    Revenue / completed transactions, both from the same filtered window.
    Reported as unavailable (``None``) when there are no completed
    transactions; it is never fabricated from other figures.

Units sold
    ``SUM(SaleItem.quantity)`` of items belonging to completed sales in
    the window (item-level totals; see category semantics below).

Discounts granted
    ``SUM(Sale.discount)`` over the completed sales in the window. The
    POS flow leaves this at zero today; the field is summed verbatim
    instead of inventing a discount concept.

Cancelled sales
    Count and ``SUM(Sale.total)`` of sales with ``status='CANCELLED'`` in
    the window, kept visually separate from revenue. Cancellation restores
    stock through RETURN movements; the schema has no monetary refund
    model, so no refund figure is reported.

Previous-period comparison
    The comparison window is the immediately preceding window with the
    same number of local calendar days. Deltas follow the dashboard's
    honesty rules: two empty windows are neutral, a zero denominator
    never yields a division.

Category-filter semantics (transaction level vs item level)
===========================================================

The same category filter means different things at the two levels, and
the queries are kept apart so totals can never be double counted:

* Transaction-level totals (revenue, transaction count, discounts,
  cancellations, chart series, transaction table) are computed from
  ``Sale`` rows. The category filter is applied as a pk__in subquery on
  sale-item categories (``Sale.pk__in=SaleItem(...).values('sale_id')``),
  so each sale contributes its ``Sale.total`` exactly once no matter how
  many matching items it contains. No joined aggregation over sale items
  is ever performed on this queryset.
* Item-level totals (units, product rankings, category breakdowns,
  margin) are computed from ``SaleItem`` rows of completed sales and use
  ``product__category`` directly. Each item row is counted once; product
  revenue is ``SUM(SaleItem.subtotal)``, i.e. before any sale-level
  discount, and is labeled as such.

Trend buckets
=============
Spans of up to 31 days use daily buckets; longer spans use consecutive
7-day buckets anchored at each window's own start day. Windows are
day-for-day translations of one another (same length, same start
weekday), so the current and previous series always have the same bucket
count and partial edge buckets cover the same number of days. ISO
calendar weeks are deliberately not used because partial-week edges would
misalign between a window and its preceding window.

Margin estimate
===============
``Product.cost_price`` is the *current* recorded cost, not a snapshot
captured at sale time. The margin figure is therefore an estimate over
completed items whose product has a usable recorded cost; items without
recorded cost are excluded and their count and revenue are disclosed. It
is never labeled profit.

Receivables snapshot
====================
Outstanding balances, status counts, and aging are a *current snapshot*
(excluding PAID and CANCELLED accounts) and are intentionally not
period-filtered; they answer "what is owed right now". Payments received,
by contrast, are period-filtered on ``Payment.payment_date``. The two
concepts are displayed separately and never combined.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django import forms
from django.contrib.auth.models import User
from django.db.models import (
    Count, DecimalField, F, IntegerField, OuterRef, Q, Subquery, Sum, Value,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from .authorization import (
    has_global_access, scoped_payments, scoped_receivables, scoped_sale_items,
    scoped_sales,
)
from .listsearch import (
    SALES_DEFAULT_SORT, SALES_SORT_FIELDS,
    paginate, resolve_page_size, sort_state,
)
from .models import (
    AccountReceivable, Category, Payment, Sale, SaleItem, quantize_money,
)

COMPLETED = 'COMPLETED'
CANCELLED = 'CANCELLED'

PRESET_CHOICES = (
    ('today', 'Today'),
    ('yesterday', 'Yesterday'),
    ('7d', 'Last 7 days'),
    ('30d', 'Last 30 days'),
    ('month', 'This month'),
    ('custom', 'Custom range'),
)
DEFAULT_PRESET = '30d'
MAX_CUSTOM_SPAN_DAYS = 366
DAILY_BUCKET_MAX_SPAN_DAYS = 31
TOP_PRODUCT_LIMIT = 8
AGING_BUCKETS = (
    ('current', 'Not yet due'),
    ('1-30', '1–30 days overdue'),
    ('31-60', '31–60 days overdue'),
    ('61+', '61+ days overdue'),
)

TRANSACTION_SORT_FIELDS = dict(SALES_SORT_FIELDS)
TRANSACTION_SORT_LABELS = {
    'code': 'Code',
    'created_at': 'Date/Time',
    'total': 'Total',
}


class ReportFilterForm(forms.Form):
    """Validated report filters; invalid input is surfaced as form errors."""

    preset = forms.ChoiceField(
        choices=[('', '—')] + list(PRESET_CHOICES), required=False,
        widget=forms.Select(attrs={'class': 'select js-auto-submit', 'id': 'report-preset'}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'input js-report-date', 'id': 'report-date-from',
        }),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'input js-report-date', 'id': 'report-date-to',
        }),
    )
    status = forms.ChoiceField(
        choices=[('', 'All statuses')] + list(Sale.SALE_STATUSES), required=False,
        widget=forms.Select(attrs={'class': 'select js-auto-submit', 'id': 'report-status'}),
    )
    payment_method = forms.ChoiceField(
        choices=[('', 'All methods')] + list(Sale.PAYMENT_METHODS), required=False,
        widget=forms.Select(attrs={'class': 'select js-auto-submit', 'id': 'report-payment'}),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.order_by('name'), required=False,
        empty_label='All categories',
        widget=forms.Select(attrs={'class': 'select js-auto-submit', 'id': 'report-category'}),
    )
    responsible = forms.ModelChoiceField(
        queryset=User.objects.order_by('username'), required=False,
        empty_label='All responsibles',
        widget=forms.Select(attrs={'class': 'select js-auto-submit', 'id': 'report-responsible'}),
    )

    def __init__(self, *args, global_access=False, **kwargs):
        """Users without global access never get a responsible filter.

        Removing the field (instead of restricting its choices) means a
        forged ``responsible`` query parameter is silently ignored -- it can
        never broaden the report beyond the user's own sales.
        """
        super().__init__(*args, **kwargs)
        if not global_access:
            self.fields.pop('responsible', None)

    def clean(self):
        cleaned = super().clean()
        preset = cleaned.get('preset') or DEFAULT_PRESET
        date_from = cleaned.get('date_from')
        date_to = cleaned.get('date_to')
        if preset == 'custom':
            if not date_from or not date_to:
                raise forms.ValidationError('Choose both a start and an end date for a custom range.')
            if date_to < date_from:
                raise forms.ValidationError('The end date must not be before the start date.')
            if (date_to - date_from).days + 1 > MAX_CUSTOM_SPAN_DAYS:
                raise forms.ValidationError(
                    f'Custom ranges are limited to {MAX_CUSTOM_SPAN_DAYS} days.',
                )
        else:
            if date_from or date_to:
                raise forms.ValidationError(
                    'Choose "Custom range" to use start and end dates.',
                )
        cleaned['preset'] = preset
        return cleaned


@dataclass(frozen=True)
class ReportFilters:
    preset: str
    date_from: str
    date_to: str
    status: str = ''
    payment_method: str = ''
    category_id: int | None = None
    category_label: str = ''
    responsible_id: int | None = None
    responsible_label: str = ''


@dataclass(frozen=True)
class ResolvedReport:
    form: ReportFilterForm
    filters: ReportFilters
    start: date
    end: date
    prev_start: date
    prev_end: date
    span_days: int
    period_label: str
    preset_label: str
    user: object = None


def _aware_start(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time(0, 0)))


def _window(start: date, end: date):
    """Inclusive local days as an aware, half-open ``[start, end+1)`` window."""
    return _aware_start(start), _aware_start(end + timedelta(days=1))


def previous_window(start: date, end: date):
    """Equal-length window ending the day before ``start``."""
    span = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    return prev_end - timedelta(days=span - 1), prev_end


def resolve_report(request, today: date | None = None) -> ResolvedReport:
    """Validate GET filters and resolve the report window.

    Invalid input leaves the form carrying validation errors; the resolved
    window falls back to the default preset so the page still renders.
    """
    today = today or timezone.localdate()
    data = request.GET.copy()
    if not data.get('preset'):
        data['preset'] = DEFAULT_PRESET
    form = ReportFilterForm(data, global_access=has_global_access(request.user))
    form.is_valid()
    cleaned = form.cleaned_data

    preset = cleaned.get('preset') or DEFAULT_PRESET
    if preset not in dict(PRESET_CHOICES):
        preset = DEFAULT_PRESET
    date_from = cleaned.get('date_from')
    date_to = cleaned.get('date_to')
    if preset == 'custom':
        valid_custom = (
            isinstance(date_from, date) and isinstance(date_to, date)
            and date_from <= date_to
            and (date_to - date_from).days + 1 <= MAX_CUSTOM_SPAN_DAYS
        )
        if valid_custom:
            start, end = date_from, date_to
        else:
            preset = DEFAULT_PRESET

    if preset == 'today':
        start = end = today
    elif preset == 'yesterday':
        start = end = today - timedelta(days=1)
    elif preset == '7d':
        start, end = today - timedelta(days=6), today
    elif preset == '30d':
        start, end = today - timedelta(days=29), today
    elif preset == 'month':
        start, end = today.replace(day=1), today

    category = cleaned.get('category')
    responsible = cleaned.get('responsible')
    filters = ReportFilters(
        preset=preset,
        date_from=start.isoformat() if preset == 'custom' else '',
        date_to=end.isoformat() if preset == 'custom' else '',
        status=cleaned.get('status') or '',
        payment_method=cleaned.get('payment_method') or '',
        category_id=category.pk if category else None,
        category_label=category.name if category else '',
        responsible_id=responsible.pk if responsible else None,
        responsible_label=(
            (responsible.get_full_name() or responsible.username) if responsible else ''
        ),
    )
    prev_start, prev_end = previous_window(start, end)
    preset_label = dict(PRESET_CHOICES)[preset]
    if start == end:
        human = f'{start:%b %d, %Y}'
    else:
        human = f'{start:%b %d} – {end:%b %d, %Y}'
    return ResolvedReport(
        form=form,
        filters=filters,
        start=start,
        end=end,
        prev_start=prev_start,
        prev_end=prev_end,
        span_days=(end - start).days + 1,
        period_label=f'{preset_label} · {human}',
        preset_label=preset_label,
        user=request.user,
    )


def active_filter_chips(report: ResolvedReport):
    """Visible chip descriptors for the active non-preset filters."""
    chips = []
    if report.filters.status:
        label = dict(Sale.SALE_STATUSES).get(report.filters.status, report.filters.status)
        chips.append({'label': f'Status: {label}'})
    if report.filters.payment_method:
        label = dict(Sale.PAYMENT_METHODS).get(
            report.filters.payment_method, report.filters.payment_method,
        )
        chips.append({'label': f'Payment: {label}'})
    if report.filters.category_id:
        chips.append({'label': f'Category: {report.filters.category_label}'})
    if report.filters.responsible_id:
        chips.append({'label': f'Responsible: {report.filters.responsible_label}'})
    return chips


def canonical_params(filters: ReportFilters, sort: str = '', direction: str = '') -> str:
    """Canonical querystring for filter/sort links; drops everything else."""
    pairs = [('preset', filters.preset)]
    if filters.preset == 'custom':
        pairs += [('date_from', filters.date_from), ('date_to', filters.date_to)]
    if filters.status:
        pairs.append(('status', filters.status))
    if filters.payment_method:
        pairs.append(('payment_method', filters.payment_method))
    if filters.category_id:
        pairs.append(('category', str(filters.category_id)))
    if filters.responsible_id:
        pairs.append(('responsible', str(filters.responsible_id)))
    if sort:
        pairs.append(('sort', sort))
        pairs.append(('dir', direction))
    return urlencode(pairs)


def transaction_sort_links(filters: ReportFilters, sort: str, direction: str):
    """Header metadata for the transaction table (canonical URLs only)."""
    headers = {}
    for field, label in TRANSACTION_SORT_LABELS.items():
        active = field == sort
        if active:
            next_dir = 'asc' if direction == 'desc' else 'desc'
        else:
            next_dir = 'asc' if field == 'code' else 'desc'
        headers[field] = {
            'label': label,
            'url': '?' + canonical_params(filters, sort=field, direction=next_dir),
            'active': active,
            'aria_sort': ('ascending' if direction == 'asc' else 'descending') if active else 'none',
            'arrow': ('▲' if direction == 'asc' else '▼') if active else '',
        }
    return headers


def sales_scope(filters: ReportFilters, start: date, end: date, user):
    """Sale rows for the window, limited to what ``user`` may see.

    Transaction-level queryset. The category filter is an EXISTS-style
    pk__in subquery so joined sale items can never duplicate Sale totals.
    """
    gte, lt = _window(start, end)
    qs = scoped_sales(user).filter(created_at__gte=gte, created_at__lt=lt)
    if filters.status:
        qs = qs.filter(status=filters.status)
    if filters.payment_method:
        qs = qs.filter(payment_method=filters.payment_method)
    if filters.responsible_id:
        qs = qs.filter(responsible_id=filters.responsible_id)
    if filters.category_id:
        qs = qs.filter(
            pk__in=SaleItem.objects.filter(
                product__category_id=filters.category_id,
            ).values('sale_id'),
        )
    return qs


def item_scope(filters: ReportFilters, start: date, end: date, user):
    """Sale items of completed sales for the window (item-level totals).

    Limited to sales ``user`` may see. Each item row is counted exactly
    once; product/category revenue is ``SUM(subtotal)`` before any
    sale-level discount.
    """
    gte, lt = _window(start, end)
    qs = scoped_sale_items(user).filter(
        sale__created_at__gte=gte,
        sale__created_at__lt=lt,
        sale__status=COMPLETED,
    )
    if filters.status:
        qs = qs.filter(sale__status=filters.status)
    if filters.payment_method:
        qs = qs.filter(sale__payment_method=filters.payment_method)
    if filters.responsible_id:
        qs = qs.filter(sale__responsible_id=filters.responsible_id)
    if filters.category_id:
        qs = qs.filter(product__category_id=filters.category_id)
    return qs


def _delta(current, previous, span_days: int, noun: str):
    zero = Decimal('0.00')
    current = current or zero
    previous = previous or zero
    if current == 0 and previous == 0:
        return {'value': '—', 'label': 'no activity in either period', 'class': ''}
    if previous == 0:
        return {
            'value': 'New',
            'label': f'no {noun} in previous {span_days} day{"s" if span_days != 1 else ""}',
            'class': 'kpi-delta-up',
        }
    change = (Decimal(current) - Decimal(previous)) / Decimal(previous) * 100
    change = change.quantize(Decimal('0.1'))
    label = f'vs previous {span_days} day{"s" if span_days != 1 else ""}'
    if change == 0:
        return {'value': '0%', 'label': label, 'class': ''}
    magnitude = f'{abs(change):.1f}'.rstrip('0').rstrip('.')
    sign = '+' if change > 0 else '-'
    return {
        'value': f'{sign}{magnitude}%',
        'label': label,
        'class': 'kpi-delta-up' if change > 0 else 'kpi-delta-down',
    }


def sales_summary(filters: ReportFilters, report: ResolvedReport):
    """KPI strip data. See module docstring for every definition."""
    completed = sales_scope(filters, report.start, report.end, report.user).filter(status=COMPLETED)
    prev_completed = sales_scope(filters, report.prev_start, report.prev_end, report.user).filter(
        status=COMPLETED,
    )
    revenue = quantize_money(completed.aggregate(s=Sum('total'))['s'])
    transactions = completed.count()
    prev_revenue = quantize_money(prev_completed.aggregate(s=Sum('total'))['s'])
    prev_transactions = prev_completed.count()

    units = item_scope(filters, report.start, report.end, report.user).aggregate(
        s=Sum('quantity'),
    )['s'] or 0
    prev_units = item_scope(filters, report.prev_start, report.prev_end, report.user).aggregate(
        s=Sum('quantity'),
    )['s'] or 0

    avg_ticket = None
    if transactions:
        avg_ticket = (revenue / transactions).quantize(Decimal('0.01'))

    discounts = quantize_money(completed.aggregate(s=Sum('discount'))['s'])

    cancelled = sales_scope(filters, report.start, report.end, report.user).filter(
        status=CANCELLED,
    ).aggregate(count=Count('pk'), amount=Sum('total'))
    cancelled_count = cancelled['count'] or 0
    cancelled_amount = quantize_money(cancelled['amount'])

    status_rows = []
    total_rows = 0
    for value, label in Sale.SALE_STATUSES:
        row = sales_scope(filters, report.start, report.end, report.user).filter(
            status=value,
        ).aggregate(count=Count('pk'), amount=Sum('total'))
        count = row['count'] or 0
        amount = quantize_money(row['amount'])
        total_rows += count
        status_rows.append({
            'value': value, 'label': label, 'count': count, 'amount': amount,
        })

    return {
        'revenue': revenue,
        'transactions': transactions,
        'avg_ticket': avg_ticket,
        'units': units,
        'discounts': discounts,
        'cancelled_count': cancelled_count,
        'cancelled_amount': cancelled_amount,
        'revenue_delta': _delta(revenue, prev_revenue, report.span_days, 'revenue'),
        'transactions_delta': _delta(transactions, prev_transactions, report.span_days, 'sales'),
        'units_delta': _delta(units, prev_units, report.span_days, 'units'),
        'status_rows': status_rows,
        'total_rows': total_rows,
    }


def _bucket_days(start: date, end: date, granularity: str):
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    if granularity == 'day':
        return [[day] for day in days]
    return [days[offset:offset + 7] for offset in range(0, len(days), 7)]


def _bucket_label(days):
    if len(days) == 1:
        return f'{days[0]:%b %d}'
    if days[0].month == days[-1].month:
        return f'{days[0]:%b %d}–{days[-1]:%d}'
    return f'{days[0]:%b %d}–{days[-1]:%b %d}'


def _sum_days(bucket, day_values):
    return sum(day_values.get(day, 0) or 0 for day in bucket)


def sales_trend(filters: ReportFilters, report: ResolvedReport):
    """Zero-filled current/previous series with compatible buckets."""
    granularity = 'day' if report.span_days <= DAILY_BUCKET_MAX_SPAN_DAYS else 'week'
    overall_start = min(report.start, report.prev_start)

    sale_rows = (
        sales_scope(filters, overall_start, report.end, report.user)
        .filter(status=COMPLETED)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(revenue=Sum('total'), transactions=Count('pk'))
    )
    revenue_by_day = {}
    transactions_by_day = {}
    for row in sale_rows:
        revenue_by_day[row['day']] = quantize_money(row['revenue'])
        transactions_by_day[row['day']] = row['transactions'] or 0

    unit_rows = (
        item_scope(filters, overall_start, report.end, report.user)
        .annotate(day=TruncDate('sale__created_at'))
        .values('day')
        .annotate(units=Sum('quantity'))
    )
    units_by_day = {row['day']: row['units'] or 0 for row in unit_rows}

    current_buckets = _bucket_days(report.start, report.end, granularity)
    previous_buckets = _bucket_days(report.prev_start, report.prev_end, granularity)

    def series(buckets, day_values):
        return [_sum_days(bucket, day_values) for bucket in buckets]

    revenue = series(current_buckets, revenue_by_day)
    revenue_prev = series(previous_buckets, revenue_by_day)
    units = series(current_buckets, units_by_day)
    transactions = series(current_buckets, transactions_by_day)

    has_data = any(revenue) or any(units) or any(transactions)
    return {
        'granularity': granularity,
        'labels': [_bucket_label(days) for days in current_buckets],
        'prev_labels': [_bucket_label(days) for days in previous_buckets],
        'revenue': [float(value) for value in revenue],
        'revenue_prev': [float(value) for value in revenue_prev],
        'units': units,
        'transactions': transactions,
        'has_data': has_data,
        'bucket_count': len(current_buckets),
    }


def payment_mix(filters: ReportFilters, report: ResolvedReport):
    rows = (
        sales_scope(filters, report.start, report.end, report.user)
        .filter(status=COMPLETED)
        .values('payment_method')
        .annotate(revenue=Sum('total'), transactions=Count('pk'))
        .order_by('-revenue', 'payment_method')
    )
    labels = dict(Sale.PAYMENT_METHODS)
    total = quantize_money(sum(
        (row['revenue'] or Decimal('0.00') for row in rows), Decimal('0.00'),
    ))
    mix = []
    for row in rows:
        revenue = quantize_money(row['revenue'])
        mix.append({
            'value': row['payment_method'],
            'label': labels.get(row['payment_method'], row['payment_method']),
            'revenue': float(revenue),
            'revenue_display': revenue,
            'transactions': row['transactions'],
            'share_pct': (
                (revenue / total * 100).quantize(Decimal('0.1')) if total > 0 else None
            ),
        })
    return {'rows': mix, 'total': total, 'has_data': total > 0}


def product_performance(filters: ReportFilters, report: ResolvedReport):
    """Product and category rankings; every ordering is deterministic."""
    items = item_scope(filters, report.start, report.end, report.user)
    grouped = items.values(
        'product_id', 'product__name', 'product__code',
    ).annotate(
        units=Sum('quantity'),
        transactions=Count('sale_id', distinct=True),
        revenue=Sum('subtotal'),
    )
    total_revenue = quantize_money(items.aggregate(s=Sum('subtotal'))['s'])

    def rows(queryset):
        result = []
        for row in queryset:
            revenue = quantize_money(row['revenue'])
            result.append({
                'product_id': row['product_id'],
                'name': row['product__name'],
                'code': row['product__code'],
                'units': row['units'] or 0,
                'transactions': row['transactions'] or 0,
                'revenue': revenue,
                'share_pct': (
                    (revenue / total_revenue * 100).quantize(Decimal('0.1'))
                    if total_revenue > 0 else None
                ),
            })
        return result

    by_units = rows(
        grouped.order_by('-units', 'product__name', 'product_id')[:TOP_PRODUCT_LIMIT],
    )
    by_revenue = rows(
        grouped.order_by('-revenue', 'product__name', 'product_id')[:TOP_PRODUCT_LIMIT],
    )

    category_rows = []
    for row in items.values('product__category__name').annotate(
        units=Sum('quantity'),
        revenue=Sum('subtotal'),
        products=Count('product_id', distinct=True),
    ).order_by('-revenue', 'product__category__name'):
        revenue = quantize_money(row['revenue'])
        category_rows.append({
            'name': row['product__category__name'],
            'units': row['units'] or 0,
            'revenue': revenue,
            'products': row['products'],
            'share_pct': (
                (revenue / total_revenue * 100).quantize(Decimal('0.1'))
                if total_revenue > 0 else None
            ),
        })

    costed = items.filter(product__cost_price__isnull=False).exclude(
        product__cost_price=0,
    )
    costed_revenue = quantize_money(costed.aggregate(s=Sum('subtotal'))['s'])
    cost_basis = costed.aggregate(
        c=Sum(
            F('quantity') * F('product__cost_price'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )['c'] or Decimal('0.00')
    cost_basis = quantize_money(cost_basis)
    excluded = items.filter(
        Q(product__cost_price__isnull=True) | Q(product__cost_price=0),
    )
    excluded_lines = excluded.count()
    excluded_revenue = quantize_money(excluded.aggregate(s=Sum('subtotal'))['s'])

    margin = None
    margin_pct = None
    cost_available = costed_revenue > 0
    if cost_available:
        margin = quantize_money(costed_revenue - cost_basis)
        if costed_revenue > 0:
            margin_pct = (margin / costed_revenue * 100).quantize(Decimal('0.1'))

    return {
        'by_units': by_units,
        'by_revenue': by_revenue,
        'categories': category_rows,
        'total_item_revenue': total_revenue,
        'has_data': total_revenue > 0 or bool(by_units),
        'margin': {
            'available': cost_available,
            'revenue': costed_revenue,
            'cost': cost_basis,
            'margin': margin,
            'margin_pct': margin_pct,
            'excluded_lines': excluded_lines,
            'excluded_revenue': excluded_revenue,
        },
    }


def financial_snapshot(filters: ReportFilters, report: ResolvedReport):
    """Received-in-period (filtered) and receivables snapshot (current)."""
    received = scoped_payments(report.user).filter(
        payment_date__gte=report.start, payment_date__lte=report.end,
    )
    received_total = quantize_money(received.aggregate(s=Sum('amount'))['s'])
    received_count = received.count()
    payment_labels = dict(Payment.PAYMENT_METHODS)
    received_by_method = []
    for row in received.values('method').annotate(
        amount=Sum('amount'), count=Count('pk'),
    ).order_by('-amount', 'method'):
        received_by_method.append({
            'label': payment_labels.get(row['method'], row['method']),
            'amount': quantize_money(row['amount']),
            'count': row['count'],
        })

    # The snapshot is derived from the ledger, not the status label: a stale
    # PAID row that still has an outstanding balance must stay visible here.
    # Exact Python sums avoid SQLite's float-derived SUM(DecimalField).
    accounts = list(
        scoped_receivables(report.user)
        .exclude(status='CANCELLED')
        .prefetch_related('payments')
    )
    today = timezone.localdate()
    outstanding = Decimal('0.00')
    status_totals = {}
    aging_totals = {key: {'count': 0, 'balance': Decimal('0.00')} for key, _ in AGING_BUCKETS}
    overdue_balance = Decimal('0.00')
    overdue_count = 0
    open_count = 0
    for account in accounts:
        balance = account.remaining_balance
        if balance <= Decimal('0.00'):
            continue
        open_count += 1
        outstanding += balance
        entry = status_totals.setdefault(account.status, {'count': 0, 'balance': Decimal('0.00')})
        entry['count'] += 1
        entry['balance'] += balance
        if account.status == 'OVERDUE':
            overdue_count += 1
            overdue_balance += balance
        days_past_due = (today - account.due_date).days
        if days_past_due <= 0:
            key = 'current'
        elif days_past_due <= 30:
            key = '1-30'
        elif days_past_due <= 60:
            key = '31-60'
        else:
            key = '61+'
        aging_totals[key]['count'] += 1
        aging_totals[key]['balance'] += balance
    outstanding = quantize_money(outstanding)
    overdue_balance = quantize_money(overdue_balance)

    status_rows = []
    for value, label in AccountReceivable.RECEIVABLE_STATUSES:
        if value == 'CANCELLED':
            continue
        entry = status_totals.get(value, {'count': 0, 'balance': Decimal('0.00')})
        if value == 'PAID' and entry['count'] == 0:
            # Fully settled accounts are omitted; stale PAID rows with a
            # remaining balance are reported above instead of hidden.
            continue
        status_rows.append({
            'value': value, 'label': label, 'count': entry['count'], 'balance': entry['balance'],
        })

    aging_rows = [
        {'key': key, 'label': label, **aging_totals[key]} for key, label in AGING_BUCKETS
    ]
    return {
        'received_total': received_total,
        'received_count': received_count,
        'received_by_method': received_by_method,
        'outstanding_total': outstanding,
        'open_count': open_count,
        'overdue_total': overdue_balance,
        'overdue_count': overdue_count,
        'status_rows': status_rows,
        'aging_rows': aging_rows,
    }


def _transactions_queryset(filters: ReportFilters, report: ResolvedReport):
    units_subquery = (
        SaleItem.objects.filter(sale=OuterRef('pk'))
        .values('sale_id')
        .annotate(u=Sum('quantity'))
        .values('u')
    )
    return (
        sales_scope(filters, report.start, report.end, report.user)
        .select_related('customer', 'responsible')
        .annotate(
            items_count=Count('items', distinct=True),
            units=Coalesce(Subquery(units_subquery, output_field=IntegerField()), Value(0)),
        )
    )


def transactions_page(request, filters: ReportFilters, report: ResolvedReport):
    sort, direction, order_by = sort_state(
        request, TRANSACTION_SORT_FIELDS, SALES_DEFAULT_SORT,
    )
    queryset = _transactions_queryset(filters, report).order_by(*order_by)
    page_obj = paginate(request, queryset, resolve_page_size(request))
    return page_obj, sort, direction


def _csv_safe(value):
    text = '' if value is None else str(value)
    if text.startswith(('=', '+', '@')) or (
        text.startswith('-') and not text[1:].replace('.', '', 1).isdigit()
    ):
        return "'" + text
    return text


def transactions_csv(filters: ReportFilters, report: ResolvedReport):
    """CSV export of the filtered transaction set (same scope as the table)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'Code', 'Date/Time', 'Customer', 'Responsible', 'Items', 'Units',
        'Payment Method', 'Status', 'Discount (R$)', 'Total (R$)',
    ])
    queryset = _transactions_queryset(filters, report).order_by('created_at', 'pk')
    for sale in queryset.iterator():
        local_stamp = timezone.localtime(sale.created_at)
        responsible = sale.responsible
        writer.writerow([
            _csv_safe(sale.code),
            local_stamp.strftime('%Y-%m-%d %H:%M'),
            _csv_safe(sale.customer.name if sale.customer else 'Walk-in'),
            _csv_safe((responsible.get_full_name() or responsible.username) if responsible else '—'),
            sale.items_count,
            sale.units,
            _csv_safe(sale.get_payment_method_display()),
            _csv_safe(sale.get_status_display()),
            f'{sale.discount:.2f}',
            f'{sale.total:.2f}',
        ])
    filename = (
        f'quadrum-sales-report-{report.start:%Y%m%d}-{report.end:%Y%m%d}.csv'
    )
    return buffer.getvalue(), filename
