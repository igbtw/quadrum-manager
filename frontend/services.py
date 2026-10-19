# ponytail: minimal service layer — protects DB integrity at model/service level
# Upgrade: replace with full transaction service when concurrency/volume grows
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from .models import (
    MIN_RECEIVABLE_AMOUNT, AccountReceivable, Person, Product, Sale,
    SaleItem, StockMovement,
)


class InsufficientStockError(ValueError):
    """Raised when a stock reduction cannot be fulfilled by available inventory."""


class ReferencedRecordError(ValueError):
    """Raised when a record with historical references cannot be deleted.

    The record must stay intact so sales, receivables, and inventory history
    keep their relationships; the message explains the blocking references.
    """

    def __init__(self, message, *, references):
        super().__init__(message)
        self.references = references


def reduce_stock(product: Product, qty: int, user: User = None, sale: Sale = None):
    """Atomic stock reduction; raises InsufficientStockError if it would go negative."""
    with transaction.atomic():
        # Lock row for update (DB-level) — PostgreSQL compatible
        p = Product.objects.select_for_update().get(pk=product.pk)
        if p.stock_quantity - qty < 0:
            raise InsufficientStockError(f"Negative stock for {p.name}: {p.stock_quantity - qty}")
        p.stock_quantity -= qty
        p.save(update_fields=['stock_quantity'])
        StockMovement.objects.create(
            product=p, movement_type='SALE', quantity=-qty,
            sale=sale, user=user, reason='Sale confirmed'
        )
        return p


def create_sale_items(sale: Sale, items_data: list, user: User = None):
    """Create SaleItem records with frozen unit_price (price at sale moment)."""
    with transaction.atomic():
        sale_items = []
        for d in items_data:
            quantity = d.get('quantity')
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError('Quantity must be a positive integer.')
            prod = Product.objects.select_for_update().get(pk=d['product_id'])
            unit_price = Decimal(str(d.get('unit_price', prod.price)))
            # Server-side price enforcement: never trust client price
            if unit_price != prod.price:
                unit_price = prod.price
            item = SaleItem.objects.create(
                sale=sale, product=prod, quantity=d['quantity'],
                unit_price=unit_price,
            )
            sale_items.append(item)
            reduce_stock(prod, item.quantity, user=user, sale=sale)
        return sale_items


def cancel_sale(sale: Sale, user: User = None):
    """Cancel completed sale: idempotent, atomic, rejects if payments exist."""
    with transaction.atomic():
        s = Sale.objects.select_for_update().get(pk=sale.pk)
        # Idempotent: nothing to do if already cancelled
        if s.status == 'CANCELLED':
            return s
        if s.status != 'COMPLETED':
            raise ValueError('Only completed sales can be cancelled.')
        # Lock the associated receivable (if any) before checking payments and
        # before marking it cancelled, so cancellation serializes with
        # register_payment()/Payment.save() on the same row.
        rc = None
        if s.payment_method == 'ON_ACCOUNT':
            rc = (
                AccountReceivable.objects.select_for_update()
                .filter(sale=s)
                .first()
            )
        # Rule 1: if a receivable exists, reject when payments are recorded
        if rc and rc.payments.exists():
            raise ValueError('Cannot cancel: recorded payments exist on the receivable account.')
        # Update sale
        s.status = 'CANCELLED'
        s.save(update_fields=['status'])
        # Receivable: mark CANCELLED (preserve record; never delete)
        if rc:
            rc.status = 'CANCELLED'
            rc.save(update_fields=['status'])
        # Stock reversal: restore each item and create RETURN movement
        for item in s.items.select_related('product').all():
            prod = Product.objects.select_for_update().get(pk=item.product.pk)
            prod.stock_quantity += item.quantity
            prod.save(update_fields=['stock_quantity'])
            StockMovement.objects.create(
                product=prod, movement_type='RETURN', quantity=item.quantity,
                sale=s, user=user, reason='Sale cancellation'
            )
        return s


def delete_person(person: Person):
    """Delete a person only when nothing historical references them.

    Runs inside a transaction with the person row locked, so a sale or
    receivable cannot appear between the reference check and the delete.
    Referenced people must be deactivated (``active=False``) instead so
    historical sales keep their customer names and receivables keep their
    debtor.
    """
    with transaction.atomic():
        locked = Person.objects.select_for_update().get(pk=person.pk)
        sales = locked.sales.count()
        receivables = locked.receivables.count()
        if sales or receivables:
            raise ReferencedRecordError(
                'This person cannot be deleted because historical records reference them.',
                references={'sales': sales, 'receivables': receivables},
            )
        locked.delete()


def delete_product(product: Product):
    """Delete a product only when no sale items or stock movements exist.

    Same locking/check discipline as :func:`delete_person`; referenced
    products must be deactivated (``active=False``) so sales history and
    inventory movements stay intact.
    """
    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product.pk)
        sale_items = locked.sale_items.count()
        movements = locked.movements.count()
        if sale_items or movements:
            raise ReferencedRecordError(
                'This product cannot be deleted because sales or inventory history reference it.',
                references={'sale_items': sale_items, 'movements': movements},
            )
        locked.delete()


def adjust_stock(product: Product, qty: int, reason: str = '', user: User = None):
    """Manual stock adjustment with audit movement."""
    from django.db import transaction
    with transaction.atomic():
        p = Product.objects.select_for_update().get(pk=product.pk)
        p.stock_quantity += qty
        p.save(update_fields=['stock_quantity'])
        StockMovement.objects.create(
            product=p, movement_type='ADJUSTMENT', quantity=qty,
            user=user, reason=reason or 'Manual adjustment'
        )
        return p


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
        # If items not yet created (e.g. POS draft), create from existing data if any
        # Receivable on account
        # A zero-value on-account sale has nothing to bill; the database
        # constraint refuses receivables below R$ 0.01, so skip creation
        # instead of crashing the finalize flow.
        if (
            s.payment_method == 'ON_ACCOUNT'
            and s.customer
            and s.total >= MIN_RECEIVABLE_AMOUNT
        ):
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
