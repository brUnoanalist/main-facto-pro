from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    rut = models.CharField(max_length=20, blank=True, default='', verbose_name='RUT/DNI')
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True, default='')
    notas = models.TextField(blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def total_deuda(self):
        return sum(f.monto for f in self.facturas.filter(estado='pendiente'))

    def facturas_vencidas(self):
        return self.facturas.filter(
            estado='pendiente',
            fecha_vencimiento__lt=timezone.now().date()
        ).count()


class Factura(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
        ('impaga', 'Impaga'),
    ]

    # Obtener opciones de moneda de forma dinámica
    MONEDA_CHOICES = [
        ('CLP', 'Peso Chileno (CLP)'),
        ('USD', 'Dólar Estadounidense (USD)'),
        ('EUR', 'Euro (EUR)'),
        ('GBP', 'Libra Esterlina (GBP)'),
        ('ARS', 'Peso Argentino (ARS)'),
        ('MXN', 'Peso Mexicano (MXN)'),
        ('COP', 'Peso Colombiano (COP)'),
        ('PEN', 'Sol Peruano (PEN)'),
        ('BRL', 'Real Brasileño (BRL)'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='facturas')
    numero_factura = models.CharField(max_length=50, unique=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    monto_neto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_iva = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_exento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default='CLP')
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    estado_sii = models.CharField(max_length=50, default='Pendiente')
    tipo_dte = models.IntegerField(null=True, blank=True)
    folio = models.IntegerField(null=True, blank=True)
    importado_sii = models.BooleanField(default=False)
    descripcion = models.TextField(blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_emision']

    def __str__(self):
        return f"{self.numero_factura} - {self.cliente.nombre}"

    def dias_vencidos(self):
        if self.estado == 'pendiente' and self.fecha_vencimiento < timezone.now().date():
            return (timezone.now().date() - self.fecha_vencimiento).days
        return 0

    def proxima_vencer(self):
        if self.estado == 'pendiente':
            dias = (self.fecha_vencimiento - timezone.now().date()).days
            return 0 <= dias <= 7
        return False

    def monto_formateado(self):
        """Retorna el monto formateado según la moneda de la factura"""
        from .utils import formatear_moneda
        return formatear_moneda(self.monto, self.moneda)

    def save(self, *args, **kwargs):
        if self.estado == 'pendiente' and self.fecha_vencimiento < timezone.now().date():
            self.estado = 'vencida'
        super().save(*args, **kwargs)


class ConfiguracionRecordatorio(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    email_activo = models.BooleanField(default=True)
    whatsapp_activo = models.BooleanField(default=False)
    dias_antes_vencimiento = models.IntegerField(default=3)
    plantilla_email = models.TextField(
        default="Estimado {cliente},\n\nLe recordamos que la factura {numero} por ${monto} vence el {fecha}.\n\nSaludos."
    )
    plantilla_whatsapp = models.TextField(
        default="Hola {cliente}, recordatorio amistoso: factura {numero} por ${monto} vence el {fecha}. ¡Gracias!"
    )

    def __str__(self):
        return f"Config: {self.usuario.username}"


class HistorialRecordatorio(models.Model):
    TIPO_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]

    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='recordatorios')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    exitoso = models.BooleanField(default=True)
    mensaje_error = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_envio']

    def __str__(self):
        return f"{self.tipo} - {self.factura.numero_factura} - {self.fecha_envio}"


# ============================================================================
# core/forms.py
# ============================================================================

from django import forms
from .models import Cliente, Factura, ConfiguracionRecordatorio

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'rut', 'email', 'telefono', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUT o DNI'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }
        labels = {
            'nombre': 'Nombre Completo',
            'rut': 'RUT/DNI',
            'email': 'Email',
            'telefono': 'Teléfono',
            'notas': 'Notas',
        }


class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = ['cliente', 'numero_factura', 'monto', 'moneda', 'fecha_emision',
                  'fecha_vencimiento', 'descripcion', 'estado']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'moneda': forms.Select(attrs={'class': 'form-control'}),
            'fecha_emision': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'cliente': 'Cliente',
            'numero_factura': 'Número de Factura',
            'monto': 'Monto',
            'moneda': 'Moneda',
            'fecha_emision': 'Fecha de Emisión',
            'fecha_vencimiento': 'Fecha de Vencimiento',
            'descripcion': 'Descripción',
            'estado': 'Estado',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['cliente'].queryset = Cliente.objects.filter(usuario=user, activo=True)


class ConfiguracionForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionRecordatorio
        fields = ['email_activo', 'whatsapp_activo', 'dias_antes_vencimiento', 
                  'plantilla_email', 'plantilla_whatsapp']
        widgets = {
            'dias_antes_vencimiento': forms.NumberInput(attrs={'class': 'form-control'}),
            'plantilla_email': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'plantilla_whatsapp': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ============================================================================
# core/views.py
# ============================================================================

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
def facturas_list(request):
    facturas = Factura.objects.filter(usuario=request.user)
    
    filtro = request.GET.get('filtro', 'todas')
    if filtro == 'vencidas':
        facturas = facturas.filter(estado='vencida')
    elif filtro == 'proximas':
        facturas = facturas.filter(
            estado='pendiente',
            fecha_vencimiento__lte=timezone.now().date() + datetime.timedelta(days=7)
        )
    elif filtro == 'pagadas':
        facturas = facturas.filter(estado='pagada')
    
    return render(request, 'core/facturas_list.html', {
        'facturas': facturas,
        'filtro': filtro
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