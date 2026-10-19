"""Frontend presentation views; data from DB."""
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import ProtectedError
from django.http import JsonResponse, HttpResponse, Http404
import logging
logger = logging.getLogger(__name__)
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from .services import (
    delete_person, delete_product, reduce_stock, create_sale_items,
    finalize_sale, cancel_sale, InsufficientStockError, ReferencedRecordError,
)
from .models import (
    AccountReceivable, Category, OnboardingProgress, Payment, PaymentConflictError,
    Person, Product, Sale, SaleItem, StockMovement, quantize_money, register_payment,
    remaining_after,
)
from .forms import ProductForm, PersonForm, LoginForm, RegisterForm
from .authorization import (
    can_manage_master_data, management_required,
    scoped_payments, scoped_receivables, scoped_sale_items, scoped_sales,
)
from .listsearch import (
    PAGE_SIZE_OPTIONS, RECEIVABLE_DEFAULT_SORT, RECEIVABLE_SORT_FIELDS,
    SALES_DEFAULT_SORT, SALES_SORT_FIELDS,
    build_querystring, normalize_q, paginate, parse_iso_date,
    resolve_page_size, sort_headers, sort_state,
)


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'service': 'quadrum'})


def _kpi_delta(current, previous, noun):
    """Percent change of a KPI vs. the previous day.

    Returns value/label/css-class for the KPI strip. Percentages are only
    computed when the comparison is valid: two empty periods are neutral,
    and a zero previous period never yields a division.
    """
    if previous == 0 and current == 0:
        return {'value': '—', 'label': 'no activity in either period', 'class': ''}
    if previous == 0:
        return {'value': 'New', 'label': f'no {noun} yesterday', 'class': 'kpi-delta-up'}
    previous = Decimal(previous)
    change = (Decimal(current) - previous) / previous * 100
    change = change.quantize(Decimal('0.1'))
    if change == 0:
        return {'value': '0%', 'label': 'vs. yesterday', 'class': ''}
    magnitude = f'{abs(change):.1f}'.rstrip('0').rstrip('.')
    sign = '+' if change > 0 else '-'
    return {
        'value': f'{sign}{magnitude}%',
        'label': 'vs. yesterday',
        'class': 'kpi-delta-up' if change > 0 else 'kpi-delta-down',
    }


@login_required
def dashboard(request):
    from django.db.models import Sum, Q, Count, F
    from django.db.models.functions import TruncDate
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    completed_today = scoped_sales(request.user).filter(status='COMPLETED', created_at__date=today)
    completed_yesterday = scoped_sales(request.user).filter(status='COMPLETED', created_at__date=yesterday)
    sales_today = completed_today.count()
    sales_yesterday = completed_yesterday.count()
    daily_revenue = quantize_money(completed_today.aggregate(s=Sum('total'))['s'])
    yesterday_revenue = quantize_money(completed_yesterday.aggregate(s=Sum('total'))['s'])
    # Derive the receivable KPI from the ledger, not from status labels: a
    # stale PAID row with an outstanding balance must remain visible here.
    receivable_accounts = list(
        scoped_receivables(request.user)
        .exclude(status='CANCELLED')
        .prefetch_related('payments')
    )
    receivables_total = quantize_money(sum(
        (account.remaining_balance for account in receivable_accounts),
        Decimal('0.00'),
    ))
    receivables_open_count = sum(
        1 for account in receivable_accounts
        if account.remaining_balance > Decimal('0.00')
    )
    overdue_accounts = scoped_receivables(request.user).filter(status='OVERDUE')
    overdue_total = quantize_money(sum(
        (a.remaining_balance for a in overdue_accounts), Decimal('0.00'),
    ))
    active_products = Product.objects.filter(active=True)
    active_products_count = active_products.count()
    low_stock_count = active_products.filter(stock_quantity__lte=F('minimum_stock')).count()
    if low_stock_count:
        low_inventory_meta = {'text': 'needs attention', 'warn': True}
    elif not active_products_count:
        low_inventory_meta = {'text': 'no products', 'warn': False}
    else:
        low_inventory_meta = {'text': 'Stock OK', 'warn': False}
    # recent sales
    recent_sales = scoped_sales(request.user).filter(status__in=['COMPLETED','PENDING','CANCELLED']).select_related('customer')[:5]
    # inventory low (preview rows; the KPI itself uses low_stock_count)
    low_stock_products = active_products.filter(stock_quantity__lte=F('minimum_stock')).select_related('category')[:5]
    # last 7 local days: units sold per day (completed sales only)
    week_start = today - timedelta(days=6)
    units_by_day = {
        row['day']: row['units']
        for row in (
            scoped_sale_items(request.user)
            .filter(sale__status='COMPLETED', sale__created_at__date__gte=week_start)
            .annotate(day=TruncDate('sale__created_at'))
            .values('day')
            .annotate(units=Sum('quantity'))
        )
    }
    chart_days = [week_start + timedelta(days=offset) for offset in range(7)]
    sales_chart = {
        'labels': [day.strftime('%a') for day in chart_days],
        'units': [units_by_day.get(day, 0) for day in chart_days],
    }
    stats = {
        'sales_today': sales_today,
        'daily_revenue': daily_revenue,
        'sales_delta': _kpi_delta(sales_today, sales_yesterday, 'sales'),
        'revenue_delta': _kpi_delta(daily_revenue, yesterday_revenue, 'revenue'),
        'receivables_total': receivables_total,
        'receivables_open_count': receivables_open_count,
        'overdue_total': overdue_total,
        'low_stock_count': low_stock_count,
        'low_inventory_meta': low_inventory_meta,
        'active_products_count': active_products_count,
        'low_stock_products': low_stock_products,
        'recent_sales': recent_sales,
        'sales_chart': sales_chart,
    }
    context = {
        'stats': stats,
        'page_title': 'Dashboard',
    }
    return render(request, 'frontend/dashboard.html', context)


@login_required
def sales_list(request):
    """Sales history with server-side search, filters, sorting, pagination."""
    from django.db.models import Count, Q
    query = normalize_q(request.GET.get('q'))
    status = request.GET.get('status') or ''
    if status not in {value for value, _ in Sale.SALE_STATUSES}:
        status = ''
    payment_method = request.GET.get('payment_method') or ''
    if payment_method not in {value for value, _ in Sale.PAYMENT_METHODS}:
        payment_method = ''
    date_from = parse_iso_date(request.GET.get('date_from'))
    date_to = parse_iso_date(request.GET.get('date_to'))

    sales_qs = scoped_sales(request.user).select_related('customer').annotate(items_count=Count('items'))
    if query:
        # Same identifiers the global palette's sale: prefix matches on.
        sales_qs = sales_qs.filter(Q(code__icontains=query) | Q(customer__name__icontains=query))
    if status:
        sales_qs = sales_qs.filter(status=status)
    if payment_method:
        sales_qs = sales_qs.filter(payment_method=payment_method)
    if date_from:
        sales_qs = sales_qs.filter(created_at__date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(created_at__date__lte=date_to)

    filters_active = bool(query or status or payment_method or date_from or date_to)
    sort, direction, order_by = sort_state(request, SALES_SORT_FIELDS, SALES_DEFAULT_SORT)
    sales_qs = sales_qs.order_by(*order_by)
    page_obj = paginate(request, sales_qs, resolve_page_size(request))

    context = {
        'sales': page_obj.object_list,
        'page_obj': page_obj,
        'query': query,
        'status': status,
        'payment_method': payment_method,
        'date_from': date_from.isoformat() if date_from else '',
        'date_to': date_to.isoformat() if date_to else '',
        'status_options': Sale.SALE_STATUSES,
        'payment_options': Sale.PAYMENT_METHODS,
        'filters_active': filters_active,
        'list_qs': build_querystring(request),
        'sort_headers': sort_headers(
            request, SALES_SORT_FIELDS, sort, direction,
            {'created_at': 'Date/Time', 'total': 'Total', 'code': 'Code'},
        ),
        'page_title': 'Sales',
    }
    return render(request, 'frontend/sales_list.html', context)


@login_required
def point_of_sale(request):
    """Point of Sale (POS) / New Sale — main screen"""
    context = {
        'products': Product.objects.filter(active=True).select_related('category'),
        'categories': Category.objects.filter(active=True),
        'people': Person.objects.filter(active=True).order_by('name'),
        'payment_methods': Sale.PAYMENT_METHODS,
        'page_title': 'New Sale',
    }
    return render(request, 'frontend/point_of_sale.html', context)


def _products_context(request, *, form=None, edit_form=None, edit_product=None):
    """Shared Products page context (list + filters + management forms).

    Reference counts for delete eligibility are unscoped: a product used in
    any sale item or stock movement anywhere must stay intact.
    """
    from django.db.models import Count, Q
    query = normalize_q(request.GET.get('q'))
    category_id = request.GET.get('category') or ''
    if category_id and not category_id.isdigit():
        category_id = ''
    # Active stays the default view; "Inactive"/"All" make the hidden records
    # reachable instead of advertising a filter that can never match.
    state = request.GET.get('state') or 'active'
    if state not in ('active', 'inactive', 'all'):
        state = 'active'

    products_qs = Product.objects.select_related('category')
    if state == 'active':
        products_qs = products_qs.filter(active=True)
    elif state == 'inactive':
        products_qs = products_qs.filter(active=False)
    if category_id:
        products_qs = products_qs.filter(category_id=category_id)
    if query:
        products_qs = products_qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
    products_qs = products_qs.order_by('name')
    page_obj = paginate(request, products_qs, resolve_page_size(request))
    products = list(page_obj.object_list)

    if products:
        ids = [p.pk for p in products]
        item_counts = dict(
            SaleItem.objects.filter(product_id__in=ids)
            .values_list('product_id').annotate(n=Count('id'))
        )
        movement_counts = dict(
            StockMovement.objects.filter(product_id__in=ids)
            .values_list('product_id').annotate(n=Count('id'))
        )
        for product in products:
            product.sale_items_count = item_counts.get(product.id, 0)
            product.movements_count = movement_counts.get(product.id, 0)
            product.can_delete = not (product.sale_items_count or product.movements_count)

    context = {
        'products': products,
        'page_obj': page_obj,
        'query': query,
        'category_id': category_id,
        'state': state,
        'state_options': (
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('all', 'All statuses'),
        ),
        'categories': Category.objects.filter(active=True),
        'all_categories': Category.objects.all(),
        'filters_active': bool(query or category_id or state != 'active'),
        'list_qs': build_querystring(request),
        'form': form or ProductForm(),
        'edit_form': edit_form,
        'edit_product': edit_product,
        'can_manage': can_manage_master_data(request.user),
        'page_title': 'Products',
    }
    return context


@login_required
def product_list(request):
    """Product catalog with search (name/code), category and state filters."""
    form = ProductForm()
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product saved.')
            return redirect('frontend:products')
        messages.error(request, 'Please check the fields.')
    return render(request, 'frontend/products.html', _products_context(request, form=form))


@management_required
@require_http_methods(['GET', 'POST'])
def product_edit(request, pk):
    """Edit one product. Invalid submissions re-render the catalog with the
    modal open and the bound form, preserving values and showing errors."""
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Product “{product.name}” updated.')
            return redirect('frontend:products')
        messages.error(request, 'Please check the fields.')
    else:
        form = ProductForm(instance=product)
    return render(
        request, 'frontend/products.html',
        _products_context(request, edit_form=form, edit_product=product),
    )


@management_required
@require_http_methods(['POST'])
def product_delete(request, pk):
    """Delete a product with no history; referenced products are deactivated."""
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    try:
        delete_product(product)
    except Product.DoesNotExist:
        messages.error(request, f'“{name}” no longer exists; it may have been deleted already.')
    except ReferencedRecordError as exc:
        refs = exc.references
        messages.error(
            request,
            f'Cannot delete “{name}”: {refs["sale_items"]} sale item(s) and '
            f'{refs["movements"]} stock movement(s) reference this product. '
            'Deactivate it instead so sales and inventory history stay intact.',
        )
    except ProtectedError:
        logger.exception('Protected delete refused for product pk=%s', pk)
        messages.error(request, f'Cannot delete “{name}” because protected records reference it.')
    else:
        messages.success(request, f'Product “{name}” deleted.')
    return redirect('frontend:products')


@login_required
def inventory(request):
    """Inventory control with search, status/category filters, and pagination."""
    from django.db.models import Count, F, Q, Sum
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        qty = request.POST.get('qty')
        reason = request.POST.get('reason', '')
        try:
            qty = int(qty)
            if qty == 0:
                raise ValueError('Quantity zero')
            prod = Product.objects.get(pk=product_id, active=True)
            from .services import adjust_stock
            adjust_stock(prod, qty, reason=reason, user=request.user if request.user.is_authenticated else None)
            messages.success(request, 'Inventory adjusted.')
        except Exception as e:
            messages.error(request, f'Adjustment error: {e}')
        return redirect('frontend:inventory')

    query = normalize_q(request.GET.get('q'))
    stock_status = request.GET.get('status') or ''
    status_values = ('NORMAL', 'LOW', 'OUT_OF_STOCK', 'INACTIVE')
    if stock_status not in status_values:
        stock_status = ''
    category_id = request.GET.get('category') or ''
    if category_id and not category_id.isdigit():
        category_id = ''

    products_qs = Product.objects.select_related('category')
    if query:
        products_qs = products_qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
    if category_id:
        products_qs = products_qs.filter(category_id=category_id)
    # Status conditions mirror the row computation below exactly, so a filter
    # option always matches the badge the same product will show.
    if stock_status == 'NORMAL':
        products_qs = products_qs.filter(active=True, stock_quantity__gt=F('minimum_stock'))
    elif stock_status == 'LOW':
        products_qs = products_qs.filter(
            active=True, stock_quantity__gt=0, stock_quantity__lte=F('minimum_stock'),
        )
    elif stock_status == 'OUT_OF_STOCK':
        products_qs = products_qs.filter(active=True, stock_quantity=0)
    elif stock_status == 'INACTIVE':
        products_qs = products_qs.filter(active=False)
    products_qs = products_qs.order_by('name')
    page_obj = paginate(request, products_qs, resolve_page_size(request))

    inventory_products = []
    for p in page_obj.object_list:
        if not p.active:
            row_status = 'INACTIVE'
        elif p.stock_quantity == 0:
            row_status = 'OUT_OF_STOCK'
        elif p.stock_quantity <= p.minimum_stock:
            row_status = 'LOW'
        else:
            row_status = 'NORMAL'
        inventory_products.append({
            'id': p.pk,
            'name': p.name,
            'category': p.category.name if p.category_id else '—',
            'category_id': p.category_id or '',
            'stock': p.stock_quantity,
            'minimum_stock': p.minimum_stock,
            'stock_status': row_status,
            'active': p.active,
            'price': p.price,
        })

    # Summary cards describe the whole catalog, not the filtered slice.
    totals = Product.objects.aggregate(
        total_items=Count('id', filter=Q(active=True)),
        total_value=Sum(F('price') * F('stock_quantity'), filter=Q(active=True)),
    )
    low_stock = Product.objects.filter(
        active=True, stock_quantity__gt=0, stock_quantity__lte=F('minimum_stock'),
    ).count()
    out_of_stock = Product.objects.filter(active=True, stock_quantity=0).count()

    context = {
        'products': inventory_products,
        'page_obj': page_obj,
        'query': query,
        'stock_status': stock_status,
        'category_id': category_id,
        'status_options': (
            ('NORMAL', 'Normal'),
            ('LOW', 'Low'),
            ('OUT_OF_STOCK', 'Out of Stock'),
            ('INACTIVE', 'Inactive'),
        ),
        'all_categories': Category.objects.all(),
        'filters_active': bool(query or stock_status or category_id),
        'list_qs': build_querystring(request),
        'product_options': Product.objects.filter(active=True).select_related('category'),
        'page_title': 'Inventory',
        'total_items': totals['total_items'] or 0,
        'total_value': totals['total_value'] or Decimal('0.00'),
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
    }
    return render(request, 'frontend/inventory.html', context)


def _people_context(request, *, form=None, edit_form=None, edit_person=None):
    """Shared People page context (list + filters + management forms).

    Reference counts for delete eligibility are deliberately unscoped: a
    person referenced by any user's sale or receivable must stay intact, so
    management integrity is evaluated against the whole database.
    """
    from django.db.models import Sum, Q, Count
    query = normalize_q(request.GET.get('q'))
    person_type = request.GET.get('type') or ''
    if person_type not in {value for value, _ in Person.PERSON_TYPES}:
        person_type = ''
    # Active stays the default view; "Inactive"/"All" expose the records the
    # old status selector promised but the queryset never loaded.
    state = request.GET.get('state') or 'active'
    if state not in ('active', 'inactive', 'all'):
        state = 'active'

    people_qs = Person.objects.all()
    if state == 'active':
        people_qs = people_qs.filter(active=True)
    elif state == 'inactive':
        people_qs = people_qs.filter(active=False)
    if person_type:
        people_qs = people_qs.filter(person_type=person_type)
    if query:
        # Same fields the global search palette matches on (name, record/doc).
        people_qs = people_qs.filter(Q(name__icontains=query) | Q(doc_id__icontains=query))
    people_qs = people_qs.order_by('name')
    page_obj = paginate(request, people_qs, resolve_page_size(request))
    people = list(page_obj.object_list)

    if people:
        ids = [p.pk for p in people]
        paid_by_account = {
            row['account_receivable_id']: row['total']
            for row in scoped_payments(request.user).filter(
                account_receivable_id__in=AccountReceivable.objects.filter(
                    person_id__in=ids,
                ).values('id'),
            ).values('account_receivable_id').annotate(total=Sum('amount'))
        }
        outstanding_by_person = {}
        open_accounts = scoped_receivables(request.user).filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            person_id__in=ids,
        ).only('id', 'person_id', 'original_amount')
        for account in open_accounts:
            outstanding = account.original_amount - (paid_by_account.get(account.id) or Decimal('0.00'))
            if outstanding > 0:
                outstanding_by_person[account.person_id] = (
                    outstanding_by_person.get(account.person_id, Decimal('0.00')) + outstanding
                )
        sales_counts = dict(
            Sale.objects.filter(customer_id__in=ids)
            .values_list('customer_id').annotate(n=Count('id'))
        )
        receivable_counts = dict(
            AccountReceivable.objects.filter(person_id__in=ids)
            .values_list('person_id').annotate(n=Count('id'))
        )
        for person in people:
            # Signed balance: negative = amount owed (matches the danger/credit styling in the template).
            person.balance = -outstanding_by_person.get(person.id, Decimal('0.00'))
            person.sales_count = sales_counts.get(person.id, 0)
            person.receivables_count = receivable_counts.get(person.id, 0)
            person.can_delete = not (person.sales_count or person.receivables_count)

    context = {
        'people': people,
        'page_obj': page_obj,
        'query': query,
        'person_type': person_type,
        'state': state,
        'person_types': Person.PERSON_TYPES,
        'state_options': (
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('all', 'All statuses'),
        ),
        'filters_active': bool(query or person_type or state != 'active'),
        'list_qs': build_querystring(request),
        'form': form or PersonForm(),
        'edit_form': edit_form,
        'edit_person': edit_person,
        'can_manage': can_manage_master_data(request.user),
        'page_title': 'People',
    }
    return context


@login_required
def people(request):
    """People registry with search (name/record), type and status filters."""
    form = PersonForm()
    if request.method == 'POST':
        form = PersonForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Person saved.')
            return redirect('frontend:people')
        messages.error(request, 'Please check the fields.')
    return render(request, 'frontend/people.html', _people_context(request, form=form))


@management_required
@require_http_methods(['GET', 'POST'])
def person_edit(request, pk):
    """Edit one person. Invalid submissions re-render the modal with the
    bound form so valid field values survive and errors stay visible."""
    person = get_object_or_404(Person, pk=pk)
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            messages.success(request, f'Person “{person.name}” updated.')
            return redirect('frontend:people')
        messages.error(request, 'Please check the fields.')
    else:
        form = PersonForm(instance=person)
    return render(
        request, 'frontend/people.html',
        _people_context(request, edit_form=form, edit_person=person),
    )


@management_required
@require_http_methods(['POST'])
def person_delete(request, pk):
    """Delete an unreferenced person; referenced people must be deactivated."""
    person = get_object_or_404(Person, pk=pk)
    name = person.name
    try:
        delete_person(person)
    except Person.DoesNotExist:
        messages.error(request, f'“{name}” no longer exists; it may have been deleted already.')
    except ReferencedRecordError as exc:
        refs = exc.references
        messages.error(
            request,
            f'Cannot delete “{name}”: {refs["sales"]} sale(s) and '
            f'{refs["receivables"]} receivable(s) reference this person. '
            'Deactivate them instead so history stays intact.',
        )
    except ProtectedError:
        logger.exception('Protected delete refused for person pk=%s', pk)
        messages.error(request, f'Cannot delete “{name}” because protected records reference them.')
    else:
        messages.success(request, f'Person “{name}” deleted.')
    return redirect('frontend:people')


@login_required
def finance(request):
    from django.db.models import Sum, Q
    receivable_accounts = list(
        scoped_receivables(request.user)
        .exclude(status='CANCELLED')
        .prefetch_related('payments')
    )
    total_receivable = quantize_money(sum(
        (account.remaining_balance for account in receivable_accounts),
        Decimal('0.00'),
    ))
    overdue_accounts = scoped_receivables(request.user).filter(status='OVERDUE')
    total_overdue = quantize_money(sum(
        (a.remaining_balance for a in overdue_accounts), Decimal('0.00'),
    ))
    if request.method == 'POST':
        from .forms import PaymentForm
        form = PaymentForm(request.POST, user=request.user)
        if form.is_valid():
            rc = form.cleaned_data['account_receivable']
            try:
                register_payment(
                    rc,
                    form.cleaned_data['amount'],
                    method=form.cleaned_data['method'],
                    user=request.user if request.user.is_authenticated else None,
                    notes=form.cleaned_data['notes'],
                    idempotency_key=form.cleaned_data['idempotency_key'],
                )
            except PaymentConflictError as exc:
                messages.error(request, str(exc))
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, 'Payment registered.')
                return redirect('frontend:finance')
        else:
            messages.error(request, 'Please verify the payment.')
    else:
        from .forms import PaymentForm
        form = PaymentForm(user=request.user)

    # ------------------------------------------------------------------
    # Receivables: independent search / filters / sorting / pagination.
    # ------------------------------------------------------------------
    receivable_status_values = {value for value, _ in AccountReceivable.RECEIVABLE_STATUSES}
    r_query = normalize_q(request.GET.get('rq'))
    r_status = request.GET.get('rstatus') or ''
    if r_status not in receivable_status_values:
        r_status = ''
    due_from = parse_iso_date(request.GET.get('due_from'))
    due_to = parse_iso_date(request.GET.get('due_to'))

    receivables_qs = scoped_receivables(request.user).select_related('person', 'sale')
    if r_status:
        # An explicit status (including PAID/CANCELLED) replaces the default
        # open-accounts view instead of intersecting with it.
        receivables_qs = receivables_qs.filter(status=r_status)
    else:
        receivables_qs = receivables_qs.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
    if r_query:
        receivables_qs = receivables_qs.filter(
            Q(person__name__icontains=r_query)
            | Q(sale__code__icontains=r_query)
            | Q(sale__notes__icontains=r_query)
        )
    if due_from:
        receivables_qs = receivables_qs.filter(due_date__gte=due_from)
    if due_to:
        receivables_qs = receivables_qs.filter(due_date__lte=due_to)
    r_filters_active = bool(r_query or r_status or due_from or due_to)
    r_sort, r_direction, r_order_by = sort_state(
        request, RECEIVABLE_SORT_FIELDS, RECEIVABLE_DEFAULT_SORT,
    )
    receivables_qs = receivables_qs.order_by(*r_order_by).distinct()
    receivables_page = paginate(
        request, receivables_qs, resolve_page_size(request), page_param='rpage',
    )
    receivables = list(receivables_page.object_list)
    for receivable in receivables:
        # Exact Python ledger sum: SQLite still returns float-derived Decimals
        # for SUM(amount) even on DecimalField.
        paid = receivable.amount_paid
        receivable.paid_display = paid
        receivable.remaining_display = remaining_after(
            receivable.original_amount, paid,
        )

    # ------------------------------------------------------------------
    # Payments: independent search / filters / pagination.
    # ------------------------------------------------------------------
    p_query = normalize_q(request.GET.get('pq'))
    payment_method = request.GET.get('pmethod') or ''
    if payment_method not in {value for value, _ in Payment.PAYMENT_METHODS}:
        payment_method = ''
    paid_from = parse_iso_date(request.GET.get('paid_from'))
    paid_to = parse_iso_date(request.GET.get('paid_to'))

    payments_qs = scoped_payments(request.user).select_related('account_receivable__person')
    if p_query:
        payments_qs = payments_qs.filter(
            Q(account_receivable__person__name__icontains=p_query)
            | Q(notes__icontains=p_query)
        )
    if payment_method:
        payments_qs = payments_qs.filter(method=payment_method)
    if paid_from:
        payments_qs = payments_qs.filter(payment_date__gte=paid_from)
    if paid_to:
        payments_qs = payments_qs.filter(payment_date__lte=paid_to)
    payments_qs = payments_qs.order_by('-created_at', '-id')

    p_filters_active = bool(p_query or payment_method or paid_from or paid_to)
    payments_page = paginate(
        request, payments_qs, resolve_page_size(request), page_param='ppage',
    )

    context = {
        'receivables': receivables,
        'receivables_page': receivables_page,
        'payments': payments_page.object_list,
        'payments_page': payments_page,
        'total_receivable': total_receivable,
        'total_overdue': total_overdue,
        'pending_accounts': scoped_receivables(request.user).filter(status='PENDING').count(),
        'overdue_accounts': scoped_receivables(request.user).filter(status='OVERDUE').count(),
        'r_query': r_query,
        'r_status': r_status,
        'due_from': due_from.isoformat() if due_from else '',
        'due_to': due_to.isoformat() if due_to else '',
        'receivable_status_options': AccountReceivable.RECEIVABLE_STATUSES,
        'r_filters_active': r_filters_active,
        'r_sort_headers': sort_headers(
            request, RECEIVABLE_SORT_FIELDS, r_sort, r_direction,
            {'due_date': 'Due Date', 'person': 'Person', 'amount': 'Amount'},
            only=('rq', 'rstatus', 'due_from', 'due_to'),
        ),
        'receivables_qs': build_querystring(
            request, only=('rq', 'rstatus', 'due_from', 'due_to', 'sort', 'dir'),
        ),
        'p_query': p_query,
        'payment_method': payment_method,
        'paid_from': paid_from.isoformat() if paid_from else '',
        'paid_to': paid_to.isoformat() if paid_to else '',
        'payment_method_options': Payment.PAYMENT_METHODS,
        'p_filters_active': p_filters_active,
        'payments_qs': build_querystring(request, only=('pq', 'pmethod', 'paid_from', 'paid_to')),
        'form': form,
        'page_title': 'Finance',
    }
    return render(request, 'frontend/finance.html', context)


@login_required
def reports(request):
    from . import reporting
    resolved = reporting.resolve_report(request)
    page_obj, sort, direction = reporting.transactions_page(
        request, resolved.filters, resolved,
    )
    context = {
        'page_title': 'Reports',
        'report': resolved,
        'form': resolved.form,
        'filter_chips': reporting.active_filter_chips(resolved),
        'summary': reporting.sales_summary(resolved.filters, resolved),
        'trend': reporting.sales_trend(resolved.filters, resolved),
        'payment_mix': reporting.payment_mix(resolved.filters, resolved),
        'products': reporting.product_performance(resolved.filters, resolved),
        'finance': reporting.financial_snapshot(resolved.filters, resolved),
        'page_obj': page_obj,
        'sort': sort,
        'direction': direction,
        'txn_headers': reporting.transaction_sort_links(resolved.filters, sort, direction),
        'params': reporting.canonical_params(resolved.filters, sort=sort, direction=direction),
    }
    return render(request, 'frontend/reports.html', context)


@login_required
def reports_export_csv(request):
    from . import reporting
    resolved = reporting.resolve_report(request)
    content, filename = reporting.transactions_csv(resolved.filters, resolved)
    response = HttpResponse(content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _safe_next_url(request):
    """Return the requested post-login destination only when it is safe."""
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return ''


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(_safe_next_url(request) or 'frontend:dashboard')
    return render(request, 'frontend/login.html', {
        'page_title': 'Login',
        'form': form,
        'next': _safe_next_url(request),
    })


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        OnboardingProgress.objects.create(user=user)
        messages.success(request, 'Account created. Sign in to continue.')
        return redirect('frontend:login')
    return render(request, 'frontend/register.html', {
        'page_title': 'Create account',
        'form': form,
    })

@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect('frontend:login')


def _onboarding_redirect(request):
    return redirect(_safe_next_url(request) or 'frontend:dashboard')


@login_required
@require_http_methods(["GET"])
def documentation(request):
    """Documentation index: topic cards, search, and the guide replay action."""
    from .search import doc_topics_by_group
    return render(request, 'frontend/documentation.html', {
        'page_title': 'Documentation',
        'doc_groups': doc_topics_by_group(),
    })


@login_required
@require_http_methods(["GET"])
def documentation_topic(request, topic_slug):
    """A single documentation topic page selected from the fixed registry."""
    from .search import DOC_TOPICS, find_doc_topic
    topic = find_doc_topic(topic_slug)
    if topic is None:
        raise Http404('Unknown documentation topic')
    index = DOC_TOPICS.index(topic)
    return render(request, topic['template'], {
        'page_title': f"{topic['title']} · Documentation",
        'topic': topic,
        'prev_topic': DOC_TOPICS[index - 1] if index > 0 else None,
        'next_topic': DOC_TOPICS[index + 1] if index < len(DOC_TOPICS) - 1 else None,
    })


@login_required
@require_http_methods(["POST"])
def onboarding_complete(request):
    progress, _ = OnboardingProgress.objects.get_or_create(user=request.user)
    progress.completed_at = timezone.now()
    progress.skipped_at = None
    progress.save(update_fields=['completed_at', 'skipped_at', 'updated_at'])
    return _onboarding_redirect(request)


@login_required
@require_http_methods(["POST"])
def onboarding_skip(request):
    progress, _ = OnboardingProgress.objects.get_or_create(user=request.user)
    progress.skipped_at = timezone.now()
    progress.save(update_fields=['skipped_at', 'updated_at'])
    return _onboarding_redirect(request)


@login_required
@require_http_methods(["POST"])
def onboarding_restart(request):
    progress, _ = OnboardingProgress.objects.get_or_create(user=request.user)
    progress.completed_at = None
    progress.skipped_at = None
    progress.current_step = 0
    progress.save(update_fields=['completed_at', 'skipped_at', 'current_step', 'updated_at'])
    return _onboarding_redirect(request)


# Keep in sync with the step sections in frontend/templates/frontend/partials/onboarding.html.
ONBOARDING_TOTAL_STEPS = 5


@login_required
@require_http_methods(["POST"])
def onboarding_step(request):
    """Persist the guide's current step for the signed-in user."""
    raw = request.POST.get('step')
    try:
        step = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'invalid step'}, status=400)
    if step < 0 or step >= ONBOARDING_TOTAL_STEPS:
        return JsonResponse({'error': 'invalid step'}, status=400)
    progress = OnboardingProgress.objects.filter(user=request.user).first()
    if progress is None or not progress.is_pending:
        return JsonResponse({'error': 'onboarding is not active'}, status=409)
    progress.current_step = step
    progress.save(update_fields=['current_step', 'updated_at'])
    return JsonResponse({'step': step})


@login_required
@require_http_methods(["POST"])
def preferences_per_page(request):
    """Persist the session-backed records-per-page preference."""
    raw = request.POST.get('per_page')
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'invalid per_page'}, status=400)
    if value not in PAGE_SIZE_OPTIONS:
        return JsonResponse({'error': 'invalid per_page'}, status=400)
    request.session['per_page'] = value
    return JsonResponse({'per_page': value})


@login_required
@require_http_methods(["GET"])
def api_search(request):
    """Small, permission-gated global search for the command palette.

    Unprefixed queries search every supported group (pages, documentation
    sections, products, people, sales). The advanced prefixes ``page:``,
    ``doc:``, ``product:``, ``person:`` and ``sale:`` restrict the search to
    one group; parsing lives in :mod:`frontend.search`.
    """
    from django.db.models import Q
    from django.urls import reverse
    from urllib.parse import urlencode

    from .search import (
        DOC_TOPICS, PAGE_REGISTRY, SEARCH_PROMPTS,
        parse_search_query, registry_matches,
    )

    query = ' '.join((request.GET.get('q') or '').split())[:100]
    prefix, term = parse_search_query(query)
    groups = []

    if prefix and not term:
        return JsonResponse({
            'query': query,
            'prefix': prefix,
            'prompt': SEARCH_PROMPTS.get(prefix, ''),
            'groups': [],
        })

    if len(term) >= 2:
        limit = 5

        if prefix in (None, 'pages'):
            items = [
                {
                    'title': entry['title'],
                    'subtitle': '',
                    'url': reverse(entry['url_name']),
                    'icon': entry['icon'],
                }
                for entry in registry_matches(PAGE_REGISTRY, term)
            ]
            if items:
                groups.append({'label': 'Pages', 'type': 'pages', 'items': items})

        if prefix in (None, 'docs'):
            items = [
                {
                    'title': entry['title'],
                    'subtitle': 'Documentation',
                    'url': reverse('frontend:documentation_topic', args=[entry['slug']]),
                    'icon': 'book-open',
                }
                for entry in registry_matches(DOC_TOPICS, term)
            ]
            if items:
                groups.append({'label': 'Documentation', 'type': 'docs', 'items': items})

        if prefix in (None, 'products'):
            products = (
                Product.objects.filter(active=True)
                .filter(Q(name__icontains=term) | Q(code__icontains=term))
                .select_related('category')
                .order_by('name')[:limit]
            )
            product_items = [
                {
                    'title': p.name,
                    'subtitle': ' · '.join(part for part in [
                        p.code,
                        p.category.name if p.category_id else '',
                        f'{p.stock_quantity} in stock',
                    ] if part),
                    # The Products list accepts ?q= for name/code, so a palette
                    # selection lands on the matching catalog row.
                    'url': reverse('frontend:products') + '?' + urlencode({'q': p.code or p.name}),
                    'icon': 'package',
                }
                for p in products
            ]
            if product_items:
                groups.append({'label': 'Products', 'type': 'products', 'items': product_items})

        if prefix in (None, 'people'):
            people = (
                Person.objects.filter(active=True)
                .filter(Q(name__icontains=term) | Q(doc_id__icontains=term))
                .order_by('name')[:limit]
            )
            person_items = [
                {
                    'title': p.name,
                    'subtitle': ' · '.join(part for part in [
                        p.get_person_type_display(),
                        p.doc_id,
                    ] if part),
                    # The People listing accepts ?q= and filters by the same
                    # fields, so a palette selection lands on matching records.
                    'url': reverse('frontend:people') + '?' + urlencode({'q': p.name}),
                    'icon': 'users',
                }
                for p in people
            ]
            if person_items:
                groups.append({'label': 'People', 'type': 'people', 'items': person_items})

        if prefix in (None, 'sales'):
            sales = (
                scoped_sales(request.user)
                .filter(Q(code__icontains=term) | Q(customer__name__icontains=term))
                .select_related('customer')
                .order_by('-created_at')[:limit]
            )
            sale_items = [
                {
                    'title': s.code,
                    'subtitle': ' · '.join(part for part in [
                        s.customer.name if s.customer_id else 'Walk-in',
                        f'R$ {s.total:.2f}',
                        s.get_status_display(),
                    ] if part),
                    # The Sales list accepts ?q= for code/customer, so a
                    # palette selection lands on that transaction.
                    'url': reverse('frontend:sales_list') + '?' + urlencode({'q': s.code}),
                    'icon': 'receipt',
                }
                for s in sales
            ]
            if sale_items:
                groups.append({'label': 'Sales', 'type': 'sales', 'items': sale_items})

    payload = {'query': query, 'groups': groups}
    if prefix:
        payload['prefix'] = prefix
    return JsonResponse(payload)


# POS interaction endpoints — persist to DB with integrity
def _validate_pos_items(items):
    """Validate POS line items for both calculation and finalization.

    Returns ``(normalized_items, error_message)``. On success ``error_message``
    is ``None`` and each normalized item has an ``int`` ``product_id`` and
    ``int`` ``quantity``, both strictly positive. ``bool`` is rejected even
    though it is a subclass of ``int``; floats (including whole values like
    ``2.0``), numeric strings, ``None``, and other types are rejected rather
    than coerced. A missing ``quantity`` is invalid.
    """
    if not isinstance(items, list):
        return None, 'Invalid items'
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            return None, 'Invalid item'
        product_id = item.get('product_id')
        if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
            return None, 'Invalid product_id'
        quantity = item.get('quantity')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            return None, 'Invalid quantity'
        normalized.append({'product_id': product_id, 'quantity': quantity})
    return normalized, None


@login_required
@require_http_methods(["POST"])
def api_pos_calculate(request):
    """Calculate total from cart data"""
    import json
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return JsonResponse({'error': 'Invalid request body'}, status=400)
        normalized_items, validation_error = _validate_pos_items(data.get('items', []))
        if validation_error is not None:
            return JsonResponse({'error': validation_error}, status=400)
        total = Decimal('0')
        for item in normalized_items:
            try:
                product = Product.objects.get(pk=item['product_id'], active=True)
            except Product.DoesNotExist:
                return JsonResponse({'error': f"Product {item['product_id']} not found"}, status=404)
            total += product.price * Decimal(item['quantity'])
        return JsonResponse({'total': str(total)})
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    except Exception:
        logger.exception("Unexpected error calculating POS total")
        return JsonResponse({'error': 'Calculation error'}, status=400)


@login_required
@require_http_methods(["POST"])
def api_pos_finalize(request):
    """Finalize sale — idempotent, atomic, DB-enforced."""
    import json, re
    from django.db import IntegrityError, transaction
    from .models import Sale, Person
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        customer_id = data.get('customer_id')
        payment_method = data.get('payment_method', 'CASH')
        idempotency_key = str(data.get('idempotency_key', '')).strip()
        if not items:
            return JsonResponse({'error': 'Empty cart'}, status=400)
        normalized_items, validation_error = _validate_pos_items(items)
        if validation_error is not None:
            return JsonResponse({'error': validation_error}, status=400)
        valid_payment_methods = {code for code, _ in Sale.PAYMENT_METHODS}
        if not isinstance(payment_method, str) or payment_method not in valid_payment_methods:
            return JsonResponse({'error': 'Invalid payment method'}, status=400)
        if not idempotency_key or len(idempotency_key) > 255 or not re.match(r'^[A-Za-z0-9_-]+$', idempotency_key):
            return JsonResponse({'error': 'Invalid idempotency key'}, status=400)
        import hashlib
        def _fingerprint():
            norm = {
                'items': sorted((i['product_id'], i['quantity']) for i in normalized_items),
                'customer_id': int(customer_id) if customer_id is not None else None,
                'payment_method': payment_method,
            }
            return hashlib.sha256(json.dumps(norm, sort_keys=True).encode()).hexdigest()
        fingerprint = _fingerprint()
        customer = None
        if customer_id:
            try:
                customer = Person.objects.get(pk=customer_id, active=True)
            except Person.DoesNotExist:
                return JsonResponse({'error': 'Customer not found'}, status=404)
        with transaction.atomic():
            # Single authoritative lookup by unique key
            try:
                existing = Sale.objects.select_related('customer').get(
                    idempotency_key=idempotency_key
                )
                # Ownership: same user only; legacy null-responsible treated as not matching
                if (existing.responsible_id or 0) != (request.user.id if request.user.is_authenticated else None):
                    return JsonResponse({'error': 'Idempotency key not authorized'}, status=403)
                if existing.status == 'COMPLETED':
                    if existing.request_fingerprint and existing.request_fingerprint != fingerprint:
                        return JsonResponse({'error': 'Key conflict: request data changed'}, status=409)
                    if not existing.request_fingerprint:
                        return JsonResponse({'error': 'Key conflict: existing sale without verification fingerprint'}, status=409)
                    return JsonResponse({
                        'success': True, 'code': existing.code,
                        'message': 'Sale completed'
                    })
                else:
                    return JsonResponse({'error': 'Checkout attempt already in progress or incomplete'}, status=409)
            except Sale.DoesNotExist:
                pass
            sale = Sale.objects.create(
                customer=customer,
                responsible=request.user if request.user.is_authenticated else None,
                status='PENDING',
                payment_method=payment_method,
                subtotal=Decimal('0'),
                total=Decimal('0'),
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
            create_sale_items(sale, normalized_items, user=request.user if request.user.is_authenticated else None)
            subtotal = sum(i.subtotal for i in sale.items.all())
            sale.subtotal = subtotal
            sale.total = subtotal
            sale.save(update_fields=['subtotal', 'total', 'request_fingerprint'])
            finalize_sale(sale, user=request.user if request.user.is_authenticated else None)
            return JsonResponse({'success': True, 'code': sale.code, 'message': 'Sale completed'})
    except IntegrityError:
        try:
            existing = Sale.objects.select_related('customer').get(
                idempotency_key=idempotency_key
            )
            if (existing.responsible_id or 0) != (request.user.id if request.user.is_authenticated else None):
                return JsonResponse({'error': 'Idempotency key not authorized'}, status=403)
            if existing.status == 'COMPLETED':
                if existing.request_fingerprint and existing.request_fingerprint != fingerprint:
                    return JsonResponse({'error': 'Key conflict: request data changed'}, status=409)
                if not existing.request_fingerprint:
                    return JsonResponse({'error': 'Key conflict: existing sale without verification fingerprint'}, status=409)
                return JsonResponse({
                    'success': True, 'code': existing.code,
                    'message': 'Sale completed'
                })
            else:
                return JsonResponse({'error': 'Checkout attempt already in progress or incomplete'}, status=409)
        except Sale.DoesNotExist:
            logger.exception("IntegrityError without idempotency record for key %s", idempotency_key)
            return JsonResponse({'error': 'Internal error finalizing sale'}, status=500)
    except InsufficientStockError:
        # Expected business conflict; the atomic block above has already
        # rolled back every checkout write before reaching this handler.
        return JsonResponse({'error': 'Insufficient stock'}, status=409)
    except Exception:
        logger.exception("Unexpected error finalizing sale")
        return JsonResponse({'error': 'Internal error finalizing sale'}, status=500)
