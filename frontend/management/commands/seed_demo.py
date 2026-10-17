from django.core.management.base import BaseCommand
from frontend.models import Category, Product, Person, Sale, SaleItem, StockMovement
from decimal import Decimal
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Seed demo data for quadrum'

    def handle(self, *args, **options):
        cat, _ = Category.objects.get_or_create(name='Snacks', defaults={'description':'School snacks'})
        Product.objects.get_or_create(code='TQ01', defaults={'name':'Cheese Tapioca','category':cat,'price':Decimal('5.00'),'stock_quantity':0,'minimum_stock':5,'active':True})
        Product.objects.get_or_create(code='CX01', defaults={'name':'Chicken Snack','category':cat,'price':Decimal('4.50'),'stock_quantity':2,'minimum_stock':10,'active':True})
        p, _ = Person.objects.get_or_create(name='Juliana Dias', defaults={'person_type':'STUDENT','active':True})
        self.stdout.write(self.style.SUCCESS('Demo seed complete'))
