from django.core.management.base import BaseCommand
from frontend.models import Category, Product, Person, Sale, SaleItem, StockMovement
from decimal import Decimal
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Seed demo data for CantinaOS'

    def handle(self, *args, **options):
        cat, _ = Category.objects.get_or_create(name='Lanches', defaults={'description':'Lanches da cantina'})
        Product.objects.get_or_create(code='TQ01', defaults={'name':'Tapioca de Queijo','category':cat,'price':Decimal('5.00'),'stock_quantity':0,'minimum_stock':5,'active':True})
        Product.objects.get_or_create(code='CX01', defaults={'name':'Coxinha','category':cat,'price':Decimal('4.50'),'stock_quantity':2,'minimum_stock':10,'active':True})
        p, _ = Person.objects.get_or_create(name='Juliana Dias', defaults={'person_type':'ALUNO','active':True})
        self.stdout.write(self.style.SUCCESS('Demo seed complete'))
