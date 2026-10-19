"""Realistic, fully reversible demo dataset for local presentations.

Both management commands share this module so generation and cleanup have a
single source of truth. Records are written through the real models with the
same invariants the application services enforce (see ``services.py``);
timestamps are backdated because the services stamp ``timezone.now()``.

A JSON manifest next to ``DEMO_DATA_MANIFEST_PATH`` records the exact primary
keys created by a seeding run. Cleanup deletes only those rows, refuses to run
when untracked records reference them, and never touches unrelated data.

Durability: the manifest is written *before* the seeding transaction commits,
so a committed dataset is always identifiable; if the transaction or the
manifest write fails, the manifest is removed and the database is rolled back.
"""
from __future__ import annotations

import json
import os
import tempfile
import unicodedata
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from random import Random

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AccountReceivable,
    Category,
    OnboardingProgress,
    Payment,
    Person,
    Product,
    Sale,
    SaleItem,
    StockMovement,
)

DEMO_USER_PREFIX = 'demo_'
DEMO_PASSWORD = 'Demo@1234'
DEMO_EMAIL_DOMAIN = 'example.test'
MANIFEST_VERSION = 1
MANIFEST_TOOL = 'seed_demo_data'

MODEL_REGISTRY = {
    'auth.User': User,
    'frontend.Category': Category,
    'frontend.Product': Product,
    'frontend.Person': Person,
    'frontend.Sale': Sale,
    'frontend.SaleItem': SaleItem,
    'frontend.StockMovement': StockMovement,
    'frontend.AccountReceivable': AccountReceivable,
    'frontend.Payment': Payment,
    'django.contrib.sessions.models.Session': Session,
}
MANIFEST_MODELS = tuple(MODEL_REGISTRY)

DELETION_ORDER = [
    'frontend.Payment',
    'frontend.StockMovement',
    'frontend.SaleItem',
    'frontend.Sale',
    'frontend.AccountReceivable',
    'frontend.Product',
    'frontend.Person',
    'frontend.Category',
]

BUSINESS_HOURS = [8, 9, 10, 10, 11, 11, 11, 12, 12, 12, 12, 13, 13, 13, 14, 14, 15, 16]

CATEGORY_SPECS = [
    ('Salgados', 'Salgados assados e fritos preparados na cantina'),
    ('Bebidas', 'Refrigerantes, águas e bebidas industrializadas'),
    ('Sucos e Vitaminas', 'Sucos naturais e vitaminas preparadas na hora'),
    ('Doces e Sobremesas', 'Doces, bolos e sobremesas caseiras'),
    ('Panificados', 'Pães, broas e produtos de padaria'),
    ('Laticínios', 'Leite, queijos, iogurtes e derivados'),
    ('Grãos e Kits', 'Castanhas, cereais e kits lanche'),
    ('Higiene e Utilitários', 'Itens de higiene e material de papelaria escolar'),
]

PRODUCT_SPECS = [
    ('Salgados', 'COX-01', 'Coxinha de Frango', '8.50', '5.10', 12),
    ('Salgados', 'PDQ-01', 'Pão de Queijo', '4.00', '2.40', 20),
    ('Salgados', 'ESF-01', 'Esfiha de Carne', '7.50', '4.50', 12),
    ('Salgados', 'EMP-01', 'Empada de Palmito', '8.00', '4.80', 10),
    ('Salgados', 'RIS-01', 'Risoles de Queijo', '7.00', '4.20', 10),
    ('Salgados', 'PAS-01', 'Pastel de Queijo', '6.50', '3.60', 15),
    ('Salgados', 'ENR-01', 'Enroladinho de Salsicha', '6.00', '3.40', 12),
    ('Bebidas', 'REF-01', 'Refrigerante Cola Lata 350ml', '6.00', '3.80', 24),
    ('Bebidas', 'REF-02', 'Refrigerante Guaraná Lata 350ml', '5.50', '3.40', 24),
    ('Bebidas', 'AGU-01', 'Água Mineral 500ml', '3.00', '1.50', 30),
    ('Bebidas', 'AGU-02', 'Água com Gás 500ml', '3.50', '1.80', 20),
    ('Bebidas', 'CHA-01', 'Chá Gelado Limão 300ml', '5.00', '3.00', 15),
    ('Bebidas', 'ISO-01', 'Isotônico 500ml', '7.50', '4.90', 12),
    ('Sucos e Vitaminas', 'SUCO-01', 'Suco de Laranja 300ml', '7.00', '3.20', 15),
    ('Sucos e Vitaminas', 'SUCO-02', 'Suco de Maracujá 300ml', '7.00', '3.30', 12),
    ('Sucos e Vitaminas', 'VIT-01', 'Vitamina de Banana 400ml', '9.00', '4.60', 10),
    ('Sucos e Vitaminas', 'SUCO-03', 'Suco de Abacaxi com Hortelã 300ml', '7.50', '3.40', 10),
    ('Doces e Sobremesas', 'DOC-01', 'Brigadeiro Gourmet', '4.50', '1.90', 20),
    ('Doces e Sobremesas', 'BOL-01', 'Bolo de Cenoura (fatia)', '6.00', '2.80', 10),
    ('Doces e Sobremesas', 'PUD-01', 'Pudim de Leite (fatia)', '6.50', '3.00', 8),
    ('Doces e Sobremesas', 'MOU-01', 'Mousse de Maracujá', '6.00', '2.70', 8),
    ('Doces e Sobremesas', 'PAL-01', 'Palha Italiana', '5.00', '2.20', 15),
    ('Doces e Sobremesas', 'TOR-01', 'Torta de Limão (fatia)', '7.00', '3.30', 8),
    ('Doces e Sobremesas', 'GEL-01', 'Gelatina de Morango', '3.50', '1.40', 20),
    ('Panificados', 'PAO-01', 'Pão Francês', '1.50', '0.80', 30),
    ('Panificados', 'PAO-02', 'Pão de Forma (pacote)', '8.50', '5.50', 10),
    ('Panificados', 'PAO-03', 'Pão Integral (pacote)', '9.50', '6.20', 10),
    ('Panificados', 'BRO-01', 'Broa de Milho', '3.00', '1.50', 15),
    ('Panificados', 'BIS-01', 'Bisnaguinha (pacote)', '7.00', '4.30', 12),
    ('Laticínios', 'LEI-01', 'Leite Integral 1L', '5.50', '3.90', 20),
    ('Laticínios', 'QUE-01', 'Queijo Minas (200g)', '12.90', '8.50', 8),
    ('Laticínios', 'IOG-01', 'Iogurte de Morango', '4.50', '2.60', 15),
    ('Laticínios', 'REQ-01', 'Requeijão Cremoso 200g', '9.90', '6.40', 10),
    ('Laticínios', 'LEI-02', 'Leite Desnatado 1L', '5.80', '4.10', 15),
    ('Grãos e Kits', 'KIT-01', 'Kit Lanche Completo', '18.00', '11.00', 8),
    ('Grãos e Kits', 'CAS-01', 'Castanha de Caju (100g)', '14.90', '9.80', 10),
    ('Grãos e Kits', 'MIX-01', 'Mix de Frutas Secas (100g)', '12.50', '8.20', 8),
    ('Grãos e Kits', 'GRA-01', 'Granola (250g)', '11.90', '7.40', 10),
    ('Higiene e Utilitários', 'ALC-01', 'Álcool em Gel 100ml', '6.90', '3.90', 15),
    ('Higiene e Utilitários', 'LEN-01', 'Lenço de Papel (pacote)', '4.50', '2.10', 20),
    ('Higiene e Utilitários', 'CAN-01', 'Caneta Esferográfica', '2.50', '1.10', 25),
    ('Higiene e Utilitários', 'CAD-01', 'Caderno Universitário', '19.90', '12.50', 6),
]

FINAL_STOCK_OVERRIDES = {
    'PDQ-01': 4,
    'COX-01': 3,
    'REF-01': 6,
    'SUCO-01': 2,
    'DOC-01': 5,
    'AGU-01': 0,
    'CAN-01': 0,
}
SPECIAL_CODES = set(FINAL_STOCK_OVERRIDES)
INACTIVE_CODES = {'CHA-01', 'GRA-01', 'LEI-02'}

POPULARITY = {
    'PDQ-01': 5, 'COX-01': 5, 'REF-01': 4, 'SUCO-01': 3, 'DOC-01': 3,
    'PAO-01': 3, 'REF-02': 3, 'ESF-01': 2, 'PAS-01': 2, 'KIT-01': 2,
    'AGU-01': 2, 'PAL-01': 2, 'VIT-01': 2, 'BOL-01': 2,
}

USER_SPECS = [
    ('demo_ana.souza', 'Ana Paula', 'Souza'),
    ('demo_carlos.lima', 'Carlos Eduardo', 'Lima'),
    ('demo_juliana.alves', 'Juliana', 'Alves'),
    ('demo_rafael.santos', 'Rafael', 'Santos'),
    ('demo_marina.costa', 'Marina', 'Costa'),
    ('demo_pedro.silva', 'Pedro Henrique', 'Silva'),
]

PEOPLE_SPECS = [
    ('Ana Beatriz Souza', 'STUDENT', 'MAT-2025-001'),
    ('Bruno Ferreira', 'STUDENT', 'MAT-2025-002'),
    ('Camila Rodrigues', 'STUDENT', 'MAT-2025-003'),
    ('Diego Martins', 'STUDENT', 'MAT-2025-004'),
    ('Fernanda Barbosa', 'STUDENT', 'MAT-2025-005'),
    ('Gustavo Pereira', 'STUDENT', 'MAT-2025-006'),
    ('Larissa Oliveira', 'STUDENT', 'MAT-2025-007'),
    ('Lucas Almeida', 'STUDENT', 'MAT-2025-008'),
    ('Natália Ribeiro', 'STUDENT', 'MAT-2025-009'),
    ('Paulo Henrique Castro', 'STUDENT', 'MAT-2025-010'),
    ('Renata Cardoso', 'STUDENT', 'MAT-2025-011'),
    ('Thiago Nunes', 'STUDENT', 'MAT-2025-012'),
    ('Helena Duarte', 'TEACHER', 'PRF-2025-01'),
    ('Marcos Vinícius Prado', 'TEACHER', 'PRF-2025-02'),
    ('Otávio Ribeiro', 'TEACHER', 'PRF-2025-03'),
    ('Patrícia Nogueira', 'TEACHER', 'PRF-2025-04'),
    ('Regina Campos', 'TEACHER', 'PRF-2025-05'),
    ('Sérgio Tavares', 'TEACHER', 'PRF-2025-06'),
    ('Cláudia Menezes', 'STAFF', 'FUN-2025-01'),
    ('Jorge Farias', 'STAFF', 'FUN-2025-02'),
    ('Simone Barreto', 'STAFF', 'FUN-2025-03'),
    ('Alice Moreira', 'VISITOR', ''),
    ('Tomás Guimarães', 'VISITOR', ''),
    ('Vitória Lopes', 'VISITOR', ''),
]


class DemoDataError(Exception):
    """Raised for controlled, user-facing demo data failures."""


class DemoDataConflictError(DemoDataError):
    def __init__(self, conflicts):
        self.conflicts = list(conflicts)
        super().__init__('; '.join(self.conflicts))


def commands_enabled() -> bool:
    return bool(getattr(settings, 'ALLOW_DEMO_DATA_COMMANDS', settings.DEBUG))


def require_enabled() -> None:
    if not commands_enabled():
        raise DemoDataError(
            'Demo data commands are disabled outside development. They only run '
            'when ALLOW_DEMO_DATA_COMMANDS is enabled (defaults to DEBUG). '
            'Never enable this on a production system.'
        )


def manifest_path() -> Path:
    return Path(settings.DEMO_DATA_MANIFEST_PATH)


def manifest_exists() -> bool:
    return manifest_path().exists()


def read_manifest():
    path = manifest_path()
    if not path.exists():
        return None
    try:
        with path.open('r', encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def write_manifest_atomic(data: dict) -> None:
    """Persist the manifest atomically (temp file + fsync + os.replace)."""
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=path.name + '.', suffix='.tmp', dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def delete_manifest() -> None:
    try:
        manifest_path().unlink()
    except FileNotFoundError:
        pass


def session_pks_for_users(user_pks) -> list:
    """Session row pks whose authenticated user is one of ``user_pks``."""
    user_ids = {int(pk) for pk in user_pks}
    if not user_ids:
        return []
    found = []
    for pk, data in Session.objects.values_list('pk', 'session_data').iterator():
        try:
            decoded = SessionStore().decode(data)
        except Exception:
            continue
        uid = decoded.get('_auth_user_id') if isinstance(decoded, dict) else None
        try:
            if uid is not None and int(uid) in user_ids:
                found.append(pk)
        except (TypeError, ValueError):
            continue
    return found


def _aware(day, hour=8, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def _slug(name: str) -> str:
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return normalized.lower().replace(' ', '.')


def _day_volumes(rng: Random, today) -> dict:
    volumes = {}
    for offset in range(30, 0, -1):
        day = today - timedelta(days=offset)
        weekday = day.weekday()
        if weekday >= 5:
            count = rng.choice([0, 1, 1, 2])
        elif weekday == 4:
            count = rng.choice([2, 3, 4, 4, 5])
        else:
            count = rng.choice([1, 2, 3, 3, 4, 4, 5])
        volumes[day] = count
    volumes[today] = 4
    volumes[today - timedelta(days=1)] = 2
    adjustable = [d for d in volumes if d not in (today, today - timedelta(days=1))]
    total = sum(volumes.values())
    while total > 80:
        day = rng.choice(adjustable)
        if volumes[day] > 0:
            volumes[day] -= 1
            total -= 1
    while total < 80:
        day = rng.choice(adjustable)
        volumes[day] += 1
        total += 1
    calm_candidates = [d for d in adjustable if d.weekday() < 5 and volumes[d] > 0]
    if calm_candidates:
        calm = rng.choice(calm_candidates)
        removed = volumes[calm]
        volumes[calm] = 0
        others = [d for d in adjustable if d != calm]
        for _ in range(removed):
            day = rng.choice(others)
            volumes[day] += 1
    return volumes


def _create_categories(created) -> dict:
    categories = {}
    for name, description in CATEGORY_SPECS:
        category = Category.objects.create(name=name, description=description)
        categories[name] = category
        created['frontend.Category'].append(category.pk)
    return categories


def _create_products(categories, created) -> list:
    products = []
    for category_name, code, name, price, cost, minimum in PRODUCT_SPECS:
        product = Product.objects.create(
            name=name,
            code=code,
            category=categories[category_name],
            price=Decimal(price),
            cost_price=Decimal(cost),
            stock_quantity=0,
            minimum_stock=minimum,
            active=code not in INACTIVE_CODES,
        )
        products.append(product)
        created['frontend.Product'].append(product.pk)
    return products


def _create_people(rng: Random, created) -> list:
    people = []
    for name, person_type, doc_id in PEOPLE_SPECS:
        person = Person.objects.create(
            name=name,
            doc_id=doc_id,
            person_type=person_type,
            email=f'{_slug(name)}@{DEMO_EMAIL_DOMAIN}',
            phone=f'(11) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}',
            active=True,
        )
        people.append(person)
        created['frontend.Person'].append(person.pk)
    return people


def _create_users(created) -> list:
    users = []
    for username, first_name, last_name in USER_SPECS:
        user = User.objects.create_user(
            username=username,
            email=f'{username[len(DEMO_USER_PREFIX):]}@{DEMO_EMAIL_DOMAIN}',
            password=DEMO_PASSWORD,
            first_name=first_name,
            last_name=last_name,
        )
        users.append(user)
        created['auth.User'].append(user.pk)
    return users


def _backdate_catalog(categories, people, products, window_start) -> None:
    stamp = _aware(window_start, 8, 0)
    Category.objects.filter(pk__in=[c.pk for c in categories.values()]).update(
        created_at=stamp, updated_at=stamp,
    )
    Person.objects.filter(pk__in=[p.pk for p in people]).update(
        created_at=stamp, updated_at=stamp,
    )
    Product.objects.filter(pk__in=[p.pk for p in products]).update(
        created_at=stamp, updated_at=stamp,
    )


def _pick_unique_products(rng: Random, pool, count: int) -> list:
    chosen = []
    while len(chosen) < count:
        candidate = rng.choices([p for p, _ in pool], weights=[w for _, w in pool], k=1)[0]
        if candidate not in chosen:
            chosen.append(candidate)
    return chosen


def _create_sales(rng, products, people, users, today, created):
    volumes = _day_volumes(rng, today)
    slots = [day for day, count in volumes.items() for _ in range(count)]
    rng.shuffle(slots)

    statuses = ['COMPLETED'] * len(slots)
    cancelled_idx = rng.sample(
        [i for i, day in enumerate(slots) if (today - day).days >= 5], 4,
    )
    pending_idx = rng.sample(
        [i for i, day in enumerate(slots)
         if i not in set(cancelled_idx) and (today - day).days >= 2], 4,
    )
    for index in cancelled_idx:
        statuses[index] = 'CANCELLED'
    for index in pending_idx:
        statuses[index] = 'PENDING'

    completed_idx = [i for i, status in enumerate(statuses) if status == 'COMPLETED']
    methods_pool = (
        ['ON_ACCOUNT'] * 10 + ['CASH'] * 30 + ['PIX'] * 22 + ['DEBIT'] * 6 + ['CREDIT'] * 4
    )
    rng.shuffle(methods_pool)
    method_for = dict(zip(completed_idx, methods_pool))

    on_account = [i for i in completed_idx if method_for[i] == 'ON_ACCOUNT']
    old_on_account = [i for i in on_account if (today - slots[i]).days >= 12]
    if len(old_on_account) < 2:
        older_candidates = [
            i for i in completed_idx
            if method_for[i] != 'ON_ACCOUNT' and (today - slots[i]).days >= 12
        ]
        for index in [i for i in on_account if i not in old_on_account]:
            if len(old_on_account) >= 2 or not older_candidates:
                break
            swap = older_candidates.pop()
            method_for[index], method_for[swap] = method_for[swap], method_for[index]
            old_on_account.append(swap)

    weighted_pool = [(p, POPULARITY.get(p.code, 1)) for p in products if p.active]
    non_special_pool = [(p, w) for p, w in weighted_pool if p.code not in SPECIAL_CODES]

    effects = {}
    sales = []
    on_account_sales = []
    status_counts = {'COMPLETED': 0, 'PENDING': 0, 'CANCELLED': 0}

    for index, day in enumerate(slots):
        status = statuses[index]
        status_counts[status] += 1
        stamp = _aware(day, rng.choice(BUSINESS_HOURS), rng.randint(0, 59))
        responsible = rng.choice(users)

        if status == 'PENDING':
            sale = Sale.objects.create(
                customer=None, responsible=responsible, status='PENDING',
                payment_method='CASH', notes='Rascunho aguardando finalização',
            )
            Sale.objects.filter(pk=sale.pk).update(created_at=stamp)
            sales.append(sale)
            created['frontend.Sale'].append(sale.pk)
            continue

        if status == 'CANCELLED':
            method = rng.choice(['CASH', 'PIX', 'DEBIT'])
            customer = rng.choice(people) if rng.random() < 0.5 else None
            pool = non_special_pool
        else:
            method = method_for[index]
            customer = rng.choice(people) if (method == 'ON_ACCOUNT' or rng.random() < 0.7) else None
            pool = weighted_pool

        item_count = rng.choice([1, 2, 2, 3, 3, 4, 5])
        chosen = _pick_unique_products(rng, pool, item_count)
        quantities = [rng.choice([1, 1, 1, 2, 2, 3, 4]) for _ in chosen]
        total = sum(product.price * quantity for product, quantity in zip(chosen, quantities))
        completed_at = stamp + timedelta(minutes=rng.randint(1, 12))

        sale = Sale.objects.create(
            customer=customer, responsible=responsible, status=status,
            payment_method=method, subtotal=total, total=total,
            completed_at=completed_at,
        )
        Sale.objects.filter(pk=sale.pk).update(created_at=stamp)
        created['frontend.Sale'].append(sale.pk)
        sales.append(sale)

        items = [
            SaleItem(
                sale=sale, product=product, quantity=quantity,
                unit_price=product.price, subtotal=product.price * quantity,
            )
            for product, quantity in zip(chosen, quantities)
        ]
        SaleItem.objects.bulk_create(items)
        created['frontend.SaleItem'].extend(item.pk for item in items)

        for item in items:
            effects.setdefault(item.product_id, []).append(
                (stamp, -item.quantity, 'SALE', sale, responsible, 'Sale confirmed'),
            )
        if status == 'CANCELLED':
            return_stamp = min(
                stamp + timedelta(days=rng.randint(1, 3), hours=rng.randint(1, 4)),
                timezone.now(),
            )
            for item in items:
                effects.setdefault(item.product_id, []).append(
                    (return_stamp, item.quantity, 'RETURN', sale, responsible, 'Sale cancellation'),
                )
        if method == 'ON_ACCOUNT':
            on_account_sales.append(sale)

    return sales, on_account_sales, effects, status_counts


def _final_stock_target(rng: Random, product: Product) -> int:
    if product.code in FINAL_STOCK_OVERRIDES:
        return FINAL_STOCK_OVERRIDES[product.code]
    if not product.active:
        return rng.randint(0, 12)
    return product.minimum_stock + rng.randint(10, 40)


def _apply_inventory(rng, products, effects, users, window_start, created):
    sold_products = [p for p in products if effects.get(p.pk)]
    adjustment_specs = {}
    for product in rng.sample(sold_products, min(3, len(sold_products))):
        day = window_start + timedelta(days=rng.randint(3, 27))
        quantity = rng.choice([-3, -2, -1, 1, 2, 3])
        reason = 'Avaria identificada' if quantity < 0 else 'Contagem de inventário'
        adjustment_specs.setdefault(product.pk, []).append(
            (_aware(day, 15, 30), quantity, 'ADJUSTMENT', None, rng.choice(users), reason),
        )

    entry_stamp = _aware(window_start, 7, 30)
    movement_objects = []
    movement_stamps = []
    for product in products:
        specs = list(effects.get(product.pk, [])) + list(adjustment_specs.get(product.pk, []))
        specs.sort(key=lambda spec: spec[0])
        non_entry_total = sum(spec[1] for spec in specs)
        running = 0
        prefix_min = 0
        for spec in specs:
            running += spec[1]
            prefix_min = min(prefix_min, running)
        target = _final_stock_target(rng, product)
        entry_quantity = max(target - non_entry_total, -prefix_min, 0)
        if entry_quantity == 0 and not specs and target > 0:
            entry_quantity = target

        complete = []
        if entry_quantity > 0:
            complete.append(
                (entry_stamp, entry_quantity, 'ENTRY', None, rng.choice(users), 'Initial stock'),
            )
        complete.extend(specs)

        balance = 0
        for _, quantity, _, _, _, _ in complete:
            balance += quantity
            if balance < 0:
                raise DemoDataError(
                    f'Inventory ledger for {product.code} would go negative '
                    f'({balance}); aborting to avoid inconsistent stock.'
                )
        product.stock_quantity = balance
        for stamp, quantity, movement_type, sale, user, reason in complete:
            movement_objects.append(StockMovement(
                product=product, movement_type=movement_type, quantity=quantity,
                sale=sale, user=user, reason=reason,
            ))
            movement_stamps.append(stamp)

    StockMovement.objects.bulk_create(movement_objects, batch_size=500)
    for movement, stamp in zip(movement_objects, movement_stamps):
        movement.created_at = stamp
    StockMovement.objects.bulk_update(movement_objects, ['created_at'], batch_size=500)
    Product.objects.bulk_update(products, ['stock_quantity'], batch_size=200)
    created['frontend.StockMovement'].extend(movement.pk for movement in movement_objects)


def _split_amounts(rng: Random, total: Decimal) -> list:
    pattern = rng.choice([1, 2, 3])
    if pattern == 1:
        return [total]
    if pattern == 2:
        first = (total / 2).quantize(Decimal('0.01'))
        return [first, total - first]
    first = (total / 3).quantize(Decimal('0.01'))
    second = (total / 3).quantize(Decimal('0.01'))
    return [first, second, total - first - second]


def _create_receivables_and_payments(rng, on_account_sales, users, today, created):
    ordered = sorted(on_account_sales, key=lambda sale: sale.completed_at)
    old = [s for s in ordered if (today - timezone.localtime(s.completed_at).date()).days >= 12]
    if len(old) < 2:
        raise DemoDataError('Not enough older On Account sales to build overdue receivables.')
    overdue = rng.sample(old, 2)
    remaining = [s for s in ordered if s not in overdue]
    rng.shuffle(remaining)
    paid, partial, pending = remaining[:3], remaining[3:6], remaining[6:]

    receivables = []
    payments = 0
    for sale in ordered:
        sale_day = timezone.localtime(sale.completed_at).date()
        due_date = sale_day + timedelta(days=10 if sale in overdue else 30)
        receivable = AccountReceivable.objects.create(
            person=sale.customer, sale=sale, original_amount=sale.total,
            due_date=due_date, status='PENDING',
        )
        receivables.append(receivable)
        created['frontend.AccountReceivable'].append(receivable.pk)

        amounts = []
        if sale in paid:
            amounts = _split_amounts(rng, sale.total)
        elif sale in partial:
            fraction = Decimal(rng.choice(['0.4', '0.5', '0.6', '0.7']))
            amounts = [(sale.total * fraction).quantize(Decimal('0.01'))]

        if amounts:
            pay_stamp = min(
                timezone.localtime(sale.completed_at)
                + timedelta(days=rng.randint(2, 10), hours=rng.randint(1, 6)),
                timezone.now() - timedelta(hours=2),
            )
            for amount in amounts:
                if amount <= 0:
                    continue
                payment = Payment.objects.create(
                    account_receivable=receivable, amount=amount,
                    method=rng.choice(['PIX', 'CASH', 'TRANSFER', 'DEBIT']),
                    responsible_user=rng.choice(users),
                    notes='Pagamento registrado no caixa',
                )
                Payment.objects.filter(pk=payment.pk).update(
                    payment_date=pay_stamp.date(), created_at=pay_stamp,
                )
                payments += 1
                created['frontend.Payment'].append(payment.pk)

    for receivable in receivables:
        receivable.update_status()
        receivable.save(update_fields=['status'])
    return payments


def seed_demo_dataset(seed: int = 42):
    rng = Random(seed)
    today = timezone.localdate()
    window_start = today - timedelta(days=30)
    created = {label: [] for label in MANIFEST_MODELS}

    try:
        with transaction.atomic():
            categories = _create_categories(created)
            products = _create_products(categories, created)
            people = _create_people(rng, created)
            users = _create_users(created)
            _backdate_catalog(categories, people, products, window_start)

            _, on_account_sales, effects, status_counts = _create_sales(
                rng, products, people, users, today, created,
            )
            _apply_inventory(rng, products, effects, users, window_start, created)
            payments = _create_receivables_and_payments(
                rng, on_account_sales, users, today, created,
            )

            counts = {
                'users': len(created['auth.User']),
                'categories': len(created['frontend.Category']),
                'products': len(created['frontend.Product']),
                'people': len(created['frontend.Person']),
                'sales_total': len(created['frontend.Sale']),
                'sales_completed': status_counts['COMPLETED'],
                'sales_pending': status_counts['PENDING'],
                'sales_cancelled': status_counts['CANCELLED'],
                'sale_items': len(created['frontend.SaleItem']),
                'stock_movements': len(created['frontend.StockMovement']),
                'receivables': len(created['frontend.AccountReceivable']),
                'payments': payments,
            }
            manifest = {
                'tool': MANIFEST_TOOL,
                'version': MANIFEST_VERSION,
                'generated_at': timezone.now().isoformat(),
                'seed': seed,
                'demo_usernames': [spec[0] for spec in USER_SPECS],
                'models': {
                    label: sorted(created.get(label, [])) for label in MANIFEST_MODELS
                },
                'counts': counts,
            }
            manifest['models']['django.contrib.sessions.models.Session'] = sorted(
                session_pks_for_users(created['auth.User']),
            )
            write_manifest_atomic(manifest)
    except BaseException:
        delete_manifest()
        raise
    return manifest, counts


def _find_conflicts(present) -> list:
    conflicts = []

    def demo(label):
        return present.get(label, set())

    def collect(queryset, description):
        count = queryset.count()
        if count:
            sample = list(queryset.values_list('pk', flat=True)[:5])
            conflicts.append(f'{count} {description} (sample pks: {sample})')

    collect(
        SaleItem.objects.exclude(pk__in=demo('frontend.SaleItem')).filter(
            Q(product_id__in=demo('frontend.Product')) | Q(sale_id__in=demo('frontend.Sale'))
        ),
        'sale item(s) reference demo products or sales but are not tracked in the manifest',
    )
    collect(
        StockMovement.objects.exclude(pk__in=demo('frontend.StockMovement')).filter(
            Q(product_id__in=demo('frontend.Product'))
            | Q(sale_id__in=demo('frontend.Sale'))
            | Q(user_id__in=demo('auth.User'))
        ),
        'stock movement(s) reference demo products, sales, or users but are not tracked in the manifest',
    )
    collect(
        Payment.objects.exclude(pk__in=demo('frontend.Payment')).filter(
            Q(account_receivable_id__in=demo('frontend.AccountReceivable'))
            | Q(responsible_user_id__in=demo('auth.User'))
        ),
        'payment(s) reference demo receivables or users but are not tracked in the manifest',
    )
    collect(
        AccountReceivable.objects.exclude(pk__in=demo('frontend.AccountReceivable')).filter(
            Q(person_id__in=demo('frontend.Person')) | Q(sale_id__in=demo('frontend.Sale'))
        ),
        'receivable(s) reference demo people or sales but are not tracked in the manifest',
    )
    collect(
        Sale.objects.exclude(pk__in=demo('frontend.Sale')).filter(
            Q(customer_id__in=demo('frontend.Person')) | Q(responsible_id__in=demo('auth.User'))
        ),
        'sale(s) reference demo people or users but are not tracked in the manifest',
    )
    collect(
        Product.objects.exclude(pk__in=demo('frontend.Product')).filter(
            category_id__in=demo('frontend.Category')
        ),
        'product(s) reference demo categories but are not tracked in the manifest',
    )
    return conflicts


def clear_demo_dataset():
    if not manifest_exists():
        return {'status': 'absent'}
    manifest = read_manifest()
    if manifest is None:
        delete_manifest()
        return {'status': 'stale-manifest'}

    models_map = manifest.get('models') or {}
    unknown = sorted(label for label in models_map if label not in MODEL_REGISTRY)
    if unknown:
        raise DemoDataConflictError(
            [f'manifest references unknown model label(s) {unknown!r}; refusing to delete anything'],
        )
    user_pks = models_map.get('auth.User') or []
    bad_accounts = [
        user.username for user in User.objects.filter(pk__in=user_pks)
        if not user.username.startswith(DEMO_USER_PREFIX)
    ]
    if bad_accounts:
        raise DemoDataConflictError(
            [f'manifest would delete non-demo account(s) {bad_accounts!r}; refusing'],
        )

    present = {}
    for label, model in MODEL_REGISTRY.items():
        pks = models_map.get(label) or []
        if pks:
            present[label] = set(
                model.objects.filter(pk__in=pks).values_list('pk', flat=True),
            )

    conflicts = _find_conflicts(present)
    if conflicts:
        raise DemoDataConflictError(conflicts)

    demo_user_ids = present.get('auth.User', set())
    removed = {}
    with transaction.atomic():
        for label in DELETION_ORDER:
            pks = present.get(label)
            if not pks:
                continue
            removed[label] = MODEL_REGISTRY[label].objects.filter(pk__in=pks).delete()[0]

        onboarding = OnboardingProgress.objects.filter(user_id__in=demo_user_ids)
        removed['frontend.OnboardingProgress'] = onboarding.count()
        onboarding.delete()

        session_pks = set(present.get('django.contrib.sessions.models.Session', set()))
        session_pks.update(session_pks_for_users(demo_user_ids))
        if session_pks:
            removed['django.contrib.sessions.models.Session'] = (
                Session.objects.filter(pk__in=session_pks).delete()[0]
            )

        if demo_user_ids:
            removed['auth.User'] = User.objects.filter(
                pk__in=demo_user_ids, username__startswith=DEMO_USER_PREFIX,
            ).delete()[0]

        for label, pks in present.items():
            if pks and MODEL_REGISTRY[label].objects.filter(pk__in=pks).exists():
                raise DemoDataError(f'Cleanup verification failed for {label}; rolling back.')
        if demo_user_ids and User.objects.filter(
            pk__in=demo_user_ids, username__startswith=DEMO_USER_PREFIX,
        ).exists():
            raise DemoDataError('Cleanup verification failed for auth.User; rolling back.')

    delete_manifest()
    return {'status': 'cleared', 'removed': removed}
