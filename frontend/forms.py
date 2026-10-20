import uuid

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils.translation import gettext, gettext_lazy as _
from decimal import Decimal
from .authorization import scoped_receivables
from .models import (
    AccountReceivable, Payment, Person, Product, quantize_money,
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'code', 'category', 'price', 'cost_price', 'stock_quantity', 'minimum_stock', 'description', 'active']
        labels = {
            'name': _('Product name'),
            'code': _('Code'),
            'category': _('Category'),
            'price': _('Price'),
            'cost_price': _('Cost price'),
            'stock_quantity': _('Inventory'),
            'minimum_stock': _('Minimum inventory'),
            'description': _('Description'),
            'active': _('Active'),
        }
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
            raise forms.ValidationError(_('Price cannot be negative.'))
        return price

    def clean_stock_quantity(self):
        qty = self.cleaned_data.get('stock_quantity')
        if qty is not None and qty < 0:
            raise forms.ValidationError(_('Stock cannot be negative.'))
        return qty


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['name', 'doc_id', 'person_type', 'email', 'phone', 'active']
        labels = {
            'name': _('Name'),
            'doc_id': _('Registration'),
            'person_type': _('Type'),
            'email': _('Email'),
            'phone': _('Phone'),
            'active': _('Active'),
        }
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
        empty_label=_('Select an account'),
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
        choices = [('', gettext('Select an account'))]
        for rc in receivables:
            remaining = rc.remaining_balance
            if remaining <= Decimal('0.00'):
                continue
            choices.append((
                rc.pk,
                gettext('%(name)s — %(reference)s · R$ %(balance)s outstanding') % {
                    'name': rc.person.name, 'reference': rc.reference,
                    'balance': f'{remaining:.2f}',
                },
            ))
        self.fields['account_receivable'].widget.choices = choices
        if not self.is_bound:
            self.initial.setdefault('idempotency_key', uuid.uuid4().hex)
        else:
            for name in self.fields:
                if not self.errors.get(name):
                    continue
                field = self[name]
                field.field.widget.attrs['aria-invalid'] = 'true'
                field.field.widget.attrs['aria-describedby'] = (
                    f'{field.auto_id}_error'
                )

    class Meta:
        model = Payment
        fields = ['account_receivable', 'amount', 'method', 'notes']
        labels = {
            'account_receivable': _('Account'),
            'amount': _('Amount'),
            'method': _('Payment method'),
            'notes': _('Notes'),
        }
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0.01'}),
            'method': forms.Select(attrs={'class': 'select'}),
            'notes': forms.Textarea(attrs={
                'class': 'textarea',
                'rows': 3,
                'placeholder': _('Optional reference'),
            }),
        }

    def clean_idempotency_key(self):
        key = (self.cleaned_data.get('idempotency_key') or '').strip()
        if not key:
            return uuid.uuid4().hex
        if len(key) > 255:
            raise forms.ValidationError(_('Invalid payment submission key.'))
        return key

    def clean_account_receivable(self):
        rc = self.cleaned_data.get('account_receivable')
        if rc is None:
            return rc
        if rc.status == 'CANCELLED':
            raise forms.ValidationError(_('This account is cancelled.'))
        if rc.remaining_balance <= Decimal('0.00'):
            raise forms.ValidationError(_('This account is already settled.'))
        return rc

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            return amount
        if amount < Decimal('0.01'):
            raise forms.ValidationError(_('Minimum value is 0.01.'))
        if quantize_money(amount) != amount:
            raise forms.ValidationError(_('Amount must have at most two decimal places.'))
        rc = self.cleaned_data.get('account_receivable')
        if rc:
            bal = rc.remaining_balance
            if bal is not None and amount > bal:
                raise forms.ValidationError(_('Payment exceeds remaining balance.'))
        return amount


class LoginForm(AuthenticationForm):
    """Credential form. AuthenticationForm keeps failures generic and
    provides the same messages for unknown users and wrong passwords."""

    username = forms.CharField(
        max_length=150,
        label=_('Username'),
        widget=forms.TextInput(attrs={
            'class': 'input',
            'autocomplete': 'username',
            'autofocus': True,
            'placeholder': _('Your username'),
        }),
    )
    password = forms.CharField(
        strip=False,
        label=_('Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'autocomplete': 'current-password',
            'placeholder': _('Your password'),
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
                'placeholder': _('Choose a username'),
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
