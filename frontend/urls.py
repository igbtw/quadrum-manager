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
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('inventory/', views.inventory, name='inventory'),
    path('people/', views.people, name='people'),
    path('people/<int:pk>/edit/', views.person_edit, name='person_edit'),
    path('people/<int:pk>/delete/', views.person_delete, name='person_delete'),
    path('finance/', views.finance, name='finance'),
    path('reports/', views.reports, name='reports'),
    path('reports/export/', views.reports_export_csv, name='reports_export'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('documentation/', views.documentation, name='documentation'),
    path('documentation/<slug:topic_slug>/', views.documentation_topic, name='documentation_topic'),
    path('onboarding/complete/', views.onboarding_complete, name='onboarding_complete'),
    path('onboarding/skip/', views.onboarding_skip, name='onboarding_skip'),
    path('onboarding/step/', views.onboarding_step, name='onboarding_step'),
    path('onboarding/restart/', views.onboarding_restart, name='onboarding_restart'),
    path('preferences/per-page/', views.preferences_per_page, name='preferences_per_page'),
    path('preferences/language/', views.preferences_language, name='preferences_language'),
    path('set-language/', views.set_language, name='set_language'),
    path('api/search/', views.api_search, name='api_search'),
    path('api/pos/calculate/', views.api_pos_calculate, name='api_pos_calculate'),
    path('api/pos/finalize/', views.api_pos_finalize, name='api_pos_finalize'),
    # Legacy pre-translation paths kept as aliases for existing integrations.
    path('api/pdv/calcular/', views.api_pos_calculate, name='api_pos_calculate_legacy'),
    path('api/pdv/finalizar/', views.api_pos_finalize, name='api_pos_finalize_legacy'),
]