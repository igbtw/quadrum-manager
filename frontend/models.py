from django.db import models, transaction
from django.db.models import Sum
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'

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
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
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

    @property
    def estoque(self):
        return self.stock_quantity

    @property
    def estoque_minimo(self):
        return self.minimum_stock

    @property
    def nome(self):
        return self.name


class Person(models.Model):
    PERSON_TYPES = [
        ('ALUNO', 'Aluno'),
        ('PROFESSOR', 'Professor'),
        ('FUNCIONARIO', 'Funcionário'),
        ('VISITANTE', 'Visitante'),
    ]
    name = models.CharField(max_length=200)
    doc_id = models.CharField(max_length=50, blank=True, verbose_name='Registro/Doc')
    person_type = models.CharField(max_length=20, choices=PERSON_TYPES, default='ALUNO')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'

    def __str__(self):
        return self.name


class Sale(models.Model):
    SALE_STATUSES = [
        ('PENDING', 'Pendente'),
        ('COMPLETED', 'Concluída'),
        ('CANCELLED', 'Cancelada'),
    ]
    PAYMENT_METHODS = [
        ('DINHEIRO', 'Dinheiro'),
        ('DEBITO', 'Débito'),
        ('CREDITO', 'Crédito'),
        ('PIX', 'PIX'),
        ('A_PRAZO', 'A prazo'),
    ]
    code = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    status = models.CharField(max_length=20, choices=SALE_STATUSES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='DINHEIRO')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'

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
        verbose_name = 'Item de Venda'
        verbose_name_plural = 'Itens de Venda'

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(str(self.quantity)) * self.unit_price
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('ENTRY', 'Entrada'),
        ('EXIT', 'Saída'),
        ('ADJUSTMENT', 'Ajuste'),
        ('SALE', 'Venda'),
        ('RETURN', 'Devolução'),
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
        verbose_name = 'Movimento de Estoque'
        verbose_name_plural = 'Movimentos de Estoque'


class AccountReceivable(models.Model):
    RECEIVABLE_STATUSES = [
        ('PENDING', 'Pendente'),
        ('PARTIAL', 'Parcial'),
        ('PAID', 'Pago'),
        ('OVERDUE', 'Vencido'),
        ('CANCELLED', 'Cancelado'),
    ]
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='receivables')
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='receivable')
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=RECEIVABLE_STATUSES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Conta a Receber'
        verbose_name_plural = 'Contas a Receber'

    @property
    def amount_paid(self):
        result = self.payments.aggregate(s=Sum('amount'))['s']
        return result or Decimal('0.00')

    @property
    def remaining_balance(self):
        paid = self.amount_paid or Decimal('0.00')
        return max(self.original_amount - paid, Decimal('0.00'))

    def update_status(self):
        from django.utils import timezone
        if self.remaining_balance <= 0:
            self.status = 'PAID'
        elif self.due_date < timezone.now().date() and self.remaining_balance > 0:
            self.status = 'OVERDUE'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        else:
            self.status = 'PENDING'


def register_payment(account_receivable: AccountReceivable, amount: Decimal, method: str = 'DINHEIRO', user: User = None, notes: str = '') -> Payment:
    """Transactional payment registration; recalculates receivable afterwards."""
    with transaction.atomic():
        rc = AccountReceivable.objects.select_for_update().get(pk=account_receivable.pk)
        if amount > rc.remaining_balance:
            raise ValueError('Pagamento excede saldo restante.')
        p = Payment.objects.create(
            account_receivable=rc, amount=amount, method=method,
            responsible_user=user, notes=notes
        )
        rc.update_status()
        rc.save(update_fields=['status'])
        return p


class Payment(models.Model):
    account_receivable = models.ForeignKey(AccountReceivable, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateField(auto_now_add=True)
    method = models.CharField(max_length=20, choices=[('DINHEIRO','Dinheiro'),('DEBITO','Débito'),('CREDITO','Crédito'),('PIX','PIX'),('TRANSFERENCIA','Transferência')], default='DINHEIRO')
    responsible_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'

    def clean(self):
        try:
            if self.account_receivable_id and isinstance(self.amount, Decimal):
                rc = AccountReceivable.objects.get(pk=self.account_receivable_id)
                bal = rc.remaining_balance
                if bal is not None and self.amount > bal:
                    from django.core.exceptions import ValidationError
                    raise ValidationError('Pagamento não pode exceder saldo restante.')
        except TypeError:
            pass  # form clean handles validation; avoid crash during instance init

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_amount = None
        if not is_new and self.pk:
            try:
                old = Payment.objects.get(pk=self.pk)
                old_amount = old.amount
            except Payment.DoesNotExist:
                old_amount = None
        super().save(*args, **kwargs)
        # Guarded hook: only recalc when amount actually changed or new record
        if is_new or old_amount != self.amount:
            self.account_receivable.refresh_from_db()
            self.account_receivable.update_status()
            self.account_receivable.save(update_fields=['status'])
