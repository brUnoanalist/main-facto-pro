from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from django.http import HttpResponse
from .models import Cliente, Factura, ConfiguracionRecordatorio, HistorialRecordatorio
from .forms import ClienteForm, FacturaForm, ConfiguracionForm
from .utils import generar_pdf_reporte, generar_excel_reporte, enviar_recordatorio_email
import datetime

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            ConfiguracionRecordatorio.objects.create(usuario=user)
            login(request, user)
            messages.success(request, '¡Registro exitoso!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    clientes = Cliente.objects.filter(usuario=request.user, activo=True)
    facturas = Factura.objects.filter(usuario=request.user)
    
    # Actualizar estados de facturas vencidas
    facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lt=timezone.now().date()
    ).update(estado='vencida')
    
    facturas_vencidas = facturas.filter(estado='vencida')
    facturas_pendientes = facturas.filter(estado='pendiente')
    facturas_proximas = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lte=timezone.now().date() + datetime.timedelta(days=7),
        fecha_vencimiento__gte=timezone.now().date()
    )
    
    total_pendiente = facturas.filter(estado__in=['pendiente', 'vencida']).aggregate(
        total=Sum('monto')
    )['total'] or 0
    
    context = {
        'total_clientes': clientes.count(),
        'total_facturas': facturas.count(),
        'facturas_vencidas': facturas_vencidas.count(),
        'facturas_pendientes':facturas_pendientes.count(),
        'facturas_proximas': facturas_proximas.count(),
        'total_pendiente': total_pendiente,
        'ultimas_facturas': facturas[:10],
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def clientes_list(request):
    clientes = Cliente.objects.filter(usuario=request.user, activo=True)
    return render(request, 'core/clientes_list.html', {'clientes': clientes})

@login_required
def cliente_detalle(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)
    facturas = cliente.facturas.all()
    return render(request, 'core/cliente_detalle.html', {
        'cliente': cliente,
        'facturas': facturas
    })

@login_required
def cliente_crear(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.usuario = request.user
            cliente.save()
            messages.success(request, 'Cliente creado exitosamente')
            return redirect('clientes_list')
    else:
        form = ClienteForm()
    return render(request, 'core/cliente_form.html', {'form': form, 'titulo': 'Nuevo Cliente'})

@login_required
def cliente_editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado exitosamente')
            return redirect('cliente_detalle', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'core/cliente_form.html', {'form': form, 'titulo': 'Editar Cliente'})

@login_required
def facturas_list(request):
    todas_facturas = Factura.objects.filter(usuario=request.user)

    # Calcular conteos para las tarjetas
    total_facturas = todas_facturas.count()
    facturas_vencidas = todas_facturas.filter(estado='vencida').count()
    facturas_pagadas = todas_facturas.filter(estado='pagada').count()
    facturas_pendientes = todas_facturas.filter(estado='pendiente').count()

    # Filtrar según la selección del usuario
    filtro = request.GET.get('filtro', 'todas')
    if filtro == 'vencidas':
        facturas = todas_facturas.filter(estado='vencida')
    elif filtro == 'proximas':
        facturas = todas_facturas.filter(
            estado='pendiente',
            fecha_vencimiento__lte=timezone.now().date() + datetime.timedelta(days=7)
        )
    elif filtro == 'pagadas':
        facturas = todas_facturas.filter(estado='pagada')
    else:
        facturas = todas_facturas

    return render(request, 'core/facturas_list.html', {
        'facturas': facturas,
        'filtro': filtro,
        'total_facturas': total_facturas,
        'facturas_vencidas': facturas_vencidas,
        'facturas_pagadas': facturas_pagadas,
        'facturas_pendientes': facturas_pendientes,
    })

@login_required
def factura_crear(request):
    if request.method == 'POST':
        form = FacturaForm(request.POST, user=request.user)
        if form.is_valid():
            factura = form.save(commit=False)
            factura.usuario = request.user
            factura.save()
            messages.success(request, 'Factura creada exitosamente')
            return redirect('facturas_list')
    else:
        form = FacturaForm(user=request.user)
    return render(request, 'core/factura_form.html', {'form': form, 'titulo': 'Nueva Factura'})

@login_required
def factura_marcar_pagada(request, pk):
    factura = get_object_or_404(Factura, pk=pk, usuario=request.user)
    factura.estado = 'pagada'
    factura.fecha_pago = timezone.now().date()
    factura.save()
    messages.success(request, 'Factura marcada como pagada')
    return redirect('facturas_list')

@login_required
def configuracion_view(request):
    config, created = ConfiguracionRecordatorio.objects.get_or_create(usuario=request.user)
    
    if request.method == 'POST':
        form = ConfiguracionForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada')
            return redirect('dashboard')
    else:
        form = ConfiguracionForm(instance=config)
    
    return render(request, 'core/configuracion.html', {'form': form})

@login_required
def enviar_recordatorio(request, pk):
    factura = get_object_or_404(Factura, pk=pk, usuario=request.user)
    config = ConfiguracionRecordatorio.objects.get(usuario=request.user)
    
    if config.email_activo:
        exitoso = enviar_recordatorio_email(factura, config)
        HistorialRecordatorio.objects.create(
            factura=factura,
            tipo='email',
            exitoso=exitoso
        )
        if exitoso:
            messages.success(request, 'Recordatorio enviado por email')
        else:
            messages.error(request, 'Error al enviar recordatorio')
    
    return redirect('facturas_list')

@login_required
def exportar_pdf(request):
    facturas = Factura.objects.filter(
        usuario=request.user,
        estado__in=['pendiente', 'vencida']
    )
    response = generar_pdf_reporte(request.user, facturas)
    return response

@login_required
def exportar_excel(request):
    facturas = Factura.objects.filter(
        usuario=request.user,
        estado__in=['pendiente', 'vencida']
    )
    response = generar_excel_reporte(request.user, facturas)
    return response
