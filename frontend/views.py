"""
Frontend views - only presentation logic, no business logic.
All data comes from mock_data.py
"""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from .services import reduce_stock, create_sale_items, finalize_sale
from .models import Product, Sale, SaleItem, AccountReceivable, StockMovement, Category, Person


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
    """Histórico de vendas"""
    context = {
        'vendas': Sale.objects.select_related('customer').order_by('-created_at')[:50],
        'page_title': 'Vendas',
    }
    return render(request, 'frontend/vendas_list.html', context)


def pdv(request):
    """PDV / Nova Venda - tela mais importante"""
    context = {
        'produtos': Product.objects.filter(active=True).select_related('category'),
        'categorias': Category.objects.filter(active=True),
        'pessoas': Person.objects.filter(active=True).order_by('name'),
        'formas_pagamento': ['DINHEIRO','DEBITO','CREDITO','PIX','A_PRAZO'],
        'page_title': 'Nova Venda',
    }
    return render(request, 'frontend/pdv.html', context)


def produtos(request):
    """Lista de produtos"""
    context = {
        'produtos': Product.objects.filter(active=True).select_related('category'),
        'categorias': Category.objects.filter(active=True),
        'page_title': 'Produtos',
    }
    return render(request, 'frontend/produtos.html', context)


def estoque(request):
    """Controle de estoque"""
    # Calcular situação de cada produto
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
        'page_title': 'Estoque',
        'total_itens': total_itens,
        'valor_total': valor_total,
        'baixo_estoque': baixo_estoque,
        'sem_estoque': sem_estoque,
    }
    return render(request, 'frontend/estoque.html', context)


def pessoas(request):
    """Cadastro de pessoas"""
    context = {
        'pessoas': Person.objects.filter(active=True).order_by('name'),
        'tipos': ['ALUNO', 'PROFESSOR', 'FUNCIONARIO', 'VISITANTE'],
        'page_title': 'Pessoas',
    }
    return render(request, 'frontend/pessoas.html', context)


def financeiro(request):
    from django.db.models import Sum
    total_aberto = AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).aggregate(s=Sum('original_amount'))['s'] or Decimal('0.00')
    overdue = AccountReceivable.objects.filter(status='OVERDUE')
    total_vencido = sum(a.remaining_balance or Decimal('0.00') for a in overdue)
    context = {
        'contas': AccountReceivable.objects.filter(status__in=['PENDING','PARTIAL','OVERDUE']).select_related('person').order_by('-due_date')[:20],
        'pagamentos': [],
        'total_receber': total_aberto,
        'total_vencido': total_vencido,
        'contas_pendentes': AccountReceivable.objects.filter(status='PENDING').count(),
        'contas_vencidas': AccountReceivable.objects.filter(status='OVERDUE').count(),
        'page_title': 'Financeiro',
    }
    return render(request, 'frontend/financeiro.html', context)


def relatorios(request):
    """Relatórios - apenas interface"""
    context = {
        'page_title': 'Relatórios',
    }
    return render(request, 'frontend/relatorios.html', context)


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


# API endpoints para interações do PDV (apenas para demonstração frontend)
@require_http_methods(["POST"])
def api_pdv_calcular(request):
    """Calcular total do carrinho (mock)"""
    try:
        data = json.loads(request.body)
        itens = data.get('itens', [])
        total = Decimal('0')
        for item in itens:
            produto = get_produto_by_id(item['produto_id'])
            if produto:
                total += produto['preco'] * item['quantidade']
        return JsonResponse({'total': str(total)})
    except Exception:
        return JsonResponse({'error': 'Erro no cálculo'}, status=400)


@require_http_methods(["POST"])
def api_pdv_finalizar(request):
    """Finalizar venda — persistir no DB com integridade."""
    from django.utils import timezone
    try:
        data = json.loads(request.body)
        itens = data.get('itens', [])
        customer_id = data.get('cliente_id')
        payment_method = data.get('forma_pagamento', 'DINHEIRO')
        # Create sale draft
        from .models import Sale, Person
        customer = None
        if customer_id:
            try:
                customer = Person.objects.get(pk=customer_id)
            except Person.DoesNotExist:
                pass
        sale = Sale.objects.create(
            customer=customer,
            responsible=request.user if request.user.is_authenticated else None,
            status='PENDING',
            payment_method=payment_method,
            subtotal=Decimal('0'),
            total=Decimal('0'),
        )
        # Build items from cart and finalize
        items_data = [{'product_id': it['produto_id'], 'quantity': it['quantidade'], 'unit_price': it.get('preco_unitario')} for it in itens]
        create_sale_items(sale, items_data, user=request.user if request.user.is_authenticated else None)
        # Recalculate totals from items
        subtotal = sum(i.subtotal for i in sale.items.all())
        sale.subtotal = subtotal
        sale.total = subtotal   # no discount for simplicity
        sale.save(update_fields=['subtotal', 'total'])
        finalize_sale(sale, user=request.user if request.user.is_authenticated else None)
        return JsonResponse({'success': True, 'codigo': sale.code, 'message': 'Venda finalizada'})
    except Exception as e:
        return JsonResponse({'error': f'Erro ao finalizar: {str(e)}'}, status=400)