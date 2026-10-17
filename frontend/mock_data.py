"""
Mock data for frontend demonstration.
Centralized mock data to make it easy to replace with real models later.
"""

from decimal import Decimal
from datetime import datetime, timedelta
import random

# Categories
CATEGORIAS = [
    {'id': 1, 'nome': 'Beverages', 'icone': 'cup'},
    {'id': 2, 'nome': 'Savories', 'icone': 'bread'},
    {'id': 3, 'nome': 'Sweets', 'icone': 'candy'},
    {'id': 4, 'nome': 'Snacks', 'icone': 'burger'},
]

# Products
PRODUTOS = [
    {'id': 1, 'nome': 'Cola 350ml', 'categoria_id': 1, 'categoria': 'Beverages', 'preco': Decimal('6.50'), 'estoque': 45, 'estoque_minimo': 10, 'ativo': True},
    {'id': 2, 'nome': 'Orange Juice 300ml', 'categoria_id': 1, 'categoria': 'Beverages', 'preco': Decimal('5.00'), 'estoque': 30, 'estoque_minimo': 8, 'ativo': True},
    {'id': 3, 'nome': 'Mineral Water 500ml', 'categoria_id': 1, 'categoria': 'Beverages', 'preco': Decimal('3.00'), 'estoque': 60, 'estoque_minimo': 15, 'ativo': True},
    {'id': 4, 'nome': 'Guarana 350ml', 'categoria_id': 1, 'categoria': 'Beverages', 'preco': Decimal('5.50'), 'estoque': 25, 'estoque_minimo': 10, 'ativo': True},
    {'id': 5, 'nome': 'Chicken Snack', 'categoria_id': 2, 'categoria': 'Savories', 'preco': Decimal('7.00'), 'estoque': 20, 'estoque_minimo': 5, 'ativo': True},
    {'id': 6, 'nome': 'Meat Pastry', 'categoria_id': 2, 'categoria': 'Savories', 'preco': Decimal('6.50'), 'estoque': 15, 'estoque_minimo': 5, 'ativo': True},
    {'id': 7, 'nome': 'Palmito Pie', 'categoria_id': 2, 'categoria': 'Savories', 'preco': Decimal('6.00'), 'estoque': 8, 'estoque_minimo': 5, 'ativo': True},
    {'id': 8, 'nome': 'Cheese Bread', 'categoria_id': 2, 'categoria': 'Savories', 'preco': Decimal('4.50'), 'estoque': 35, 'estoque_minimo': 10, 'ativo': True},
    {'id': 9, 'nome': 'Meat Esfiha', 'categoria_id': 2, 'categoria': 'Savories', 'preco': Decimal('5.50'), 'estoque': 12, 'estoque_minimo': 5, 'ativo': True},
    {'id': 10, 'nome': 'Brigadeiro', 'categoria_id': 3, 'categoria': 'Sweets', 'preco': Decimal('2.50'), 'estoque': 50, 'estoque_minimo': 15, 'ativo': True},
    {'id': 11, 'nome': 'Beijinho', 'categoria_id': 3, 'categoria': 'Sweets', 'preco': Decimal('2.50'), 'estoque': 40, 'estoque_minimo': 15, 'ativo': True},
    {'id': 12, 'nome': 'Milk Chocolate', 'categoria_id': 3, 'categoria': 'Sweets', 'preco': Decimal('4.00'), 'estoque': 30, 'estoque_minimo': 10, 'ativo': True},
    {'id': 13, 'nome': 'Mint Candy', 'categoria_id': 3, 'categoria': 'Sweets', 'preco': Decimal('0.50'), 'estoque': 100, 'estoque_minimo': 20, 'ativo': True},
    {'id': 14, 'nome': 'X-Burger', 'categoria_id': 4, 'categoria': 'Snacks', 'preco': Decimal('15.00'), 'estoque': 10, 'estoque_minimo': 3, 'ativo': True},
    {'id': 15, 'nome': 'X-Salad', 'categoria_id': 4, 'categoria': 'Snacks', 'preco': Decimal('17.00'), 'estoque': 8, 'estoque_minimo': 3, 'ativo': True},
    {'id': 16, 'nome': 'Simple Hot Dog', 'categoria_id': 4, 'categoria': 'Snacks', 'preco': Decimal('10.00'), 'estoque': 15, 'estoque_minimo': 5, 'ativo': True},
    {'id': 17, 'nome': 'Hot Mixed', 'categoria_id': 4, 'categoria': 'Snacks', 'preco': Decimal('8.00'), 'estoque': 5, 'estoque_minimo': 3, 'ativo': False},
    {'id': 18, 'nome': 'Cheese Tapioca', 'categoria_id': 4, 'categoria': 'Snacks', 'preco': Decimal('12.00'), 'estoque': 0, 'estoque_minimo': 5, 'ativo': True},
]

# People
PESSOAS = [
    {'id': 1, 'nome': 'João Silva', 'tipo': 'STUDENT', 'matricula': '2023001', 'status': 'ACTIVE', 'saldo': Decimal('15.50')},
    {'id': 2, 'nome': 'Maria Santos', 'tipo': 'STUDENT', 'matricula': '2023002', 'status': 'ACTIVE', 'saldo': Decimal('0.00')},
    {'id': 3, 'nome': 'Pedro Oliveira', 'tipo': 'STUDENT', 'matricula': '2023003', 'status': 'ACTIVE', 'saldo': Decimal('-25.00')},
    {'id': 4, 'nome': 'Ana Costa', 'tipo': 'TEACHER', 'matricula': 'PROF001', 'status': 'ACTIVE', 'saldo': Decimal('120.00')},
    {'id': 5, 'nome': 'Carlos Lima', 'tipo': 'TEACHER', 'matricula': 'PROF002', 'status': 'ACTIVE', 'saldo': Decimal('80.50')},
    {'id': 6, 'nome': 'Fernanda Rocha', 'tipo': 'STAFF', 'matricula': 'FUNC001', 'status': 'ACTIVE', 'saldo': Decimal('200.00')},
    {'id': 7, 'nome': 'Roberto Alves', 'tipo': 'STAFF', 'matricula': 'FUNC002', 'status': 'ACTIVE', 'saldo': Decimal('50.00')},
    {'id': 8, 'nome': 'Juliana Dias', 'tipo': 'VISITOR', 'matricula': 'VIS001', 'status': 'ACTIVE', 'saldo': Decimal('0.00')},
    {'id': 9, 'nome': 'Lucas Ferreira', 'tipo': 'STUDENT', 'matricula': '2023004', 'status': 'INACTIVE', 'saldo': Decimal('-10.00')},
    {'id': 10, 'nome': 'Patrícia Gomes', 'tipo': 'STUDENT', 'matricula': '2023005', 'status': 'ACTIVE', 'saldo': Decimal('45.00')},
]

# Payment methods
FORMAS_PAGAMENTO = [
    {'id': 1, 'nome': 'Cash', 'icone': 'cash'},
    {'id': 2, 'nome': 'Debit Card', 'icone': 'card'},
    {'id': 3, 'nome': 'Credit Card', 'icone': 'card'},
    {'id': 4, 'nome': 'PIX', 'icone': 'phone'},
    {'id': 5, 'nome': 'Account Balance', 'icone': 'wallet'},
]

# Sales (history)
def gerar_vendas_mock():
    vendas = []
    base_date = datetime.now() - timedelta(days=7)
    for i in range(30):
        data = base_date + timedelta(days=random.uniform(0, 7), hours=random.uniform(7, 18))
        pessoa = random.choice(PESSOAS)
        n_itens = random.randint(1, 5)
        itens = random.sample(PRODUTOS, n_itens)
        total = Decimal('0')
        for item in itens:
            qtd = random.randint(1, 3)
            total += item['preco'] * qtd
        forma_pgto = random.choice(FORMAS_PAGAMENTO)
        status = random.choice(['COMPLETED', 'COMPLETED', 'COMPLETED', 'CANCELLED', 'PENDING'])
        vendas.append({
            'id': i + 1,
            'codigo': f'VD{1000 + i}',
            'pessoa': pessoa,
            'data_hora': data,
            'total': total,
            'forma_pagamento': forma_pgto['nome'],
            'status': status,
            'itens': [{'produto': item, 'quantidade': random.randint(1, 3)} for item in itens]
        })
    return sorted(vendas, key=lambda x: x['data_hora'], reverse=True)

VENDAS = gerar_vendas_mock()

# Accounts receivable
CONTAS_RECEBER = [
    {'id': 1, 'pessoa': PESSOAS[2], 'valor': Decimal('25.00'), 'vencimento': datetime.now() - timedelta(days=5), 'status': 'OVERDUE', 'descricao': 'Sale VD1005'},
    {'id': 2, 'pessoa': PESSOAS[8], 'valor': Decimal('10.00'), 'vencimento': datetime.now() - timedelta(days=2), 'status': 'OVERDUE', 'descricao': 'Sale VD1012'},
    {'id': 3, 'pessoa': PESSOAS[0], 'valor': Decimal('15.50'), 'vencimento': datetime.now() + timedelta(days=3), 'status': 'PENDING', 'descricao': 'Sale VD1018'},
    {'id': 4, 'pessoa': PESSOAS[3], 'valor': Decimal('120.00'), 'vencimento': datetime.now() + timedelta(days=10), 'status': 'PENDING', 'descricao': 'Monthly Fee'},
    {'id': 5, 'pessoa': PESSOAS[5], 'valor': Decimal('200.00'), 'vencimento': datetime.now() + timedelta(days=15), 'status': 'PENDING', 'descricao': 'Advance'},
    {'id': 6, 'pessoa': PESSOAS[1], 'valor': Decimal('30.00'), 'vencimento': datetime.now() + timedelta(days=1), 'status': 'PENDING', 'descricao': 'Sale VD1022'},
    {'id': 7, 'pessoa': PESSOAS[4], 'valor': Decimal('80.50'), 'vencimento': datetime.now() + timedelta(days=20), 'status': 'PENDING', 'descricao': 'Monthly Fee'},
]

# Recent payments
PAGAMENTOS_RECENTES = [
    {'id': 1, 'pessoa': PESSOAS[0], 'valor': Decimal('50.00'), 'data': datetime.now() - timedelta(days=1), 'forma': 'PIX', 'referencia': 'Balance recharge'},
    {'id': 2, 'pessoa': PESSOAS[3], 'valor': Decimal('100.00'), 'data': datetime.now() - timedelta(days=2), 'forma': 'Debit Card', 'referencia': 'Monthly Fee'},
    {'id': 3, 'pessoa': PESSOAS[5], 'valor': Decimal('150.00'), 'data': datetime.now() - timedelta(days=3), 'forma': 'Cash', 'referencia': 'Advance'},
    {'id': 4, 'pessoa': PESSOAS[6], 'valor': Decimal('75.00'), 'data': datetime.now() - timedelta(days=4), 'forma': 'PIX', 'referencia': 'Balance recharge'},
]

# Dashboard stats
def get_dashboard_stats():
    sales_today = [v for v in VENDAS if v['data_hora'].date() == datetime.now().date()]
    daily_revenue = sum(v['total'] for v in sales_today)
    receivable_total = sum(c['valor'] for c in CONTAS_RECEBER if c['status'] == 'PENDING')
    overdue_total = sum(c['valor'] for c in CONTAS_RECEBER if c['status'] == 'OVERDUE')
    low_stock_products = [p for p in PRODUTOS if p['estoque'] <= p['estoque_minimo'] and p['ativo']]
    
    return {
        'vendas_dia': len(sales_today),
        'daily_revenue': daily_revenue,
        'receivable_total': receivable_total,
        'overdue_total': overdue_total,
        'low_stock_products_estoque': low_stock_products[:5],
        'vendas_recentes': sales_today[:5] if sales_today else VENDAS[:5],
    }

# Helper functions
def get_produto_by_id(produto_id):
    for p in PRODUTOS:
        if p['id'] == produto_id:
            return p
    return None

def get_pessoa_by_id(pessoa_id):
    for p in PESSOAS:
        if p['id'] == pessoa_id:
            return p
    return None

def get_categoria_by_id(categoria_id):
    for c in CATEGORIAS:
        if c['id'] == categoria_id:
            return c
    return None