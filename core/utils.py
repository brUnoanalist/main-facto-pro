from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook
from io import BytesIO
import datetime
from decimal import Decimal, InvalidOperation

# ========================
# UTILIDADES DE MONEDA
# ========================

# Configuración de monedas soportadas
MONEDAS_CONFIG = {
    'CLP': {
        'simbolo': '$',
        'nombre': 'Peso Chileno',
        'codigo': 'CLP',
        'separador_miles': '.',
        'separador_decimal': ',',
        'decimales': 0,
        'posicion_simbolo': 'antes',
        'bandera': '🇨🇱'
    },
    'USD': {
        'simbolo': '$',
        'nombre': 'Dólar Estadounidense',
        'codigo': 'USD',
        'separador_miles': ',',
        'separador_decimal': '.',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇺🇸'
    },
    'EUR': {
        'simbolo': '€',
        'nombre': 'Euro',
        'codigo': 'EUR',
        'separador_miles': '.',
        'separador_decimal': ',',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇪🇺'
    },
    'GBP': {
        'simbolo': '£',
        'nombre': 'Libra Esterlina',
        'codigo': 'GBP',
        'separador_miles': ',',
        'separador_decimal': '.',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇬🇧'
    },
    'ARS': {
        'simbolo': '$',
        'nombre': 'Peso Argentino',
        'codigo': 'ARS',
        'separador_miles': '.',
        'separador_decimal': ',',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇦🇷'
    },
    'MXN': {
        'simbolo': '$',
        'nombre': 'Peso Mexicano',
        'codigo': 'MXN',
        'separador_miles': ',',
        'separador_decimal': '.',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇲🇽'
    },
    'COP': {
        'simbolo': '$',
        'nombre': 'Peso Colombiano',
        'codigo': 'COP',
        'separador_miles': '.',
        'separador_decimal': ',',
        'decimales': 0,
        'posicion_simbolo': 'antes',
        'bandera': '🇨🇴'
    },
    'PEN': {
        'simbolo': 'S/',
        'nombre': 'Sol Peruano',
        'codigo': 'PEN',
        'separador_miles': ',',
        'separador_decimal': '.',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇵🇪'
    },
    'BRL': {
        'simbolo': 'R$',
        'nombre': 'Real Brasileño',
        'codigo': 'BRL',
        'separador_miles': '.',
        'separador_decimal': ',',
        'decimales': 2,
        'posicion_simbolo': 'antes',
        'bandera': '🇧🇷'
    }
}


def formatear_moneda(monto, codigo_moneda='CLP', incluir_codigo=False):
    """
    Formatea un monto según las convenciones de la moneda especificada.

    Args:
        monto: Cantidad a formatear (puede ser Decimal, float, int o str)
        codigo_moneda: Código de moneda ISO (default: 'CLP')
        incluir_codigo: Si True, incluye el código de moneda (ej: "CLP $1.500.000")

    Returns:
        String formateado según la moneda

    Ejemplos:
        >>> formatear_moneda(1500000, 'CLP')
        '$1.500.000'
        >>> formatear_moneda(1500.50, 'USD')
        '$1,500.50'
        >>> formatear_moneda(1500, 'EUR', incluir_codigo=True)
        'EUR €1.500,00'
    """
    # Convertir a Decimal para precisión
    try:
        if isinstance(monto, str):
            monto = Decimal(monto.replace(',', '').replace('.', ''))
        else:
            monto = Decimal(str(monto))
    except (InvalidOperation, ValueError):
        return "N/A"

    # Obtener configuración de la moneda
    config = MONEDAS_CONFIG.get(codigo_moneda.upper(), MONEDAS_CONFIG['CLP'])

    # Redondear según los decimales de la moneda
    if config['decimales'] == 0:
        monto = monto.quantize(Decimal('1'))
    else:
        monto = monto.quantize(Decimal('0.01'))

    # Separar parte entera y decimal
    monto_str = str(monto)
    if '.' in monto_str:
        parte_entera, parte_decimal = monto_str.split('.')
    else:
        parte_entera = monto_str
        parte_decimal = ''

    # Formatear parte entera con separador de miles
    parte_entera = parte_entera.lstrip('-')
    es_negativo = str(monto).startswith('-')

    # Agregar separadores de miles
    grupos = []
    while len(parte_entera) > 3:
        grupos.insert(0, parte_entera[-3:])
        parte_entera = parte_entera[:-3]
    if parte_entera:
        grupos.insert(0, parte_entera)

    parte_entera_formateada = config['separador_miles'].join(grupos)

    # Construir el monto formateado
    if config['decimales'] > 0 and parte_decimal:
        # Asegurar que tenga el número correcto de decimales
        parte_decimal = parte_decimal.ljust(config['decimales'], '0')
        monto_formateado = f"{parte_entera_formateada}{config['separador_decimal']}{parte_decimal}"
    else:
        monto_formateado = parte_entera_formateada

    # Agregar símbolo de moneda
    if config['posicion_simbolo'] == 'antes':
        resultado = f"{config['simbolo']}{monto_formateado}"
    else:
        resultado = f"{monto_formateado}{config['simbolo']}"

    # Agregar signo negativo si es necesario
    if es_negativo:
        resultado = f"-{resultado}"

    # Incluir código de moneda si se solicita
    if incluir_codigo:
        resultado = f"{codigo_moneda.upper()} {resultado}"

    return resultado


def formatear_moneda_simple(monto, codigo_moneda='CLP'):
    """
    Versión simplificada del formateo de moneda sin opciones avanzadas.

    Args:
        monto: Cantidad a formatear
        codigo_moneda: Código de moneda ISO (default: 'CLP')

    Returns:
        String formateado

    Ejemplos:
        >>> formatear_moneda_simple(1500000, 'CLP')
        '$1.500.000'
        >>> formatear_moneda_simple(1500.50, 'USD')
        '$1,500.50'
    """
    return formatear_moneda(monto, codigo_moneda, incluir_codigo=False)


def parsear_monto(monto_str, codigo_moneda='CLP'):
    """
    Convierte un string formateado a Decimal.

    Args:
        monto_str: String con el monto (puede incluir separadores y símbolos)
        codigo_moneda: Código de moneda para conocer el formato

    Returns:
        Decimal con el valor numérico

    Ejemplos:
        >>> parsear_monto('$1.500.000', 'CLP')
        Decimal('1500000')
        >>> parsear_monto('$1,500.50', 'USD')
        Decimal('1500.50')
        >>> parsear_monto('€1.500,00', 'EUR')
        Decimal('1500.00')
    """
    if not monto_str:
        return Decimal('0')

    # Obtener configuración de la moneda
    config = MONEDAS_CONFIG.get(codigo_moneda.upper(), MONEDAS_CONFIG['CLP'])

    # Limpiar el string
    monto_limpio = str(monto_str)

    # Remover símbolos de moneda
    for moneda_config in MONEDAS_CONFIG.values():
        monto_limpio = monto_limpio.replace(moneda_config['simbolo'], '')

    # Remover espacios y códigos de moneda
    for codigo in MONEDAS_CONFIG.keys():
        monto_limpio = monto_limpio.replace(codigo, '')
    monto_limpio = monto_limpio.strip()

    # Remover separadores de miles y reemplazar separador decimal
    monto_limpio = monto_limpio.replace(config['separador_miles'], '')
    monto_limpio = monto_limpio.replace(config['separador_decimal'], '.')

    try:
        return Decimal(monto_limpio)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def obtener_monedas_disponibles(incluir_bandera=True):
    """
    Retorna una lista de monedas disponibles para usar en selectores.

    Args:
        incluir_bandera: Si True, incluye el emoji de la bandera en el nombre

    Returns:
        Lista de tuplas (codigo, nombre_display) para usar en Django choices

    Ejemplo:
        >>> obtener_monedas_disponibles()
        [('CLP', '🇨🇱 Peso Chileno (CLP)'), ('USD', '🇺🇸 Dólar Estadounidense (USD)'), ...]
    """
    monedas = []
    for codigo, config in sorted(MONEDAS_CONFIG.items()):
        if incluir_bandera:
            nombre_display = f"{config['bandera']} {config['nombre']} ({codigo})"
        else:
            nombre_display = f"{config['nombre']} ({codigo})"
        monedas.append((codigo, nombre_display))
    return monedas


def obtener_info_moneda(codigo_moneda):
    """
    Retorna la configuración completa de una moneda.

    Args:
        codigo_moneda: Código ISO de la moneda

    Returns:
        Diccionario con la configuración o None si no existe
    """
    return MONEDAS_CONFIG.get(codigo_moneda.upper())


# ========================
# FUNCIONES DE EMAIL Y REPORTES
# ========================

def enviar_recordatorio_email(factura, config):
    try:
        # Obtener moneda de la factura (default CLP si no existe)
        codigo_moneda = getattr(factura, 'moneda', 'CLP')
        monto_formateado = formatear_moneda(factura.monto, codigo_moneda)

        mensaje = config.plantilla_email.format(
            cliente=factura.cliente.nombre,
            numero=factura.numero_factura,
            monto=monto_formateado,
            fecha=factura.fecha_vencimiento.strftime('%d/%m/%Y')
        )
        
        send_mail(
            subject=f'Recordatorio Factura {factura.numero_factura}',
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[factura.cliente.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False

def generar_pdf_reporte(usuario, facturas):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    titulo = Paragraph(f"<b>Reporte de Morosidad - {datetime.date.today()}</b>", styles['Title'])
    elements.append(titulo)
    elements.append(Spacer(1, 12))
    
    data = [['Factura', 'Cliente', 'Monto', 'Vencimiento', 'Estado']]

    for f in facturas:
        # Obtener moneda de la factura (default CLP si no existe)
        codigo_moneda = getattr(f, 'moneda', 'CLP')
        monto_formateado = formatear_moneda(f.monto, codigo_moneda)

        data.append([
            f.numero_factura,
            f.cliente.nombre,
            monto_formateado,
            f.fecha_vencimiento.strftime('%d/%m/%Y'),
            f.get_estado_display()
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_morosidad_{datetime.date.today()}.pdf"'
    return response

def generar_excel_reporte(usuario, facturas):
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte Morosidad"
    
    headers = ['Factura', 'Cliente', 'RUT/DNI', 'Email', 'Moneda', 'Monto', 'Emisión', 'Vencimiento', 'Estado', 'Días Vencidos']
    ws.append(headers)

    for f in facturas:
        # Obtener moneda de la factura (default CLP si no existe)
        codigo_moneda = getattr(f, 'moneda', 'CLP')
        monto_formateado = formatear_moneda(f.monto, codigo_moneda)

        ws.append([
            f.numero_factura,
            f.cliente.nombre,
            f.cliente.rut if f.cliente.rut else '-',
            f.cliente.email,
            codigo_moneda,
            monto_formateado,
            f.fecha_emision.strftime('%d/%m/%Y'),
            f.fecha_vencimiento.strftime('%d/%m/%Y'),
            f.get_estado_display(),
            f.dias_vencidos()
        ])
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reporte_morosidad_{datetime.date.today()}.xlsx"'
    return response
