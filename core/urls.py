# ============================================================================
# core/urls.py
# ============================================================================

from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('clientes/', views.clientes_list, name='clientes_list'),
    path('clientes/nuevo/', views.cliente_crear, name='cliente_crear'),
    path('clientes/<int:pk>/', views.cliente_detalle, name='cliente_detalle'),
    path('clientes/<int:pk>/editar/', views.cliente_editar, name='cliente_editar'),
    
    path('facturas/', views.facturas_list, name='facturas_list'),
    path('facturas/nueva/', views.factura_crear, name='factura_crear'),
    path('facturas/<int:pk>/pagar/', views.factura_marcar_pagada, name='factura_pagar'),
    path('facturas/<int:pk>/recordatorio/', views.enviar_recordatorio, name='enviar_recordatorio'),
    path('facturas/importar-sii/', views.importar_sii, name='importar_sii'),

    path('configuracion/', views.configuracion_view, name='configuracion'),
    path('exportar/pdf/', views.exportar_pdf, name='exportar_pdf'),
    path('exportar/excel/', views.exportar_excel, name='exportar_excel'),
]