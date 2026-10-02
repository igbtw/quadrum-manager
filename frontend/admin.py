from django.contrib import admin
from .models import Category, Product, Person, Sale, SaleItem, StockMovement, AccountReceivable, Payment

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'active', 'created_at']
    search_fields = ['name']
    list_filter = ['active']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'price', 'stock_quantity', 'minimum_stock', 'active', 'is_low_stock', 'is_out_of_stock']
    search_fields = ['name', 'code']
    list_filter = ['category', 'active']
    ordering = ['name']

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'doc_id', 'person_type', 'active']
    search_fields = ['name', 'doc_id']
    list_filter = ['person_type', 'active']

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['code', 'customer', 'status', 'total', 'created_at', 'completed_at']
    list_filter = ['status', 'payment_method']
    search_fields = ['code', 'customer__name']
    ordering = ['-created_at']

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'subtotal']

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'quantity', 'sale', 'created_at']
    list_filter = ['movement_type']

@admin.register(AccountReceivable)
class AccountReceivableAdmin(admin.ModelAdmin):
    list_display = ['person', 'sale', 'original_amount', 'due_date', 'status', 'remaining_balance']
    list_filter = ['status']
    search_fields = ['person__name']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['account_receivable', 'amount', 'payment_date', 'method']
