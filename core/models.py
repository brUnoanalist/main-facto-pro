from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import re


def validar_rut_chileno(rut):
    """
    Valida el formato y dígito verificador de un RUT chileno.
    Acepta formatos: 12.345.678-9, 12345678-9, 123456789
    """
    if not rut:
        return True  # RUT es opcional

    # Limpiar el RUT
    rut_limpio = rut.upper().replace('.', '').replace('-', '').replace(' ', '')

    if not rut_limpio:
        return True

    # Validar que solo contenga números y K
    if not re.match(r'^[0-9]+[0-9K]$', rut_limpio):
        raise ValidationError('El RUT debe contener solo números y puede terminar en K')

    if len(rut_limpio) < 2:
        raise ValidationError('El RUT es muy corto')

    # Separar cuerpo y dígito verificador
    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1]

    # Calcular dígito verificador
    suma = 0
    multiplo = 2

    for i in reversed(cuerpo):
        suma += int(i) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2

    resto = suma % 11
    dv_calculado = 11 - resto

    if dv_calculado == 11:
        dv_calculado = '0'
    elif dv_calculado == 10:
        dv_calculado = 'K'
    else:
        dv_calculado = str(dv_calculado)

    if dv_ingresado != dv_calculado:
        raise ValidationError(f'El dígito verificador es incorrecto. Debería ser {dv_calculado}')

    return True


def formatear_rut(rut):
    """Formatea un RUT al formato estándar XX.XXX.XXX-X"""
    if not rut:
        return rut

    rut_limpio = rut.upper().replace('.', '').replace('-', '').replace(' ', '')

    if len(rut_limpio) < 2:
        return rut

    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]

    # Formatear con puntos
    cuerpo_formateado = ''
    for i, char in enumerate(reversed(cuerpo)):
        if i > 0 and i % 3 == 0:
            cuerpo_formateado = '.' + cuerpo_formateado
        cuerpo_formateado = char + cuerpo_formateado

    return f'{cuerpo_formateado}-{dv}'


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    rut = models.CharField(max_length=20, blank=True, default='', verbose_name='RUT/DNI',
                          validators=[validar_rut_chileno])
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

    def clean(self):
        """Validación adicional del modelo"""
        super().clean()
        if self.rut:
            validar_rut_chileno(self.rut)

    def save(self, *args, **kwargs):
        # Formatear el RUT antes de guardar
        if self.rut:
            self.rut = formatear_rut(self.rut)
        super().save(*args, **kwargs)

    def rut_formateado(self):
        """Retorna el RUT formateado"""
        return formatear_rut(self.rut) if self.rut else ''

    def total_deuda(self):
        """Retorna el total de deuda (solo facturas pendientes)"""
        return sum(
            f.monto_total if f.monto_total else f.monto
            for f in self.facturas.filter(estado='pendiente')
        )

    def facturas_vencidas(self):
        """Retorna el número de facturas pendientes con estado de cobranza vencida, mora o incobrable"""
        return self.facturas.filter(
            estado='pendiente',
            estado_cobranza__in=['vencida', 'mora', 'incobrable']
        ).count()

    def facturas_en_mora(self):
        """Retorna el número de facturas en mora"""
        return self.facturas.filter(
            estado='pendiente',
            estado_cobranza='mora'
        ).count()


class Factura(models.Model):
    # Estados principales - Modelo simplificado y profesional
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('anulada', 'Anulada'),
    ]

    # Sub-estados de cobranza (solo para facturas pendientes)
    ESTADO_COBRANZA_CHOICES = [
        ('vigente', 'Vigente'),           # No ha vencido
        ('por_vencer', 'Por Vencer'),     # Vence en 7 días o menos
        ('vencida', 'Vencida'),           # Pasó la fecha de vencimiento
        ('mora', 'En Mora'),              # Vencida + 30 días
        ('incobrable', 'Incobrable'),     # Vencida + 90 días
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
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Monto ya pagado de la factura')
    monto_pendiente = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Monto que aún falta por pagar')
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default='CLP')
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    estado_cobranza = models.CharField(max_length=20, choices=ESTADO_COBRANZA_CHOICES, default='vigente', null=True, blank=True)
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
        """Retorna los días que lleva vencida la factura"""
        if self.estado == 'pendiente' and self.fecha_vencimiento < timezone.now().date():
            return (timezone.now().date() - self.fecha_vencimiento).days
        return 0

    def proxima_vencer(self):
        """Verifica si la factura está próxima a vencer (7 días o menos)"""
        if self.estado == 'pendiente':
            dias = (self.fecha_vencimiento - timezone.now().date()).days
            return 0 <= dias <= 7
        return False

    def porcentaje_pagado(self):
        """Retorna el porcentaje pagado de la factura"""
        if self.monto_total and self.monto_total > 0:
            return (self.monto_pagado / self.monto_total) * 100
        return 0

    def tiene_pago_parcial(self):
        """Verifica si la factura tiene un pago parcial"""
        return self.monto_pagado > 0 and self.monto_pendiente > 0

    def actualizar_estado_cobranza(self):
        """Actualiza automáticamente el estado de cobranza según la fecha"""
        if self.estado != 'pendiente':
            self.estado_cobranza = None
            return

        hoy = timezone.now().date()
        dias_vencido = (hoy - self.fecha_vencimiento).days
        dias_para_vencer = (self.fecha_vencimiento - hoy).days

        if dias_vencido >= 90:
            self.estado_cobranza = 'incobrable'
        elif dias_vencido >= 30:
            self.estado_cobranza = 'mora'
        elif dias_vencido > 0:
            self.estado_cobranza = 'vencida'
        elif dias_para_vencer <= 7:
            self.estado_cobranza = 'por_vencer'
        else:
            self.estado_cobranza = 'vigente'

    def monto_formateado(self):
        """Retorna el monto formateado según la moneda de la factura"""
        from .utils import formatear_moneda
        return formatear_moneda(self.monto, self.moneda)

    def save(self, *args, **kwargs):
        # Actualizar estado de cobranza automáticamente
        if self.estado == 'pendiente':
            self.actualizar_estado_cobranza()
        else:
            self.estado_cobranza = None
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