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
    path('sales/', views.sales_list, name='sales_list'),
    path('sales/new/', views.point_of_sale, name='point_of_sale'),
    path('products/', views.product_list, name='products'),
    path('inventory/', views.inventory, name='inventory'),
    path('people/', views.people, name='people'),
    path('finance/', views.finance, name='finance'),
    path('reports/', views.reports, name='reports'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/pdv/calcular/', views.api_pos_calculate, name='api_pos_calculate'),
    path('api/pdv/finalizar/', views.api_pos_finalize, name='api_pos_finalize'),
]