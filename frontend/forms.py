from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
from .models import Product, Person, Payment, AccountReceivable


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'code', 'category', 'price', 'cost_price', 'stock_quantity', 'minimum_stock', 'description', 'active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'category': forms.Select(),
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
            'person_type': forms.Select(choices=Person.PERSON_TYPES),
        }

    def clean_doc_id(self):
        doc = self.cleaned_data.get('doc_id', '').strip()
        return doc


class PaymentForm(forms.ModelForm):
    account_receivable = forms.ModelChoiceField(
        queryset=AccountReceivable.objects.exclude(status='CANCELLED'))

    class Meta:
        model = Payment
        fields = ['account_receivable', 'amount', 'method', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
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
