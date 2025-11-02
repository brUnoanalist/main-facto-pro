from django import template
from core.utils import formatear_moneda, formatear_rut

register = template.Library()


@register.filter(name='currency')
def currency(value, codigo_moneda='CLP'):
    """
    Filtra un valor numérico para formatearlo como moneda.

    Uso en templates:
        {{ valor|currency:"USD" }}
        {{ valor|currency:"CLP" }}
        {{ valor|currency }}  # Default: CLP
    """
    if value is None:
        return formatear_moneda(0, codigo_moneda)
    return formatear_moneda(value, codigo_moneda)


@register.filter(name='formatear_rut')
def format_rut(value):
    """
    Filtra un RUT para formatearlo al estándar chileno XX.XXX.XXX-X.

    Uso en templates:
        {{ cliente.rut|formatear_rut }}
    """
    if not value:
        return ''
    return formatear_rut(value)
