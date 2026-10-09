"""
Mock data for frontend demonstration.
Centralized mock data to make it easy to replace with real models later.
"""

from decimal import Decimal
from datetime import datetime, timedelta
import random

# Categories
CATEGORIAS = [
    {'id': 1, 'nome': 'Bebidas', 'icone': 'cup'},
    {'id': 2, 'nome': 'Salgados', 'icone': 'bread'},
    {'id': 3, 'nome': 'Doces', 'icone': 'candy'},
    {'id': 4, 'nome': 'Lanches', 'icone': 'burger'},
]

# Products
PRODUTOS = [
    {'id': 1, 'nome': 'Coca-Cola 350ml', 'categoria_id': 1, 'categoria': 'Bebidas', 'preco': Decimal('6.50'), 'estoque': 45, 'estoque_minimo': 10, 'ativo': True},
    {'id': 2, 'nome': 'Suco de Laranja 300ml', 'categoria_id': 1, 'categoria': 'Bebidas', 'preco': Decimal('5.00'), 'estoque': 30, 'estoque_minimo': 8, 'ativo': True},
    {'id': 3, 'nome': 'Água Mineral 500ml', 'categoria_id': 1, 'categoria': 'Bebidas', 'preco': Decimal('3.00'), 'estoque': 60, 'estoque_minimo': 15, 'ativo': True},
    {'id': 4, 'nome': 'Guaraná Antarctica 350ml', 'categoria_id': 1, 'categoria': 'Bebidas', 'preco': Decimal('5.50'), 'estoque': 25, 'estoque_minimo': 10, 'ativo': True},
    {'id': 5, 'nome': 'Coxinha de Frango', 'categoria_id': 2, 'categoria': 'Salgados', 'preco': Decimal('7.00'), 'estoque': 20, 'estoque_minimo': 5, 'ativo': True},
    {'id': 6, 'nome': 'Pastel de Carne', 'categoria_id': 2, 'categoria': 'Salgados', 'preco': Decimal('6.50'), 'estoque': 15, 'estoque_minimo': 5, 'ativo': True},
    {'id': 7, 'nome': 'Empada de Palmito', 'categoria_id': 2, 'categoria': 'Salgados', 'preco': Decimal('6.00'), 'estoque': 8, 'estoque_minimo': 5, 'ativo': True},
    {'id': 8, 'nome': 'Pão de Queijo', 'categoria_id': 2, 'categoria': 'Salgados', 'preco': Decimal('4.50'), 'estoque': 35, 'estoque_minimo': 10, 'ativo': True},
    {'id': 9, 'nome': 'Esfiha de Carne', 'categoria_id': 2, 'categoria': 'Salgados', 'preco': Decimal('5.50'), 'estoque': 12, 'estoque_minimo': 5, 'ativo': True},
    {'id': 10, 'nome': 'Brigadeiro', 'categoria_id': 3, 'categoria': 'Doces', 'preco': Decimal('2.50'), 'estoque': 50, 'estoque_minimo': 15, 'ativo': True},
    {'id': 11, 'nome': 'Beijinho', 'categoria_id': 3, 'categoria': 'Doces', 'preco': Decimal('2.50'), 'estoque': 40, 'estoque_minimo': 15, 'ativo': True},
    {'id': 12, 'nome': 'Chocolate Ao Leite', 'categoria_id': 3, 'categoria': 'Doces', 'preco': Decimal('4.00'), 'estoque': 30, 'estoque_minimo': 10, 'ativo': True},
    {'id': 13, 'nome': 'Bala de Menta', 'categoria_id': 3, 'categoria': 'Doces', 'preco': Decimal('0.50'), 'estoque': 100, 'estoque_minimo': 20, 'ativo': True},
    {'id': 14, 'nome': 'X-Burger', 'categoria_id': 4, 'categoria': 'Lanches', 'preco': Decimal('15.00'), 'estoque': 10, 'estoque_minimo': 3, 'ativo': True},
    {'id': 15, 'nome': 'X-Salada', 'categoria_id': 4, 'categoria': 'Lanches', 'preco': Decimal('17.00'), 'estoque': 8, 'estoque_minimo': 3, 'ativo': True},
    {'id': 16, 'nome': 'Hot Dog Simples', 'categoria_id': 4, 'categoria': 'Lanches', 'preco': Decimal('10.00'), 'estoque': 15, 'estoque_minimo': 5, 'ativo': True},
    {'id': 17, 'nome': 'Misto Quente', 'categoria_id': 4, 'categoria': 'Lanches', 'preco': Decimal('8.00'), 'estoque': 5, 'estoque_minimo': 3, 'ativo': False},
    {'id': 18, 'nome': 'Tapioca de Queijo', 'categoria_id': 4, 'categoria': 'Lanches', 'preco': Decimal('12.00'), 'estoque': 0, 'estoque_minimo': 5, 'ativo': True},
]

# People
PESSOAS = [
    {'id': 1, 'nome': 'João Silva', 'tipo': 'ALUNO', 'matricula': '2023001', 'status': 'ATIVO', 'saldo': Decimal('15.50')},
    {'id': 2, 'nome': 'Maria Santos', 'tipo': 'ALUNO', 'matricula': '2023002', 'status': 'ATIVO', 'saldo': Decimal('0.00')},
    {'id': 3, 'nome': 'Pedro Oliveira', 'tipo': 'ALUNO', 'matricula': '2023003', 'status': 'ATIVO', 'saldo': Decimal('-25.00')},
    {'id': 4, 'nome': 'Ana Costa', 'tipo': 'PROFESSOR', 'matricula': 'PROF001', 'status': 'ATIVO', 'saldo': Decimal('120.00')},
    {'id': 5, 'nome': 'Carlos Lima', 'tipo': 'PROFESSOR', 'matricula': 'PROF002', 'status': 'ATIVO', 'saldo': Decimal('80.50')},
    {'id': 6, 'nome': 'Fernanda Rocha', 'tipo': 'FUNCIONÁRIO', 'matricula': 'FUNC001', 'status': 'ATIVO', 'saldo': Decimal('200.00')},
    {'id': 7, 'nome': 'Roberto Alves', 'tipo': 'FUNCIONÁRIO', 'matricula': 'FUNC002', 'status': 'ATIVO', 'saldo': Decimal('50.00')},
    {'id': 8, 'nome': 'Juliana Dias', 'tipo': 'VISITANTE', 'matricula': 'VIS001', 'status': 'ATIVO', 'saldo': Decimal('0.00')},
    {'id': 9, 'nome': 'Lucas Ferreira', 'tipo': 'ALUNO', 'matricula': '2023004', 'status': 'INATIVO', 'saldo': Decimal('-10.00')},
    {'id': 10, 'nome': 'Patrícia Gomes', 'tipo': 'ALUNO', 'matricula': '2023005', 'status': 'ATIVO', 'saldo': Decimal('45.00')},
]

# Payment methods
FORMAS_PAGAMENTO = [
    {'id': 1, 'nome': 'Dinheiro', 'icone': 'cash'},
    {'id': 2, 'nome': 'Cartão Débito', 'icone': 'card'},
    {'id': 3, 'nome': 'Cartão Crédito', 'icone': 'card'},
    {'id': 4, 'nome': 'PIX', 'icone': 'phone'},
    {'id': 5, 'nome': 'Saldo Conta', 'icone': 'wallet'},
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
        status = random.choice(['CONCLUIDA', 'CONCLUIDA', 'CONCLUIDA', 'CANCELADA', 'PENDENTE'])
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
    {'id': 1, 'pessoa': PESSOAS[2], 'valor': Decimal('25.00'), 'vencimento': datetime.now() - timedelta(days=5), 'status': 'VENCIDA', 'descricao': 'Venda VD1005'},
    {'id': 2, 'pessoa': PESSOAS[8], 'valor': Decimal('10.00'), 'vencimento': datetime.now() - timedelta(days=2), 'status': 'VENCIDA', 'descricao': 'Venda VD1012'},
    {'id': 3, 'pessoa': PESSOAS[0], 'valor': Decimal('15.50'), 'vencimento': datetime.now() + timedelta(days=3), 'status': 'PENDENTE', 'descricao': 'Venda VD1018'},
    {'id': 4, 'pessoa': PESSOAS[3], 'valor': Decimal('120.00'), 'vencimento': datetime.now() + timedelta(days=10), 'status': 'PENDENTE', 'descricao': 'Mensalidade'},
    {'id': 5, 'pessoa': PESSOAS[5], 'valor': Decimal('200.00'), 'vencimento': datetime.now() + timedelta(days=15), 'status': 'PENDENTE', 'descricao': 'Adiantamento'},
    {'id': 6, 'pessoa': PESSOAS[1], 'valor': Decimal('30.00'), 'vencimento': datetime.now() + timedelta(days=1), 'status': 'PENDENTE', 'descricao': 'Venda VD1022'},
    {'id': 7, 'pessoa': PESSOAS[4], 'valor': Decimal('80.50'), 'vencimento': datetime.now() + timedelta(days=20), 'status': 'PENDENTE', 'descricao': 'Mensalidade'},
]

# Recent payments
PAGAMENTOS_RECENTES = [
    {'id': 1, 'pessoa': PESSOAS[0], 'valor': Decimal('50.00'), 'data': datetime.now() - timedelta(days=1), 'forma': 'PIX', 'referencia': 'Recarga de saldo'},
    {'id': 2, 'pessoa': PESSOAS[3], 'valor': Decimal('100.00'), 'data': datetime.now() - timedelta(days=2), 'forma': 'Cartão Débito', 'referencia': 'Mensalidade'},
    {'id': 3, 'pessoa': PESSOAS[5], 'valor': Decimal('150.00'), 'data': datetime.now() - timedelta(days=3), 'forma': 'Dinheiro', 'referencia': 'Adiantamento'},
    {'id': 4, 'pessoa': PESSOAS[6], 'valor': Decimal('75.00'), 'data': datetime.now() - timedelta(days=4), 'forma': 'PIX', 'referencia': 'Recarga de saldo'},
]

# Dashboard stats
def get_dashboard_stats():
    vendas_hoje = [v for v in VENDAS if v['data_hora'].date() == datetime.now().date()]
    faturamento_dia = sum(v['total'] for v in vendas_hoje)
    valor_receber = sum(c['valor'] for c in CONTAS_RECEBER if c['status'] == 'PENDENTE')
    valor_vencido = sum(c['valor'] for c in CONTAS_RECEBER if c['status'] == 'VENCIDA')
    produtos_baixo = [p for p in PRODUTOS if p['estoque'] <= p['estoque_minimo'] and p['ativo']]
    
    return {
        'vendas_dia': len(vendas_hoje),
        'faturamento_dia': faturamento_dia,
        'valor_receber': valor_receber,
        'valor_vencido': valor_vencido,
        'produtos_baixo_estoque': produtos_baixo[:5],
        'vendas_recentes': vendas_hoje[:5] if vendas_hoje else VENDAS[:5],
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