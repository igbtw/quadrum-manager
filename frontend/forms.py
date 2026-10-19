import uuid

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from .authorization import scoped_receivables
from .models import (
    AccountReceivable, Payment, Person, Product, quantize_money,
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'code', 'category', 'price', 'cost_price', 'stock_quantity', 'minimum_stock', 'description', 'active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'code': forms.TextInput(attrs={'class': 'input'}),
            'category': forms.Select(attrs={'class': 'select'}),
            'price': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0'}),
            'cost_price': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'input', 'min': '0'}),
            'minimum_stock': forms.NumberInput(attrs={'class': 'input', 'min': '0'}),
            'description': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < Decimal('0.00'):
            raise forms.ValidationError('Price cannot be negative.')
        return price

    def clean_stock_quantity(self):
        qty = self.cleaned_data.get('stock_quantity')
        if qty is not None and qty < 0:
            raise forms.ValidationError('Stock cannot be negative.')
        return qty


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['name', 'doc_id', 'person_type', 'email', 'phone', 'active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'doc_id': forms.TextInput(attrs={'class': 'input'}),
            'person_type': forms.Select(choices=Person.PERSON_TYPES, attrs={'class': 'select'}),
            'email': forms.EmailInput(attrs={'class': 'input'}),
            'phone': forms.TextInput(attrs={'class': 'input'}),
        }

    def clean_doc_id(self):
        doc = self.cleaned_data.get('doc_id', '').strip()
        return doc


class PaymentForm(forms.ModelForm):
    """Server-authoritative payment form.

    Eligibility is derived from the ledger (cancelled or fully settled
    accounts cannot receive money), never from the displayed status alone, so
    a stale ``PAID`` row with a positive balance stays payable. The select is
    still scoped for authorization and offers only receivable choices with an
    actual outstanding balance; a forged POST naming a settled account is
    rejected in validation and again by ``register_payment``/``Payment.save``.
    """

    idempotency_key = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.HiddenInput(),
    )
    account_receivable = forms.ModelChoiceField(
        queryset=AccountReceivable.objects.none(),
        widget=forms.Select(attrs={'class': 'select'}),
        empty_label='Select an account',
    )

    def __init__(self, *args, user, **kwargs):
        """``user`` is required: choices are limited to the receivables that
        user may see (their own, or every receivable with global access)."""
        super().__init__(*args, **kwargs)
        scoped = (
            scoped_receivables(user)
            .exclude(status='CANCELLED')
            .select_related('person', 'sale')
            .prefetch_related('payments')
        )
        receivables = list(scoped)
        # Keep settled rows in the validation queryset so a stale/forged POST
        # gets an explicit "already settled" error instead of "invalid choice".
        self.fields['account_receivable'].queryset = (
            AccountReceivable.objects.filter(pk__in=[rc.pk for rc in receivables])
            .select_related('person', 'sale')
            .prefetch_related('payments')
        )
        choices = [('', 'Select an account')]
        for rc in receivables:
            remaining = rc.remaining_balance
            if remaining <= Decimal('0.00'):
                continue
            choices.append((
                rc.pk,
                f'{rc.person.name} — {rc.reference} · R$ {remaining:.2f} outstanding',
            ))
        self.fields['account_receivable'].widget.choices = choices
        if not self.is_bound:
            self.initial.setdefault('idempotency_key', uuid.uuid4().hex)

    class Meta:
        model = Payment
        fields = ['account_receivable', 'amount', 'method', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0.01'}),
            'method': forms.Select(attrs={'class': 'select'}),
            'notes': forms.Textarea(attrs={
                'class': 'textarea',
                'rows': 3,
                'placeholder': 'Optional reference',
            }),
        }

    def clean_idempotency_key(self):
        key = (self.cleaned_data.get('idempotency_key') or '').strip()
        if not key:
            return uuid.uuid4().hex
        if len(key) > 255:
            raise forms.ValidationError('Invalid payment submission key.')
        return key

    def clean_account_receivable(self):
        rc = self.cleaned_data.get('account_receivable')
        if rc is None:
            return rc
        if rc.status == 'CANCELLED':
            raise forms.ValidationError('This account is cancelled.')
        if rc.remaining_balance <= Decimal('0.00'):
            raise forms.ValidationError('This account is already settled.')
        return rc

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            return amount
        if amount < Decimal('0.01'):
            raise forms.ValidationError('Minimum value is 0.01.')
        if quantize_money(amount) != amount:
            raise forms.ValidationError('Amount must have at most two decimal places.')
        rc = self.cleaned_data.get('account_receivable')
        if rc:
            bal = rc.remaining_balance
            if bal is not None and amount > bal:
                raise forms.ValidationError('Payment exceeds remaining balance.')
        return amount


class LoginForm(AuthenticationForm):
    """Credential form. AuthenticationForm keeps failures generic and
    provides the same messages for unknown users and wrong passwords."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'input',
            'autocomplete': 'username',
            'autofocus': True,
            'placeholder': 'Your username',
        }),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'autocomplete': 'current-password',
            'placeholder': 'Your password',
        }),
    )


class RegisterForm(UserCreationForm):
    """Public self-service registration: username plus password confirmation.

    Privileged fields are intentionally absent: new accounts are always
    ordinary users (``is_staff=False``, ``is_superuser=False``). Password
    strength is enforced by Django's configured password validators.
    """

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'input',
                'autocomplete': 'username',
                'autofocus': True,
                'placeholder': 'Choose a username',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'input',
            'autocomplete': 'new-password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'input',
            'autocomplete': 'new-password',
        })
