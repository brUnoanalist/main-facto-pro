from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Q, Sum, Count, Case, When, F
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Cliente, Factura, ConfiguracionRecordatorio, HistorialRecordatorio
from .forms import ClienteForm, FacturaForm, ConfiguracionForm
from .utils import generar_pdf_reporte, generar_excel_reporte, enviar_recordatorio_email
import datetime


def actualizar_estados_cobranza(facturas):
    """
    Actualiza los estados de cobranza de las facturas pendientes.
    Esta función debe llamarse en cada vista que muestre facturas.
    """
    for factura in facturas.filter(estado='pendiente'):
        factura.actualizar_estado_cobranza()
        factura.save()

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = request.POST.get('email', '')
            user.save()
            ConfiguracionRecordatorio.objects.create(usuario=user)
            login(request, user, backend='core.backends.EmailBackend')
            messages.success(request, '¡Registro exitoso!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    error = None
    if request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            error = 'Correo electrónico o contraseña incorrectos'
    return render(request, 'core/login.html', {'error': error})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    clientes = Cliente.objects.filter(usuario=request.user, activo=True)

    # Actualizar estados de cobranza primero
    facturas_pendientes = Factura.objects.filter(usuario=request.user, estado='pendiente')
    for factura in facturas_pendientes:
        factura.actualizar_estado_cobranza()
        factura.save()

    # Refrescar el QuerySet después de actualizar
    facturas = Factura.objects.filter(usuario=request.user)

    # ========== SISTEMA DE ALERTAS INTELIGENTES ==========
    alertas = []

    # Alerta 1: Facturas vencidas este mes
    inicio_mes = timezone.now().date().replace(day=1)
    facturas_vencidas_mes = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__gte=inicio_mes,
        fecha_vencimiento__lt=timezone.now().date()
    ).count()
    if facturas_vencidas_mes > 0:
        alertas.append({
            'tipo': 'danger',
            'icono': 'exclamation-triangle-fill',
            'mensaje': f'Tienes {facturas_vencidas_mes} facturas vencidas este mes',
            'accion': 'facturas_list',
            'filtro': 'vencidas'
        })

    # Alerta 2: Facturas por vencer en los próximos 7 días
    proxima_semana = timezone.now().date() + datetime.timedelta(days=7)
    facturas_por_vencer_pronto = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__gte=timezone.now().date(),
        fecha_vencimiento__lte=proxima_semana
    ).count()
    if facturas_por_vencer_pronto > 0:
        alertas.append({
            'tipo': 'warning',
            'icono': 'clock-fill',
            'mensaje': f'{facturas_por_vencer_pronto} facturas vencen en los próximos 7 días',
            'accion': 'facturas_list',
            'filtro': 'por_vencer'
        })

    # Alerta 3: Facturas en mora (+30 días vencidas)
    facturas_mora_count = facturas.filter(estado='pendiente', estado_cobranza='mora').count()
    if facturas_mora_count > 0:
        monto_mora = facturas.filter(estado='pendiente', estado_cobranza='mora').aggregate(
            total=Sum(Case(
                When(monto_pendiente__gt=0, then=F('monto_pendiente')),
                default=F('monto_total')
            ))
        )['total'] or 0
        alertas.append({
            'tipo': 'danger',
            'icono': 'hourglass-split',
            'mensaje': f'{facturas_mora_count} facturas en mora por ${monto_mora:,.0f}',
            'accion': 'facturas_list',
            'filtro': 'mora'
        })

    # Alerta 4: Concentración de clientes (análisis 80/20)
    if facturas.filter(estado='pendiente').exists():
        total_pendiente_global = facturas.filter(estado='pendiente').aggregate(
            total=Sum(Case(
                When(monto_pendiente__gt=0, then=F('monto_pendiente')),
                default=F('monto_total')
            ))
        )['total'] or 0

        if total_pendiente_global > 0:
            # Top 5 clientes con más deuda
            top_clientes = facturas.filter(estado='pendiente').values('cliente__nombre').annotate(
                deuda=Sum(Case(
                    When(monto_pendiente__gt=0, then=F('monto_pendiente')),
                    default=F('monto_total')
                ))
            ).order_by('-deuda')[:5]

            deuda_top5 = sum(c['deuda'] for c in top_clientes)
            porcentaje_concentracion = (deuda_top5 / total_pendiente_global) * 100 if total_pendiente_global > 0 else 0

            if porcentaje_concentracion >= 70:
                alertas.append({
                    'tipo': 'info',
                    'icono': 'pie-chart-fill',
                    'mensaje': f'5 clientes concentran el {porcentaje_concentracion:.0f}% de tu cartera por cobrar',
                    'accion': None,
                    'filtro': None
                })

    # Alerta 5: Facturas sin fecha de vencimiento o con datos incompletos
    facturas_sin_vencimiento = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__isnull=True
    ).count()
    if facturas_sin_vencimiento > 0:
        alertas.append({
            'tipo': 'secondary',
            'icono': 'question-circle-fill',
            'mensaje': f'{facturas_sin_vencimiento} facturas sin fecha de vencimiento',
            'accion': 'facturas_list',
            'filtro': 'pendientes'
        })

    # Alerta 6: Facturas incobrables (+90 días)
    facturas_incobrables_count = facturas.filter(estado='pendiente', estado_cobranza='incobrable').count()
    if facturas_incobrables_count > 0:
        alertas.append({
            'tipo': 'dark',
            'icono': 'x-circle-fill',
            'mensaje': f'{facturas_incobrables_count} facturas podrían ser incobrables (+90 días)',
            'accion': 'facturas_list',
            'filtro': 'incobrables'
        })

    # Contadores por estado principal
    facturas_pendientes = facturas.filter(estado='pendiente').count()
    facturas_pagadas = facturas.filter(estado='pagada').count()
    facturas_anuladas = facturas.filter(estado='anulada').count()

    # Contadores por estado de cobranza (solo pendientes)
    # Forzar evaluación del QuerySet para obtener datos actualizados
    facturas_vigentes = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='vigente').count()
    facturas_por_vencer = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='por_vencer').count()
    facturas_vencidas = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='vencida').count()
    facturas_en_mora = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='mora').count()
    facturas_incobrables = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='incobrable').count()

    # Facturas próximas a vencer (7 días o menos)
    facturas_proximas = facturas.filter(
        estado='pendiente',
        estado_cobranza='por_vencer'
    )

    # Total por cobrar - suma directa de monto_pendiente de facturas pendientes
    total_pendiente = facturas.filter(estado='pendiente').aggregate(
        total=Sum('monto_pendiente')
    )['total'] or 0

    # Total pagado - suma directa de monto_pagado de todas las facturas
    total_pagado = facturas.aggregate(
        total=Sum('monto_pagado')
    )['total'] or 0

    # Total facturado
    total_facturado = facturas.aggregate(
        total=Sum('monto_total')
    )['total'] or 0

    # Total de facturas con pago parcial
    facturas_pago_parcial = facturas.filter(
        estado='pendiente',
        monto_pagado__gt=0,
        monto_pendiente__gt=0
    ).count()

    # Monto total de pagos parciales recibidos
    monto_pagos_parciales = facturas.filter(
        estado='pendiente',
        monto_pagado__gt=0
    ).aggregate(total=Sum('monto_pagado'))['total'] or 0

    # Montos por estado de cobranza para gráficos
    # Usar monto_pendiente directamente ya que todas son facturas pendientes
    monto_vigentes = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='vigente').aggregate(
        total=Sum('monto_pendiente')
    )['total'] or 0

    monto_por_vencer = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='por_vencer').aggregate(
        total=Sum('monto_pendiente')
    )['total'] or 0

    monto_vencidas = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='vencida').aggregate(
        total=Sum('monto_pendiente')
    )['total'] or 0

    monto_en_mora = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='mora').aggregate(
        total=Sum('monto_pendiente')
    )['total'] or 0

    monto_incobrables = Factura.objects.filter(usuario=request.user, estado='pendiente', estado_cobranza='incobrable').aggregate(
        total=Sum('monto_pendiente')
    )['total'] or 0

    monto_pagadas = facturas.filter(estado='pagada').aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    # Facturas por mes para gráfico de línea (últimos 12 meses con datos)
    facturas_por_mes = facturas.annotate(
        mes=TruncMonth('fecha_emision')
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')

    # Limitar a los últimos 12 meses con datos
    facturas_por_mes_list = list(facturas_por_mes)[-12:]

    # Preparar datos para el gráfico
    import json
    meses_labels = []
    meses_data = []
    for item in facturas_por_mes_list:
        meses_labels.append(item['mes'].strftime('%b %Y'))
        meses_data.append(item['total'])

    # ========== MAPA DE VENCIMIENTO ==========
    hoy = timezone.now().date()

    # 0-30 días vencidas
    vencidas_0_30 = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lt=hoy,
        fecha_vencimiento__gte=hoy - datetime.timedelta(days=30)
    )
    monto_0_30 = vencidas_0_30.aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    # 31-60 días vencidas
    vencidas_31_60 = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lt=hoy - datetime.timedelta(days=30),
        fecha_vencimiento__gte=hoy - datetime.timedelta(days=60)
    )
    monto_31_60 = vencidas_31_60.aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    # 61-90 días vencidas
    vencidas_61_90 = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lt=hoy - datetime.timedelta(days=60),
        fecha_vencimiento__gte=hoy - datetime.timedelta(days=90)
    )
    monto_61_90 = vencidas_61_90.aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    # +90 días vencidas
    vencidas_90_mas = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lt=hoy - datetime.timedelta(days=90)
    )
    monto_90_mas = vencidas_90_mas.aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    context = {
        'total_clientes': clientes.count(),
        'total_facturas': facturas.count(),
        # Estados principales
        'facturas_pendientes': facturas_pendientes,
        'facturas_pagadas': facturas_pagadas,
        # Estados de cobranza (solo para pendientes)
        'facturas_vigentes': facturas_vigentes,
        'facturas_por_vencer': facturas_por_vencer,
        'facturas_vencidas': facturas_vencidas,
        'facturas_en_mora': facturas_en_mora,
        'facturas_incobrables': facturas_incobrables,
        # Métricas de pagos parciales
        'facturas_pago_parcial': facturas_pago_parcial,
        'monto_pagos_parciales': float(monto_pagos_parciales),
        'total_pagado': float(total_pagado),
        'total_facturado': float(total_facturado),
        # Montos por estado de cobranza
        'monto_vigentes': int(monto_vigentes),
        'monto_por_vencer': int(monto_por_vencer),
        'monto_vencidas': int(monto_vencidas),
        'monto_en_mora': int(monto_en_mora),
        'monto_incobrables': int(monto_incobrables),
        'monto_pagadas': float(monto_pagadas),
        # Total pendiente (suma de todos los estados de cobranza)
        'total_pendiente': float(total_pendiente),
        # Alertas inteligentes
        'alertas': alertas,
        # Mapa de vencimiento
        'vencidas_0_30': vencidas_0_30.count(),
        'monto_0_30': float(monto_0_30),
        'vencidas_31_60': vencidas_31_60.count(),
        'monto_31_60': float(monto_31_60),
        'vencidas_61_90': vencidas_61_90.count(),
        'monto_61_90': float(monto_61_90),
        'vencidas_90_mas': vencidas_90_mas.count(),
        'monto_90_mas': float(monto_90_mas),
        # Otros datos
        'ultimas_facturas': facturas.order_by('-fecha_emision')[:10],
        'meses_labels': json.dumps(meses_labels),
        'meses_data': json.dumps(meses_data),
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def clientes_list(request):
    clientes = Cliente.objects.filter(usuario=request.user, activo=True)

    # Actualizar estados de cobranza de todas las facturas
    facturas = Factura.objects.filter(usuario=request.user)
    actualizar_estados_cobranza(facturas)

    # Búsqueda
    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        clientes = clientes.filter(
            Q(nombre__icontains=busqueda) |
            Q(rut__icontains=busqueda) |
            Q(email__icontains=busqueda)
        )

    # Ordenamiento
    orden = request.GET.get('orden', 'nombre')
    if orden in ['nombre', '-nombre', 'rut', '-rut', '-fecha_registro']:
        clientes = clientes.order_by(orden)

    # Calcular métricas para cada cliente
    clientes_con_metricas = []
    for cliente in clientes:
        facturas_cliente = cliente.facturas.all()
        facturas_vencidas = facturas_cliente.filter(
            estado='pendiente',
            estado_cobranza__in=['vencida', 'mora', 'incobrable']
        ).count()
        total_deuda = facturas_cliente.filter(estado='pendiente').aggregate(
            total=Sum(Case(
                When(monto_pendiente__gt=0, then=F('monto_pendiente')),
                default=F('monto_total')
            ))
        )['total'] or 0
        total_facturas = facturas_cliente.count()
        facturas_pagadas = facturas_cliente.filter(estado='pagada').count()

        cliente.facturas_vencidas = facturas_vencidas
        cliente.total_deuda = total_deuda
        cliente.total_facturas = total_facturas
        cliente.facturas_pagadas = facturas_pagadas
        clientes_con_metricas.append(cliente)

    # Dashboard de clientes
    total_clientes = Cliente.objects.filter(usuario=request.user, activo=True).count()
    clientes_con_deuda = 0
    clientes_al_dia = 0
    total_por_cobrar = 0

    for c in Cliente.objects.filter(usuario=request.user, activo=True):
        deuda = c.facturas.filter(estado='pendiente').aggregate(
            total=Sum(Case(
                When(monto_pendiente__gt=0, then=F('monto_pendiente')),
                default=F('monto_total')
            ))
        )['total'] or 0
        if deuda > 0:
            clientes_con_deuda += 1
            total_por_cobrar += deuda
        else:
            clientes_al_dia += 1

    # Paginación
    paginator = Paginator(clientes_con_metricas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/clientes_list.html', {
        'clientes': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
        'orden': orden,
        'total_clientes': total_clientes,
        'clientes_con_deuda': clientes_con_deuda,
        'clientes_al_dia': clientes_al_dia,
        'total_por_cobrar': total_por_cobrar,
    })

@login_required
def cliente_detalle(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)

    # Actualizar estados de cobranza
    facturas = cliente.facturas.all()
    actualizar_estados_cobranza(facturas)

    # Métricas del cliente
    total_facturas = facturas.count()
    facturas_pagadas = facturas.filter(estado='pagada').count()
    facturas_pendientes = facturas.filter(estado='pendiente').count()
    facturas_vencidas = facturas.filter(
        estado='pendiente',
        estado_cobranza__in=['vencida', 'mora', 'incobrable']
    ).count()

    # Montos
    total_facturado = facturas.aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    total_pagado = facturas.filter(estado='pagada').aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    total_pendiente = facturas.filter(estado='pendiente').aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    # Por estado de cobranza
    monto_vigente = facturas.filter(estado='pendiente', estado_cobranza='vigente').aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    monto_por_vencer = facturas.filter(estado='pendiente', estado_cobranza='por_vencer').aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    monto_vencido = facturas.filter(
        estado='pendiente',
        estado_cobranza__in=['vencida', 'mora', 'incobrable']
    ).aggregate(
        total=Sum(Case(
            When(monto_pendiente__gt=0, then=F('monto_pendiente')),
            default=F('monto_total')
        ))
    )['total'] or 0

    # Tasa de pago
    tasa_pago = 0
    if total_facturado > 0:
        tasa_pago = round((total_pagado / total_facturado) * 100)

    return render(request, 'core/cliente_detalle.html', {
        'cliente': cliente,
        'facturas': facturas,
        'total_facturas': total_facturas,
        'facturas_pagadas': facturas_pagadas,
        'facturas_pendientes': facturas_pendientes,
        'facturas_vencidas': facturas_vencidas,
        'total_facturado': total_facturado,
        'total_pagado': total_pagado,
        'total_pendiente': total_pendiente,
        'monto_vigente': monto_vigente,
        'monto_por_vencer': monto_por_vencer,
        'monto_vencido': monto_vencido,
        'tasa_pago': tasa_pago,
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

    # Actualizar estados de cobranza
    actualizar_estados_cobranza(todas_facturas)

    # Calcular conteos para las tarjetas - Estados principales
    total_facturas = todas_facturas.count()
    facturas_pagadas = todas_facturas.filter(estado='pagada').count()
    facturas_pendientes = todas_facturas.filter(estado='pendiente').count()

    # Conteos por estado de cobranza
    facturas_vigentes = todas_facturas.filter(estado='pendiente', estado_cobranza='vigente').count()
    facturas_por_vencer = todas_facturas.filter(estado='pendiente', estado_cobranza='por_vencer').count()
    facturas_vencidas = todas_facturas.filter(estado='pendiente', estado_cobranza='vencida').count()
    facturas_en_mora = todas_facturas.filter(estado='pendiente', estado_cobranza='mora').count()
    facturas_incobrables = todas_facturas.filter(estado='pendiente', estado_cobranza='incobrable').count()

    # Filtrar según la selección del usuario
    filtro = request.GET.get('filtro', 'todas')
    if filtro == 'vigentes':
        facturas = todas_facturas.filter(estado='pendiente', estado_cobranza='vigente')
    elif filtro == 'por_vencer':
        facturas = todas_facturas.filter(estado='pendiente', estado_cobranza='por_vencer')
    elif filtro == 'vencidas':
        facturas = todas_facturas.filter(estado='pendiente', estado_cobranza='vencida')
    elif filtro == 'mora':
        facturas = todas_facturas.filter(estado='pendiente', estado_cobranza='mora')
    elif filtro == 'incobrables':
        facturas = todas_facturas.filter(estado='pendiente', estado_cobranza='incobrable')
    elif filtro == 'pagadas':
        facturas = todas_facturas.filter(estado='pagada')
    elif filtro == 'pendientes':
        facturas = todas_facturas.filter(estado='pendiente')
    else:
        facturas = todas_facturas

    # ========== BÚSQUEDA ==========
    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        facturas = facturas.filter(
            Q(numero_factura__icontains=busqueda) |
            Q(cliente__nombre__icontains=busqueda) |
            Q(cliente__rut__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )

    # ========== ORDENAMIENTO ==========
    orden = request.GET.get('orden', '-fecha_emision')
    ordenes_validos = ['fecha_emision', '-fecha_emision', 'fecha_vencimiento', '-fecha_vencimiento',
                      'monto_total', '-monto_total', 'cliente__nombre', '-cliente__nombre']
    if orden in ordenes_validos:
        facturas = facturas.order_by(orden)

    # ========== PAGINACIÓN ==========
    paginator = Paginator(facturas, 25)  # 25 facturas por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/facturas_list.html', {
        'facturas': page_obj,
        'page_obj': page_obj,
        'filtro': filtro,
        'busqueda': busqueda,
        'orden': orden,
        'total_facturas': total_facturas,
        'facturas_pendientes': facturas_pendientes,
        'facturas_pagadas': facturas_pagadas,
        # Estados de cobranza
        'facturas_vigentes': facturas_vigentes,
        'facturas_por_vencer': facturas_por_vencer,
        'facturas_vencidas': facturas_vencidas,
        'facturas_en_mora': facturas_en_mora,
        'facturas_incobrables': facturas_incobrables,
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
    # Actualizar montos: todo pasa a pagado
    factura.monto_pagado = factura.monto_total or factura.monto or 0
    factura.monto_pendiente = 0
    factura.estado_cobranza = None
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
    facturas = Factura.objects.filter(usuario=request.user)

    # Actualizar estados de cobranza
    actualizar_estados_cobranza(facturas)

    # Exportar solo facturas pendientes
    facturas = facturas.filter(estado='pendiente')
    response = generar_pdf_reporte(request.user, facturas)
    return response

@login_required
def exportar_excel(request):
    facturas = Factura.objects.filter(usuario=request.user)

    # Actualizar estados de cobranza
    actualizar_estados_cobranza(facturas)

    # Exportar solo facturas pendientes
    facturas = facturas.filter(estado='pendiente')
    response = generar_excel_reporte(request.user, facturas)
    return response

@login_required
def importar_sii(request):
    """Vista para importar facturas desde archivos CSV o XML del SII"""
    import csv
    import io
    import xml.etree.ElementTree as ET
    from decimal import Decimal
    from datetime import datetime as dt

    # Funciones auxiliares para parseo
    def parse_decimal(value_str):
        if not value_str or value_str == '0':
            return Decimal('0')
        cleaned = str(value_str).strip()
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        return Decimal(cleaned)

    def parse_date(date_str):
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = ['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']
        for fmt in formats:
            try:
                return dt.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f'Formato de fecha no reconocido: {date_str}')

    def parse_xml_sii(xml_content):
        """Parsea XML del SII (LibroCompraVenta) y extrae los detalles de facturas"""
        # Namespace del SII
        ns = {'sii': 'http://www.sii.cl/SiiDte'}

        root = ET.fromstring(xml_content)

        # Buscar elementos Detalle (con o sin namespace)
        detalles = root.findall('.//sii:Detalle', ns)
        if not detalles:
            detalles = root.findall('.//Detalle')

        facturas_data = []
        notas_credito = []

        for detalle in detalles:
            # Función auxiliar para obtener texto de elemento
            def get_text(tag):
                elem = detalle.find(f'sii:{tag}', ns)
                if elem is None:
                    elem = detalle.find(tag)
                return elem.text.strip() if elem is not None and elem.text else ''

            tipo_doc = get_text('TpoDoc')
            folio = get_text('FolioDoc')
            fecha_doc = get_text('FchDoc')
            rut_receptor = get_text('RUTRecep')
            razon_social = get_text('RznSocRecep')
            monto_neto = get_text('MntNeto')
            monto_iva = get_text('MntIVA')
            monto_total = get_text('MntTotal')

            if not folio or not rut_receptor:
                continue

            # Nota de crédito - guardar para aplicar después
            if tipo_doc == '61':
                folio_ref = get_text('FolioDocRef')
                monto_nc = monto_total.replace('.', '').replace(',', '').replace('-', '') if monto_total else '0'
                notas_credito.append({
                    'folio_ref': folio_ref,
                    'monto': int(monto_nc) if monto_nc else 0,
                })
                continue

            # Nota de débito - ignorar por ahora
            if tipo_doc == '56':
                continue

            # Facturas (33, 34, etc.)
            facturas_data.append({
                'folio': folio,
                'tipo_dte': tipo_doc,
                'fecha_emision': fecha_doc,
                'rut': rut_receptor,
                'razon_social': razon_social or f'Cliente {rut_receptor}',
                'monto_neto': monto_neto,
                'monto_iva': monto_iva,
                'monto_total': monto_total,
                'nc_aplicadas': 0,
            })

        # Aplicar notas de crédito a las facturas referenciadas
        for nc in notas_credito:
            for factura in facturas_data:
                if factura['folio'] == nc['folio_ref']:
                    factura['nc_aplicadas'] += nc['monto']
                    break

        return facturas_data

    if request.method == 'POST':
        # Paso 2: Confirmar importación
        if 'confirmar_importacion' in request.POST:
            csv_data = request.session.get('csv_preview_data')
            if not csv_data:
                messages.error(request, 'No hay datos para importar. Por favor, sube el archivo nuevamente.')
                return redirect('importar_sii')

            facturas_creadas = 0
            facturas_actualizadas = 0
            errores = []

            for item in csv_data:
                try:
                    # Buscar o crear cliente
                    cliente, created = Cliente.objects.get_or_create(
                        rut=item['rut'],
                        usuario=request.user,
                        defaults={
                            'nombre': item['razon_social'],
                            'email': f'{item["rut"].replace("-", "").replace(".", "")}@temp.com',
                            'activo': True
                        }
                    )

                    if not created and cliente.nombre != item['razon_social']:
                        cliente.nombre = item['razon_social']
                        cliente.save()

                    # Crear o actualizar factura
                    factura, factura_created = Factura.objects.update_or_create(
                        numero_factura=item['folio'],
                        usuario=request.user,
                        defaults={
                            'cliente': cliente,
                            'monto': Decimal(str(item['monto_total'])),
                            'monto_total': Decimal(str(item['monto_total'])),
                            'monto_pagado': Decimal(str(item['monto_pagado'])),
                            'monto_pendiente': Decimal(str(item['monto_pendiente'])),
                            'fecha_emision': dt.strptime(item['fecha_emision'], '%Y-%m-%d').date(),
                            'fecha_vencimiento': dt.strptime(item['fecha_vencimiento'], '%Y-%m-%d').date() if item['fecha_vencimiento'] else None,
                            'fecha_pago': dt.strptime(item['fecha_pago'], '%Y-%m-%d').date() if item.get('fecha_pago') else None,
                            'estado': item['estado'],
                            'descripcion': f'Importado desde SII - {item["razon_social"]}',
                        }
                    )

                    if factura_created:
                        facturas_creadas += 1
                    else:
                        facturas_actualizadas += 1

                except Exception as e:
                    errores.append(f'Folio {item["folio"]}: {str(e)}')

            # Limpiar datos de sesión
            if 'csv_preview_data' in request.session:
                del request.session['csv_preview_data']

            mensaje_exito = f'Importación completada: {facturas_creadas} facturas creadas, {facturas_actualizadas} actualizadas'
            messages.success(request, mensaje_exito)

            if errores:
                for error in errores[:5]:
                    messages.warning(request, error)
                if len(errores) > 5:
                    messages.warning(request, f'... y {len(errores) - 5} errores más')

            return redirect('facturas_list')

        # Paso 1: Subir archivo y mostrar vista previa
        uploaded_file = request.FILES.get('csv_file')

        if not uploaded_file:
            messages.error(request, 'Por favor, selecciona un archivo CSV o XML')
            return redirect('importar_sii')

        file_name = uploaded_file.name.lower()
        if not file_name.endswith('.csv') and not file_name.endswith('.xml'):
            messages.error(request, 'El archivo debe ser CSV o XML')
            return redirect('importar_sii')

        try:
            # Decodificar el archivo
            decoded_file = uploaded_file.read().decode('utf-8-sig')

            preview_data = []
            errores = []
            total_monto = Decimal('0')
            total_pendiente = Decimal('0')

            # Determinar si es XML o CSV
            is_xml = file_name.endswith('.xml')

            if is_xml:
                # Procesar XML del SII
                xml_facturas = parse_xml_sii(decoded_file)

                for row_num, item in enumerate(xml_facturas, start=1):
                    try:
                        numero_factura = item['folio']
                        rut_emisor = item['rut']
                        razon_social = item['razon_social']
                        fecha_emision_str = item['fecha_emision']
                        monto_total_str = item['monto_total'] or '0'

                        monto_total = parse_decimal(monto_total_str)
                        fecha_emision = parse_date(fecha_emision_str) if fecha_emision_str else timezone.now().date()
                        fecha_vencimiento = fecha_emision + datetime.timedelta(days=30)

                        # Aplicar notas de crédito al monto pendiente
                        nc_aplicadas = Decimal(str(item.get('nc_aplicadas', 0)))
                        monto_pendiente = monto_total - nc_aplicadas
                        monto_pagado = nc_aplicadas

                        # Si la NC cubre todo el monto, marcar como pagada
                        if monto_pendiente <= 0:
                            estado_factura = 'pagada'
                            monto_pendiente = Decimal('0')
                            monto_pagado = monto_total
                        else:
                            estado_factura = 'pendiente'

                        existe = Factura.objects.filter(
                            numero_factura=numero_factura,
                            usuario=request.user
                        ).exists()

                        preview_item = {
                            'row_num': row_num,
                            'folio': numero_factura,
                            'rut': rut_emisor,
                            'razon_social': razon_social,
                            'fecha_emision': fecha_emision.strftime('%Y-%m-%d'),
                            'fecha_vencimiento': fecha_vencimiento.strftime('%Y-%m-%d'),
                            'monto_total': float(monto_total),
                            'monto_pendiente': float(monto_pendiente),
                            'monto_pagado': float(monto_pagado),
                            'estado': estado_factura,
                            'fecha_pago': None,
                            'existe': existe,
                            'valido': True
                        }
                        preview_data.append(preview_item)
                        total_monto += monto_total
                        total_pendiente += monto_pendiente

                    except Exception as e:
                        errores.append({
                            'row_num': row_num,
                            'error': str(e)
                        })
                        continue
            else:
                # Procesar CSV
                io_string = io.StringIO(decoded_file)

                # Detectar el delimitador automáticamente
                sample = io_string.read(1024)
                io_string.seek(0)
                delimiter = ';' if sample.count(';') > sample.count(',') else ','

                csv_reader = csv.DictReader(io_string, delimiter=delimiter)

                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        # Leer datos directamente del CSV
                        numero_factura = row.get('folio', '').strip()
                        tipo_dte_str = row.get('tipo_dte', '33').strip() or '33'
                        fecha_emision_str = row.get('fecha_emision', '').strip()
                        fecha_vencimiento_str = row.get('fecha_vencimiento', '').strip()
                        rut_emisor = row.get('rut_receptor', '').strip()
                        razon_social = row.get('razon_social_receptor', '').strip()
                        monto_total_str = row.get('monto_total', '0').strip() or '0'
                        monto_pendiente_str = row.get('monto_pendiente', '0').strip() or '0'
                        estado_pago_str = row.get('estado_pago', '').strip()

                        # Para compatibilidad con otros formatos
                        if not numero_factura:
                            numero_factura = row.get('Folio', row.get('Número Documento', '')).strip()
                        if not rut_emisor:
                            rut_emisor = row.get('RUT Receptor', row.get('RUTReceptor', row.get('RUT Emisor', ''))).strip()
                        if not razon_social:
                            razon_social = row.get('Razón Social Receptor', row.get('RazonSocialReceptor', row.get('Razón Social', ''))).strip()
                        if not fecha_emision_str:
                            fecha_emision_str = row.get('Fecha Emisión', row.get('FechaEmision', row.get('Fecha', ''))).strip()
                        if not monto_total_str or monto_total_str == '0':
                            monto_total_str = row.get('Monto Total', row.get('MontoTotal', row.get('Total', '0'))).strip() or '0'

                        # Validar datos mínimos requeridos
                        if not numero_factura:
                            errores.append(f'Fila {row_num}: Falta el folio de la factura')
                            continue
                        if not rut_emisor:
                            errores.append(f'Fila {row_num}: Falta el RUT del receptor')
                            continue
                        if not razon_social:
                            errores.append(f'Fila {row_num}: Falta la razón social del receptor')
                            continue
                        if not fecha_emision_str:
                            errores.append(f'Fila {row_num}: Falta la fecha de emisión')
                            continue

                        monto_total = parse_decimal(monto_total_str)
                        fecha_emision = parse_date(fecha_emision_str) if fecha_emision_str else timezone.now().date()

                        if fecha_vencimiento_str:
                            fecha_vencimiento = parse_date(fecha_vencimiento_str)
                        else:
                            fecha_vencimiento = fecha_emision + datetime.timedelta(days=30)

                        monto_pendiente = parse_decimal(monto_pendiente_str)
                        monto_pagado = monto_total - monto_pendiente if monto_total > 0 else Decimal('0')

                        estado_factura = 'pendiente'
                        fecha_pago = None

                        if estado_pago_str:
                            estado_lower = estado_pago_str.strip().lower()
                            if 'pago total' in estado_lower or estado_lower == 'pagada' or estado_lower == 'pagado':
                                estado_factura = 'pagada'
                                fecha_pago = timezone.now().date()
                            elif 'pago parcial' in estado_lower or 'parcial' in estado_lower:
                                estado_factura = 'pendiente'

                        if monto_pendiente == 0:
                            estado_factura = 'pagada'
                            fecha_pago = timezone.now().date() if not fecha_pago else fecha_pago
                            monto_pagado = monto_total

                        existe = Factura.objects.filter(
                            numero_factura=numero_factura,
                            usuario=request.user
                        ).exists()

                        preview_item = {
                            'row_num': row_num,
                            'folio': numero_factura,
                            'rut': rut_emisor,
                            'razon_social': razon_social,
                            'fecha_emision': fecha_emision.strftime('%Y-%m-%d'),
                            'fecha_vencimiento': fecha_vencimiento.strftime('%Y-%m-%d') if fecha_vencimiento else '',
                            'monto_total': float(monto_total),
                            'monto_pendiente': float(monto_pendiente),
                            'monto_pagado': float(monto_pagado),
                            'estado': estado_factura,
                            'fecha_pago': fecha_pago.strftime('%Y-%m-%d') if fecha_pago else None,
                            'existe': existe,
                            'valido': True
                        }
                        preview_data.append(preview_item)
                        total_monto += monto_total
                        total_pendiente += monto_pendiente

                    except Exception as e:
                        errores.append({
                            'row_num': row_num,
                            'error': str(e)
                        })
                        continue

            # Guardar datos en sesión para confirmar
            request.session['csv_preview_data'] = preview_data

            # Contar estadísticas
            nuevas = len([p for p in preview_data if not p['existe']])
            actualizadas = len([p for p in preview_data if p['existe']])
            pagadas = len([p for p in preview_data if p['estado'] == 'pagada'])
            pendientes = len([p for p in preview_data if p['estado'] == 'pendiente'])

            return render(request, 'core/importar_sii.html', {
                'preview': True,
                'preview_data': preview_data,
                'errores': errores,
                'total_facturas': len(preview_data),
                'nuevas': nuevas,
                'actualizadas': actualizadas,
                'pagadas': pagadas,
                'pendientes': pendientes,
                'total_monto': float(total_monto),
                'total_pendiente': float(total_pendiente),
            })

        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            return redirect('importar_sii')

    return render(request, 'core/importar_sii.html')


def error_404(request, exception):
    """Vista personalizada para errores 404"""
    return render(request, '404.html', status=404)


def error_500(request):
    """Vista personalizada para errores 500"""
    return render(request, '500.html', status=500)
