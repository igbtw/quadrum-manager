# ponytail: minimal service layer — protects DB integrity at model/service level
# Upgrade: replace with full transaction service when concurrency/volume grows
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Product, Sale, SaleItem, StockMovement, AccountReceivable


def reduce_stock(product: Product, qty: int, user: User = None, sale: Sale = None):
    """Atomic stock reduction; raises if negative."""
    with transaction.atomic():
        # Lock row for update (DB-level) — PostgreSQL compatible
        p = Product.objects.select_for_update().get(pk=product.pk)
        if p.stock_quantity - qty < 0:
            raise ValueError(f"Estoque negativo para {p.name}: {p.stock_quantity - qty}")
        p.stock_quantity -= qty
        p.save(update_fields=['stock_quantity'])
        StockMovement.objects.create(
            product=p, movement_type='SALE', quantity=-qty,
            sale=sale, user=user, reason='Venda confirmada'
        )
        return p


def create_sale_items(sale: Sale, items_data: list, user: User = None):
    """Create SaleItem records with frozen unit_price (price at sale moment)."""
    with transaction.atomic():
        sale_items = []
        for d in items_data:
            prod = Product.objects.select_for_update().get(pk=d['product_id'])
            unit_price = Decimal(str(d.get('unit_price', prod.price)))
            item = SaleItem.objects.create(
                sale=sale, product=prod, quantity=d['quantity'],
                unit_price=unit_price,
            )
            sale_items.append(item)
            reduce_stock(prod, item.quantity, user=user, sale=sale)
        return sale_items


def finalize_sale(sale: Sale, user: User = None):
    """Confirm sale: create items if missing, reduce stock, record user, update status."""
    with transaction.atomic():
        s = Sale.objects.select_for_update().get(pk=sale.pk)
        if s.status == 'COMPLETED':
            return s
        s.status = 'COMPLETED'
        s.completed_at = timezone.now()
        s.responsible = user or s.responsible
        s.save(update_fields=['status', 'completed_at', 'responsible'])
        # If items not yet created (e.g. PDV draft), create from existing data if any
        # Receivable on account
        if s.payment_method == 'A_PRAZO' and s.customer:
            AccountReceivable.objects.get_or_create(
                sale=s,
                defaults={
                    'person': s.customer,
                    'original_amount': s.total,
                    'due_date': s.completed_at.date() if s.completed_at else timezone.now().date(),
                    'status': 'PENDING',
                }
            )
        return s
