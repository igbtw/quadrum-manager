"""
Frontend views - only presentation logic, no business logic.
All data comes from mock_data.py
"""
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .mock_data import PRODUTOS, CATEGORIAS, PESSOAS, FORMAS_PAGAMENTO, \
    VENDAS, CONTAS_RECEBER, PAGAMENTOS_RECENTES, \
    get_dashboard_stats, get_produto_by_id, get_pessoa_by_id
from decimal import Decimal
import json


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'service': 'cantinaos'})


def dashboard(request):
    """Dashboard principal com resumo do dia"""
    stats = get_dashboard_stats()
    context = {
        'stats': stats,
        'page_title': 'Dashboard',
    }
    return render(request, 'frontend/dashboard.html', context)


def vendas_list(request):
    """Histórico de vendas"""
    context = {
        'vendas': VENDAS,
        'page_title': 'Vendas',
    }
    return render(request, 'frontend/vendas_list.html', context)


def pdv(request):
    """PDV / Nova Venda - tela mais importante"""
    context = {
        'produtos': PRODUTOS,
        'categorias': CATEGORIAS,
        'pessoas': [p for p in PESSOAS if p['status'] == 'ATIVO'],
        'formas_pagamento': FORMAS_PAGAMENTO,
        'page_title': 'Nova Venda',
    }
    return render(request, 'frontend/pdv.html', context)


def produtos(request):
    """Lista de produtos"""
    context = {
        'produtos': PRODUTOS,
        'categorias': CATEGORIAS,
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
    
    for p in PRODUTOS:
        if not p['ativo']:
            situacao = 'INATIVO'
        elif p['estoque'] == 0:
            situacao = 'SEM ESTOQUE'
            sem_estoque += 1
        elif p['estoque'] <= p['estoque_minimo']:
            situacao = 'BAIXO'
            baixo_estoque += 1
        else:
            situacao = 'NORMAL'
        
        if p['ativo']:
            total_itens += 1
            valor_total += p['preco'] * p['estoque']
        
        produtos_estoque.append({**p, 'situacao': situacao})
    
    context = {
        'produtos': produtos_estoque,
        'page_title': 'Estoque',
        'total_itens': total_itens,
        'valor_total': valor_total,
        'baixo_estoque': baixo_estoque,
        'sem_estoque': sem_estoque,
        'categorias': CATEGORIAS,
    }
    return render(request, 'frontend/estoque.html', context)


def pessoas(request):
    """Cadastro de pessoas"""
    context = {
        'pessoas': PESSOAS,
        'tipos': ['ALUNO', 'PROFESSOR', 'FUNCIONÁRIO', 'VISITANTE'],
        'page_title': 'Pessoas',
    }
    return render(request, 'frontend/pessoas.html', context)


def financeiro(request):
    """Financeiro - contas a receber"""
    total_receber = sum(c['valor'] for c in CONTAS_RECEBER if c['status'] == 'PENDENTE')
    total_vencido = sum(c['valor'] for c in CONTAS_RECEBER if c['status'] == 'VENCIDA')
    contas_pendentes = len([c for c in CONTAS_RECEBER if c['status'] == 'PENDENTE'])
    contas_vencidas = len([c for c in CONTAS_RECEBER if c['status'] == 'VENCIDA'])
    
    context = {
        'contas': CONTAS_RECEBER,
        'pagamentos': PAGAMENTOS_RECENTES,
        'total_receber': total_receber,
        'total_vencido': total_vencido,
        'contas_pendentes': contas_pendentes,
        'contas_vencidas': contas_vencidas,
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
    """Tela de login - apenas interface"""
    if request.method == 'POST':
        # Simular login bem-sucedido
        return redirect('dashboard')
    context = {
        'page_title': 'Login',
    }
    return render(request, 'frontend/login.html', context)


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
    """Finalizar venda (mock - não persiste)"""
    try:
        data = json.loads(request.body)
        # Simular sucesso
        return JsonResponse({
            'success': True,
            'codigo': f'VD{1000 + len(VENDAS) + 1}',
            'message': 'Venda finalizada com sucesso (simulação)'
        })
    except Exception:
        return JsonResponse({'error': 'Erro ao finalizar'}, status=400)