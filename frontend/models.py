import time

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, OperationalError, models, transaction
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, ROUND_HALF_UP


# BRL currency policy: two decimal places, half-up rounding on the final cent.
# Every financial comparison and displayed total goes through these helpers so
# SQLite's float-derived aggregates (e.g. Decimal('80.3000000000000') or
# Decimal('0E-13')) cannot leak excessive precision into decisions.
CURRENCY_QUANTUM = Decimal('0.01')
CURRENCY_ROUNDING = ROUND_HALF_UP
MIN_RECEIVABLE_AMOUNT = Decimal('0.01')


def quantize_money(value):
    """Normalize a monetary value to BRL currency precision (2 decimals)."""
    if value is None:
        return Decimal('0.00')
    return Decimal(value).quantize(CURRENCY_QUANTUM, rounding=CURRENCY_ROUNDING)


def remaining_after(original_amount, paid_amount):
    """Outstanding balance at currency precision, floored at zero."""
    outstanding = quantize_money(Decimal(original_amount) - Decimal(paid_amount))
    return outstanding if outstanding > Decimal('0.00') else Decimal('0.00')


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True, null=True)
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    minimum_stock = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        constraints = [
            models.CheckConstraint(check=models.Q(stock_quantity__gte=0), name='stock_non_negative'),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name

    @property
    def is_low_stock(self):
        return self.active and self.stock_quantity <= self.minimum_stock and self.stock_quantity > 0

    @property
    def is_out_of_stock(self):
        return self.active and self.stock_quantity == 0


class Person(models.Model):
    PERSON_TYPES = [
        ('STUDENT', _('Student')),
        ('TEACHER', _('Teacher')),
        ('STAFF', _('Staff')),
        ('VISITOR', _('Visitor')),
    ]
    name = models.CharField(max_length=200)
    doc_id = models.CharField(max_length=50, blank=True, verbose_name=_('Record/Doc'))
    person_type = models.CharField(max_length=20, choices=PERSON_TYPES, default='STUDENT')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Person')
        verbose_name_plural = _('People')
        permissions = [
            (
                'manage_master_data',
                _('Can manage master data (people, products, categories)'),
            ),
        ]

    def __str__(self):
        return self.name


class Sale(models.Model):
    SALE_STATUSES = [
        ('PENDING', _('Pending')),
        ('COMPLETED', _('Completed')),
        ('CANCELLED', _('Cancelled')),
    ]
    PAYMENT_METHODS = [
        ('CASH', _('Cash')),
        ('DEBIT', _('Debit')),
        ('CREDIT', _('Credit')),
        ('PIX', 'PIX'),
        ('ON_ACCOUNT', _('On Account')),
    ]
    code = models.CharField(max_length=20, unique=True, blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True, blank=True, null=True, db_index=True, default=None)
    request_fingerprint = models.CharField(max_length=255, blank=True, null=True, db_index=True, default=None)
    customer = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    status = models.CharField(max_length=20, choices=SALE_STATUSES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Sale')
        verbose_name_plural = _('Sales')
        permissions = [
            (
                'view_all_responsible_data',
                _('Can view every responsible user\'s sales, receivables and payments'),
            ),
        ]

    def save(self, *args, **kwargs):
        # Prevent double insert/update conflict when Django passes force_insert
        if self.pk and not self.code:
            kwargs.pop('force_insert', None)
            self.code = f"VEN-{self.pk:06d}"
            super(Sale, self).save(update_fields=['code'], *args, **kwargs)
            return
        if not self.pk:
            super().save(*args, **kwargs)
            if not self.code and self.pk:
                self.code = f"VEN-{self.pk:06d}"
                kwargs.pop('force_insert', None)
                super(Sale, self).save(update_fields=['code'], *args, **kwargs)
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.customer or '—'}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = _('Sale Item')
        verbose_name_plural = _('Sale Items')

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(str(self.quantity)) * self.unit_price
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('ENTRY', _('Entry')),
        ('EXIT', _('Exit')),
        ('ADJUSTMENT', _('Adjustment')),
        ('SALE', _('Sale')),
        ('RETURN', _('Return')),
    ]
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, default='ADJUSTMENT')
    quantity = models.IntegerField()
    reason = models.CharField(max_length=200, blank=True)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Stock Movement')
        verbose_name_plural = _('Stock Movements')


class AccountReceivable(models.Model):
    RECEIVABLE_STATUSES = [
        ('PENDING', _('Pending')),
        ('PARTIAL', _('Partial')),
        ('PAID', _('Paid')),
        ('OVERDUE', _('Overdue')),
        ('CANCELLED', _('Cancelled')),
    ]
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='receivables')
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='receivable')
    original_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(MIN_RECEIVABLE_AMOUNT)],
    )
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=RECEIVABLE_STATUSES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Account Receivable')
        verbose_name_plural = _('Accounts Receivable')
        constraints = [
            models.CheckConstraint(
                check=models.Q(original_amount__gte=MIN_RECEIVABLE_AMOUNT),
                name='receivable_amount_minimum',
            ),
        ]

    def __str__(self):
        due = self.due_date.strftime('%m/%d/%Y') if self.due_date else '—'
        return f'{self.person.name} — R$ {self.original_amount:.2f} (due {due})'

    @property
    def reference(self):
        """Human reference used in payment selectors and diagnostics."""
        if self.sale_id:
            return self.sale.code
        return f'AR-{self.pk:05d}' if self.pk else 'AR'

    @property
    def amount_paid(self):
        """Exact sum of recorded payments, normalized to currency precision.

        Computed in Python from each stored Decimal instead of SQL ``SUM``:
        SQLite aggregates DecimalField through binary floats, which produces
        values like ``Decimal('80.3000000000000')``/``Decimal('0E-13')``.
        """
        paid = sum(
            (payment.amount for payment in self.payments.all()),
            Decimal('0.00'),
        )
        return quantize_money(paid)

    @property
    def remaining_balance(self):
        return remaining_after(self.original_amount, self.amount_paid)

    def update_status(self):
        if self.status == 'CANCELLED':
            return
        paid = self.amount_paid
        balance = remaining_after(self.original_amount, paid)
        if balance <= Decimal('0.00'):
            self.status = 'PAID'
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = 'OVERDUE'
        elif paid > Decimal('0.00'):
            self.status = 'PARTIAL'
        else:
            self.status = 'PENDING'


class PaymentConflictError(ValueError):
    """Raised when an idempotency key is reused for a different payment."""


PAYMENT_RETRY_ATTEMPTS = 4
PAYMENT_RETRY_DELAYS = (0.05, 0.10, 0.20)


def validate_payment_amount(amount):
    """Enforce positive, two-decimal BRL payment amounts."""
    if not isinstance(amount, Decimal):
        raise ValueError(_('Payment amount must be a decimal value.'))
    if amount < MIN_RECEIVABLE_AMOUNT:
        raise ValueError(_('Payment amount must be at least R$ 0.01.'))
    if quantize_money(amount) != amount:
        raise ValueError(_('Payment amount must have at most two decimal places.'))


def _lock_receivable(receivable_pk):
    """Lock the receivable for the payment critical section.

    ``select_for_update()`` is a no-op on SQLite, so the follow-up UPDATE
    forces SQLite's database-level write lock *before* the payment ledger is
    read. On PostgreSQL the SELECT ... FOR UPDATE row lock serializes the same
    block. Either way the check-then-write sequence is protected.
    """
    rc = AccountReceivable.objects.select_for_update().get(pk=receivable_pk)
    # Writing a value (updated_at) acquires SQLite's write lock; without it a
    # deferred transaction could read a stale ledger before upgrading.
    AccountReceivable.objects.filter(pk=receivable_pk).update(updated_at=timezone.now())
    rc.refresh_from_db()
    return rc


def _available_balance(rc, exclude_payment_pk=None):
    """Authoritative outstanding balance, optionally crediting one payment.

    ``exclude_payment_pk`` is used when validating an existing payment edit:
    its current amount is part of ``amount_paid`` but must not count against
    the value being saved.
    """
    payments = rc.payments.all()
    if exclude_payment_pk is not None:
        payments = payments.exclude(pk=exclude_payment_pk)
    paid = quantize_money(sum((p.amount for p in payments), Decimal('0.00')))
    return remaining_after(rc.original_amount, paid)


def _assert_payment_matches_request(existing, receivable_pk, amount, method, user):
    if (
        existing.account_receivable_id != receivable_pk
        or quantize_money(existing.amount) != quantize_money(amount)
        or existing.method != method
        or existing.responsible_user_id != (user.pk if user else None)
    ):
        raise PaymentConflictError(
            _('This payment submission key was already used for a different request.')
        )


def _register_payment_once(receivable_pk, amount, method, user, notes, idempotency_key):
    try:
        with transaction.atomic():
            rc = _lock_receivable(receivable_pk)
            if idempotency_key:
                existing = (
                    Payment.objects.filter(idempotency_key=idempotency_key)
                    .select_related('account_receivable')
                    .first()
                )
                if existing is not None:
                    # A replay of an already-committed request resolves to the
                    # original result instead of charging the account again.
                    _assert_payment_matches_request(
                        existing, receivable_pk, amount, method, user,
                    )
                    return existing
            if rc.status == 'CANCELLED':
                raise ValueError(_('Cannot register payment for a cancelled receivable.'))
            balance = rc.remaining_balance
            if balance <= Decimal('0.00'):
                raise ValueError(_('This account is already settled.'))
            if quantize_money(amount) > balance:
                raise ValueError(_('Payment exceeds remaining balance.'))
            payment = Payment.objects.create(
                account_receivable=rc, amount=quantize_money(amount), method=method,
                responsible_user=user, notes=notes, idempotency_key=idempotency_key,
            )
            rc.update_status()
            rc.save(update_fields=['status'])
            return payment
    except IntegrityError:
        # Unique key raced with another transaction. The atomic block has
        # rolled back; resolve the winner outside the broken transaction.
        if not idempotency_key:
            raise
        existing = (
            Payment.objects.filter(idempotency_key=idempotency_key)
            .select_related('account_receivable')
            .first()
        )
        if existing is None:
            raise
        _assert_payment_matches_request(existing, receivable_pk, amount, method, user)
        return existing


def register_payment(
    account_receivable: AccountReceivable,
    amount: Decimal,
    method: str = 'CASH',
    user: User = None,
    notes: str = '',
    idempotency_key: str = None,
) -> Payment:
    """Transactional, idempotent payment registration.

    Eligibility is recalculated from the authoritative ledger inside the
    locked critical section: cancelled and settled receivables reject new
    payments, and an amount above the outstanding balance is refused. SQLite
    write-lock conflicts are retried from a fresh transaction; a retry never
    reuses a half-open ``atomic()`` block.
    """
    validate_payment_amount(amount)
    if idempotency_key:
        idempotency_key = str(idempotency_key).strip() or None
        if idempotency_key and len(idempotency_key) > 255:
            raise ValueError(_('Invalid payment submission key.'))
    receivable_pk = account_receivable.pk
    for attempt in range(PAYMENT_RETRY_ATTEMPTS):
        try:
            return _register_payment_once(
                receivable_pk, amount, method, user, notes, idempotency_key,
            )
        except OperationalError as exc:
            message = str(exc).lower()
            retryable = 'locked' in message or 'busy' in message
            if not retryable or attempt == PAYMENT_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(PAYMENT_RETRY_DELAYS[min(attempt, len(PAYMENT_RETRY_DELAYS) - 1)])


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('CASH', _('Cash')),
        ('DEBIT', _('Debit')),
        ('CREDIT', _('Credit')),
        ('PIX', 'PIX'),
        ('TRANSFER', _('Transfer')),
    ]
    account_receivable = models.ForeignKey(AccountReceivable, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateField(auto_now_add=True)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH')
    responsible_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Server-generated submission token (see register_payment). Nullable so
    # historical payments and demo-data seeding remain compatible.
    idempotency_key = models.CharField(
        max_length=255, unique=True, null=True, blank=True, default=None,
    )

    class Meta:
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')

    def _old_row(self):
        if self._state.adding or not self.pk:
            return None
        return Payment.objects.filter(pk=self.pk).first()

    def _is_new_or_reassigned(self):
        """True when this row would be inserted or moved to another receivable."""
        if self._state.adding:
            return True
        old = self._old_row()
        return old is not None and old.account_receivable_id != self.account_receivable_id

    def clean(self):
        if not self.account_receivable_id:
            return
        rc = AccountReceivable.objects.get(pk=self.account_receivable_id)
        old = self._old_row()
        reassigned = old is None or old.account_receivable_id != self.account_receivable_id
        if reassigned and rc.status == 'CANCELLED':
            raise ValidationError(_('Cannot register payment for a cancelled receivable.'))
        if not isinstance(self.amount, Decimal):
            raise ValidationError(_('Payment amount must be a decimal value.'))
        try:
            validate_payment_amount(self.amount)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        exclude_pk = self.pk if (old is not None and not reassigned) else None
        available = _available_balance(rc, exclude_payment_pk=exclude_pk)
        if reassigned and available <= Decimal('0.00'):
            raise ValidationError(_('This account is already settled.'))
        if quantize_money(self.amount) > available:
            raise ValidationError(_('Payment cannot exceed remaining balance.'))

    def _guard_and_save(self, old, *args, **kwargs):
        """Validate against locked ledger state, then persist."""
        is_new = old is None
        rc_changed = is_new or old.account_receivable_id != self.account_receivable_id
        try:
            validate_payment_amount(self.amount)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        with transaction.atomic():
            rc = _lock_receivable(self.account_receivable_id)
            if rc_changed and rc.status == 'CANCELLED':
                raise ValidationError(_('Cannot register payment for a cancelled receivable.'))
            exclude_pk = None if rc_changed else self.pk
            available = _available_balance(rc, exclude_payment_pk=exclude_pk)
            if rc_changed and available <= Decimal('0.00'):
                raise ValidationError(_('This account is already settled.'))
            if quantize_money(self.amount) > available:
                raise ValidationError(_('Payment cannot exceed remaining balance.'))
            super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        # ORM entry points bypass clean()/full_clean(); guard them here. The
        # ledger is read only after the receivable lock is acquired so a
        # concurrent payment cannot slip between validation and insert.
        old = self._old_row()
        old_amount = old.amount if old is not None else None
        if old is None or old.account_receivable_id != self.account_receivable_id or old_amount != self.amount:
            self._guard_and_save(old, *args, **kwargs)
        else:
            super().save(*args, **kwargs)
        # Guarded hook: only recalc when amount actually changed or new record
        if old is None or old_amount != self.amount:
            self.account_receivable.refresh_from_db()
            self.account_receivable.update_status()
            self.account_receivable.save(update_fields=['status'])


class OnboardingProgress(models.Model):
    """Per-user first-run guide state; rows are created for new registrations."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='onboarding')
    current_step = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Onboarding Progress')
        verbose_name_plural = _('Onboarding Progress')

    def __str__(self):
        state = 'pending'
        if self.completed_at:
            state = 'completed'
        elif self.skipped_at:
            state = 'skipped'
        return f'{self.user.username} — {state}'

    @property
    def is_pending(self):
        return self.completed_at is None and self.skipped_at is None


class UserProfile(models.Model):
    """Minimal per-user application preferences.

    Currently only the UI language; kept deliberately small. The post_save
    signal creates a default row for new users, while pre-existing users
    without a profile safely default to English and get a row only when they
    explicitly save a language from Preferences.
    """

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('pt-br', 'Português (Brasil)'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    language = models.CharField(
        max_length=10, choices=LANGUAGE_CHOICES, default='en',
    )

    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')

    def __str__(self):
        return f'{self.user.username} — {self.language}'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create the default profile once, for newly created accounts only."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
