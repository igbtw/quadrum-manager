"""Frontend presentation views; data from DB."""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from .services import reduce_stock, create_sale_items, finalize_sale, cancel_sale
from .models import Product, Sale, SaleItem, AccountReceivable, StockMovement, Category, Person, Payment
from .forms import ProductForm, PersonForm


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'service': 'cantinaos'})


def dashboard(request):
    from django.db.models import Sum, Q, Count, F
    today = timezone.now().date()
    vendas_hoje = Sale.objects.filter(status='COMPLETED', created_at__date=today).count()
    faturamento = Sale.objects.filter(status='COMPLETED', created_at__date=today).aggregate(s=Sum('total'))['s'] or Decimal('0.00')
    valor_receber = AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).aggregate(s=Sum('original_amount'))['s'] or Decimal('0.00')
    # remaining balance computed via payments (simplified for dashboard)
    low_stock = Product.objects.filter(active=True, stock_quantity__lte=F('minimum_stock'), stock_quantity__gt=0).count()
    out_stock = Product.objects.filter(active=True, stock_quantity=0).count()
    # recent sales
    vendas_recentes = Sale.objects.filter(status__in=['COMPLETED','PENDING','CANCELLED']).select_related('customer')[:5]
    # inventory low
    produtos_baixo_estoque = Product.objects.filter(active=True, stock_quantity__lte=F('minimum_stock')).select_related('category')[:5]
    stats = {
        'vendas_dia': vendas_hoje,
        'faturamento_dia': faturamento,
        'valor_receber': valor_receber,
        'produtos_baixo_estoque': produtos_baixo_estoque,
        'vendas_recentes': vendas_recentes,
    }
    context = {
        'stats': stats,
        'page_title': 'Dashboard',
    }
    return render(request, 'frontend/dashboard.html', context)


def vendas_list(request):
    """Sales history"""
    context = {
        'vendas': Sale.objects.select_related('customer').order_by('-created_at')[:50],
        'page_title': 'Vendas',
    }
    return render(request, 'frontend/vendas_list.html', context)


@login_required
def pdv(request):
    """PDV / New Sale — main screen"""
    context = {
        'produtos': Product.objects.filter(active=True).select_related('category'),
        'categorias': Category.objects.filter(active=True),
        'pessoas': Person.objects.filter(active=True).order_by('name'),
        'formas_pagamento': ['DINHEIRO','DEBITO','CREDITO','PIX','A_PRAZO'],
        'page_title': 'Nova Venda',
    }
    return render(request, 'frontend/pdv.html', context)


def produtos(request):
    """Product list"""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto salvo.')
            return redirect('frontend:produtos')
        else:
            messages.error(request, 'Verifique os campos.')
    else:
        form = ProductForm()
    context = {
        'produtos': Product.objects.filter(active=True).select_related('category'),
        'categorias': Category.objects.filter(active=True),
        'form': form,
        'page_title': 'Produtos',
    }
    return render(request, 'frontend/produtos.html', context)


@login_required
def estoque(request):
    """Inventory control"""
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        qty = request.POST.get('qty')
        reason = request.POST.get('reason', '')
        try:
            qty = int(qty)
            if qty == 0:
                raise ValueError('Quantidade zero')
            prod = Product.objects.get(pk=product_id, active=True)
            from .services import adjust_stock
            adjust_stock(prod, qty, reason=reason, user=request.user if request.user.is_authenticated else None)
            messages.success(request, 'Estoque ajustado.')
        except Exception as e:
            messages.error(request, f'Erro no ajuste: {e}')
        return redirect('frontend:estoque')
    # Calculate each product inventory status
    produtos_estoque = []
    total_itens = 0
    valor_total = Decimal('0')
    baixo_estoque = 0
    sem_estoque = 0
    
    for p in Product.objects.filter(active=True):
        if p.stock_quantity == 0:
            situacao = 'SEM ESTOQUE'
            sem_estoque += 1
        elif p.stock_quantity <= p.minimum_stock:
            situacao = 'BAIXO'
            baixo_estoque += 1
        else:
            situacao = 'NORMAL'
        total_itens += 1
        valor_total += p.price * p.stock_quantity
        
        produtos_estoque.append({'nome': p.name, 'estoque': p.stock_quantity, 'estoque_minimo': p.minimum_stock, 'situacao': situacao, 'preco': p.price})
    
    context = {
        'produtos': produtos_estoque,
        'produtos_select': Product.objects.filter(active=True).select_related('category'),
        'page_title': 'Estoque',
        'total_itens': total_itens,
        'valor_total': valor_total,
        'baixo_estoque': baixo_estoque,
        'sem_estoque': sem_estoque,
    }
    return render(request, 'frontend/estoque.html', context)


def pessoas(request):
    """People registry"""
    if request.method == 'POST':
        form = PersonForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pessoa salva.')
            return redirect('frontend:pessoas')
        else:
            messages.error(request, 'Verifique os campos.')
    else:
        form = PersonForm()
    context = {
        'pessoas': Person.objects.filter(active=True).order_by('name'),
        'tipos': Person.PERSON_TYPES,
        'form': form,
        'page_title': 'Pessoas',
    }
    return render(request, 'frontend/pessoas.html', context)


@login_required
def financeiro(request):
    from django.db.models import Sum
    total_aberto = AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).aggregate(s=Sum('original_amount'))['s'] or Decimal('0.00')
    overdue = AccountReceivable.objects.filter(status='OVERDUE')
    total_vencido = sum(a.remaining_balance or Decimal('0.00') for a in overdue)
    if request.method == 'POST':
        from .forms import PaymentForm
        form = PaymentForm(request.POST)
        if form.is_valid():
            from .models import register_payment
            rc = form.cleaned_data['account_receivable']
            register_payment(rc, form.cleaned_data['amount'], method=form.cleaned_data['method'], user=request.user if request.user.is_authenticated else None, notes=form.cleaned_data['notes'])
            messages.success(request, 'Pagamento registrado.')
            return redirect('frontend:financeiro')
        else:
            messages.error(request, 'Verifique o pagamento.')
    else:
        from .forms import PaymentForm
        form = PaymentForm()
    context = {
        'contas': AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).select_related('person').order_by('-due_date')[:20],
        'pagamentos': Payment.objects.select_related('account_receivable__person').order_by('-created_at')[:20],
        'total_receber': total_aberto,
        'total_vencido': total_vencido,
        'contas_pendentes': AccountReceivable.objects.filter(status='PENDING').count(),
        'contas_vencidas': AccountReceivable.objects.filter(status='OVERDUE').count(),
        'form': form,
        'page_title': 'Financeiro',
    }
    return render(request, 'frontend/financeiro.html', context)


@login_required
def relatorios(request):
    from django.db.models import Sum, Count, Q, F
    from django.utils import timezone
    today = timezone.now().date()
    semana_antes = today - timezone.timedelta(days=7)
    vendas_periodo = Sale.objects.filter(status='COMPLETED', created_at__date__gte=semana_antes)
    total_vendas = vendas_periodo.aggregate(s=Sum('total'))['s'] or Decimal('0.00')
    count_vendas = vendas_periodo.count()
    # Best-selling by product via sale items
    best = SaleItem.objects.filter(sale__status='COMPLETED').values('product__name').annotate(q=Sum('quantity')).order_by('-q')[:5]
    # Low stock
    baixo = Product.objects.filter(active=True, stock_quantity__lte=F('minimum_stock')).count()
    # Receivables
    receb = AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).aggregate(s=Sum('original_amount'))['s'] or Decimal('0.00')
    contexto = {
        'page_title': 'Relatórios',
        'total_vendas_periodo': total_vendas,
        'count_vendas_periodo': count_vendas,
        'best_selling': best,
        'low_stock_count': baixo,
        'receivable_total': receb,
        'vendas_hoje': Sale.objects.filter(status='COMPLETED', created_at__date=today).count(),
    }
    return render(request, 'frontend/relatorios.html', contexto)


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('frontend:dashboard')
        else:
            return render(request, 'frontend/login.html', {
                'page_title': 'Login', 'error': 'Credenciais inválidas',
            })
    return render(request, 'frontend/login.html', {'page_title': 'Login'})

def logout_view(request):
    logout(request)
    return redirect('frontend:login')


# PDV interaction endpoints — persist to DB with integrity
@require_http_methods(["POST"])
def api_pdv_calcular(request):
    """Calculate total from cart data"""
    import json
    try:
        data = json.loads(request.body)
        itens = data.get('itens', [])
        total = Decimal('0')
        for item in itens:
            produto_id = item.get('produto_id')
            quantidade = item.get('quantidade', 1)
            try:
                produto = Product.objects.get(pk=produto_id, active=True)
            except Product.DoesNotExist:
                return JsonResponse({'error': f'Produto {produto_id} não encontrado'}, status=404)
            total += produto.price * Decimal(str(quantidade))
        return JsonResponse({'total': str(total)})
    except Exception as e:
        return JsonResponse({'error': f'Erro no cálculo: {str(e)}'}, status=400)


@require_http_methods(["POST"])
def api_pdv_finalizar(request):
    """Finalize sale — persist to DB with integrity"""
    import json
    try:
        data = json.loads(request.body)
        itens = data.get('itens', [])
        customer_id = data.get('cliente_id')
        payment_method = data.get('forma_pagamento', 'DINHEIRO')
        if not itens:
            return JsonResponse({'error': 'Carrinho vazio'}, status=400)
        from .models import Sale, Person
        customer = None
        if customer_id:
            try:
                customer = Person.objects.get(pk=customer_id, active=True)
            except Person.DoesNotExist:
                return JsonResponse({'error': 'Cliente não encontrado'}, status=404)
        sale = Sale.objects.create(
            customer=customer,
            responsible=request.user if request.user.is_authenticated else None,
            status='PENDING',
            payment_method=payment_method,
            subtotal=Decimal('0'),
            total=Decimal('0'),
        )
        items_data = [{'product_id': it['produto_id'], 'quantity': it['quantidade'], 'unit_price': it.get('preco_unitario', None)} for it in itens]
        create_sale_items(sale, items_data, user=request.user if request.user.is_authenticated else None)
        subtotal = sum(i.subtotal for i in sale.items.all())
        sale.subtotal = subtotal
        sale.total = subtotal
        sale.save(update_fields=['subtotal', 'total'])
        finalize_sale(sale, user=request.user if request.user.is_authenticated else None)
        return JsonResponse({'success': True, 'codigo': sale.code, 'message': 'Venda finalizada'})
    except Exception as e:
        return JsonResponse({'error': f'Erro ao finalizar: {str(e)}'}, status=400)