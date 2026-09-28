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
    path('vendas/', views.vendas_list, name='vendas_list'),
    path('vendas/nova/', views.pdv, name='pdv'),
    path('produtos/', views.produtos, name='produtos'),
    path('estoque/', views.estoque, name='estoque'),
    path('pessoas/', views.pessoas, name='pessoas'),
    path('financeiro/', views.financeiro, name='financeiro'),
    path('relatorios/', views.relatorios, name='relatorios'),
    path('login/', views.login_view, name='login'),
]