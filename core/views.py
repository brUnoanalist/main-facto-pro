from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.db.models import Q, Sum, Count, Case, When, F
from django.db.models.functions import TruncMonth
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

    facturas_vencidas = facturas.filter(estado='vencida').count()
    facturas_pendientes = facturas.filter(estado='pendiente').count()
    facturas_impagas = facturas.filter(estado='impaga').count()
    facturas_pagadas = facturas.filter(estado='pagada').count()

    facturas_proximas = facturas.filter(
        estado='pendiente',
        fecha_vencimiento__lte=timezone.now().date() + datetime.timedelta(days=7),
        fecha_vencimiento__gte=timezone.now().date()
    )

    total_pendiente = facturas.filter(estado__in=['pendiente', 'vencida', 'impaga']).aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    # Montos por estado para gráfico de barras
    monto_vencidas = facturas.filter(estado='vencida').aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    monto_impagas = facturas.filter(estado='impaga').aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    monto_pendientes = facturas.filter(estado='pendiente').aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    monto_pagadas = facturas.filter(estado='pagada').aggregate(
        total=Sum(Case(
            When(monto_total__gt=0, then=F('monto_total')),
            default=F('monto')
        ))
    )['total'] or 0

    # Facturas por mes (últimos 6 meses) para gráfico de línea
    facturas_por_mes = facturas.filter(
        fecha_emision__gte=timezone.now().date() - datetime.timedelta(days=180)
    ).annotate(
        mes=TruncMonth('fecha_emision')
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')

    # Preparar datos para el gráfico
    import json
    meses_labels = []
    meses_data = []
    for item in facturas_por_mes:
        meses_labels.append(item['mes'].strftime('%b %Y'))
        meses_data.append(item['total'])

    context = {
        'total_clientes': clientes.count(),
        'total_facturas': facturas.count(),
        'facturas_vencidas': facturas_vencidas,
        'facturas_pendientes': facturas_pendientes,
        'facturas_impagas': facturas_impagas,
        'facturas_pagadas': facturas_pagadas,
        'facturas_proximas': facturas_proximas.count(),
        'total_pendiente': total_pendiente,
        'ultimas_facturas': facturas[:10],
        'monto_vencidas': float(monto_vencidas),
        'monto_impagas': float(monto_impagas),
        'monto_pendientes': float(monto_pendientes),
        'monto_pagadas': float(monto_pagadas),
        'meses_labels': json.dumps(meses_labels),
        'meses_data': json.dumps(meses_data),
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

@login_required
def importar_sii(request):
    """Vista para importar facturas desde archivos CSV del SII"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')

        if not csv_file:
            messages.error(request, 'Por favor, selecciona un archivo CSV')
            return redirect('importar_sii')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'El archivo debe ser un CSV')
            return redirect('importar_sii')

        try:
            import csv
            import io
            from decimal import Decimal
            from datetime import datetime

            # Decodificar el archivo CSV
            decoded_file = csv_file.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string, delimiter=';')

            facturas_creadas = 0
            facturas_actualizadas = 0
            errores = []

            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Extraer datos del CSV del SII
                    # Los nombres de las columnas pueden variar según el formato del SII
                    numero_factura = row.get('Número Documento') or row.get('Numero Documento') or row.get('Folio')
                    rut_emisor = row.get('RUT Emisor') or row.get('Rut Emisor')
                    razon_social = row.get('Razón Social') or row.get('Razon Social') or row.get('Nombre')

                    # Procesar fechas
                    fecha_emision_str = row.get('Fecha Emisión') or row.get('Fecha Emision') or row.get('Fecha')
                    fecha_vencimiento_str = row.get('Fecha Vencimiento')

                    # Procesar montos
                    monto_neto_str = row.get('Monto Neto') or row.get('Neto') or '0'
                    monto_iva_str = row.get('Monto IVA') or row.get('IVA') or '0'
                    monto_total_str = row.get('Monto Total') or row.get('Total')

                    # Limpiar y convertir valores numéricos
                    monto_neto = Decimal(monto_neto_str.replace('.', '').replace(',', '.')) if monto_neto_str else Decimal('0')
                    monto_iva = Decimal(monto_iva_str.replace('.', '').replace(',', '.')) if monto_iva_str else Decimal('0')
                    monto_total = Decimal(monto_total_str.replace('.', '').replace(',', '.')) if monto_total_str else Decimal('0')

                    # Si no hay monto total, calcularlo
                    if monto_total == 0:
                        monto_total = monto_neto + monto_iva

                    # Convertir fechas
                    fecha_emision = datetime.strptime(fecha_emision_str, '%d-%m-%Y').date() if fecha_emision_str else timezone.now().date()

                    if fecha_vencimiento_str:
                        fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%d-%m-%Y').date()
                    else:
                        # Si no hay fecha de vencimiento, usar 30 días después de la emisión
                        fecha_vencimiento = fecha_emision + datetime.timedelta(days=30)

                    # Buscar o crear cliente
                    cliente, created = Cliente.objects.get_or_create(
                        rut=rut_emisor,
                        usuario=request.user,
                        defaults={
                            'nombre': razon_social,
                            'email': f'{rut_emisor.replace("-", "").replace(".", "")}@temp.com',
                            'activo': True
                        }
                    )

                    # Actualizar el nombre si el cliente ya existía pero el nombre es diferente
                    if not created and cliente.nombre != razon_social:
                        cliente.nombre = razon_social
                        cliente.save()

                    # Crear o actualizar factura
                    factura, factura_created = Factura.objects.update_or_create(
                        numero_factura=numero_factura,
                        usuario=request.user,
                        defaults={
                            'cliente': cliente,
                            'monto': monto_total,
                            'monto_neto': monto_neto,
                            'monto_iva': monto_iva,
                            'monto_total': monto_total,
                            'fecha_emision': fecha_emision,
                            'fecha_vencimiento': fecha_vencimiento,
                            'estado': 'pendiente',
                            'descripcion': f'Importado desde SII - {razon_social}',
                        }
                    )

                    if factura_created:
                        facturas_creadas += 1
                    else:
                        facturas_actualizadas += 1

                except Exception as e:
                    errores.append(f'Fila {row_num}: {str(e)}')
                    continue

            # Mostrar resumen de la importación
            mensaje_exito = f'Importación completada: {facturas_creadas} facturas creadas, {facturas_actualizadas} actualizadas'
            messages.success(request, mensaje_exito)

            if errores:
                for error in errores[:5]:  # Mostrar solo los primeros 5 errores
                    messages.warning(request, error)
                if len(errores) > 5:
                    messages.warning(request, f'... y {len(errores) - 5} errores más')

            return redirect('facturas_list')

        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            return redirect('importar_sii')

    return render(request, 'core/importar_sii.html')
