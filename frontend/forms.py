from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from .authorization import scoped_receivables
from .models import Product, Person, Payment, AccountReceivable


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
    account_receivable = forms.ModelChoiceField(
        queryset=AccountReceivable.objects.exclude(status='CANCELLED').select_related('person'),
        widget=forms.Select(attrs={'class': 'select'}),
        empty_label='Select an account',
    )

    def __init__(self, *args, user, **kwargs):
        """``user`` is required: choices are limited to the receivables that
        user may see (their own, or every receivable with global access)."""
        super().__init__(*args, **kwargs)
        self.fields['account_receivable'].queryset = (
            scoped_receivables(user).exclude(status='CANCELLED').select_related('person')
        )

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

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount < Decimal('0.01'):
            raise forms.ValidationError('Minimum value is 0.01.')
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
