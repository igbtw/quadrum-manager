"""
URL configuration for frontend app.
"""
from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('sales/', views.vendas_list, name='vendas_list'),
    path('sales/new/', views.pdv, name='pdv'),
    path('products/', views.produtos, name='produtos'),
    path('inventory/', views.estoque, name='estoque'),
    path('people/', views.pessoas, name='pessoas'),
    path('finance/', views.financeiro, name='financeiro'),
    path('reports/', views.relatorios, name='relatorios'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/pdv/calcular/', views.api_pdv_calcular, name='api_pdv_calcular'),
    path('api/pdv/finalizar/', views.api_pdv_finalizar, name='api_pdv_finalizar'),
]