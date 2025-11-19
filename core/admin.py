from django.contrib import admin
from .models import Cliente, Factura, ConfiguracionRecordatorio, HistorialRecordatorio


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'rut', 'email', 'telefono', 'activo', 'fecha_registro', 'usuario']
    list_filter = ['activo', 'fecha_registro']
    search_fields = ['nombre', 'rut', 'email']
    readonly_fields = ['fecha_registro']
    fieldsets = (
        ('Información Principal', {
            'fields': ('nombre', 'rut', 'email', 'telefono')
        }),
        ('Detalles Adicionales', {
            'fields': ('notas', 'activo', 'usuario', 'fecha_registro')
        }),
    )


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ['numero_factura', 'cliente', 'monto_total', 'moneda', 'estado', 'estado_cobranza_display',
                    'estado_sii', 'fecha_emision', 'fecha_vencimiento', 'importado_sii', 'usuario']
    list_filter = ['estado', 'estado_cobranza', 'estado_sii', 'moneda', 'importado_sii', 'fecha_emision', 'tipo_dte']
    search_fields = ['numero_factura', 'cliente__nombre', 'cliente__rut', 'descripcion']
    readonly_fields = ['fecha_creacion', 'dias_vencidos']
    date_hierarchy = 'fecha_emision'

    fieldsets = (
        ('Información de Factura', {
            'fields': ('numero_factura', 'cliente', 'descripcion')
        }),
        ('Montos', {
            'fields': ('monto', 'monto_neto', 'monto_iva', 'monto_exento', 'monto_total', 'moneda')
        }),
        ('Fechas', {
            'fields': ('fecha_emision', 'fecha_vencimiento', 'fecha_pago', 'fecha_creacion')
        }),
        ('Estados', {
            'fields': ('estado', 'estado_cobranza')
        }),
        ('Información SII', {
            'fields': ('tipo_dte', 'folio', 'importado_sii'),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('usuario',),
            'classes': ('collapse',)
        }),
    )

    def dias_vencidos(self, obj):
        return obj.dias_vencidos()
    dias_vencidos.short_description = 'Días Vencidos'

    def estado_cobranza_display(self, obj):
        """Muestra el estado de cobranza de forma amigable"""
        if obj.estado_cobranza:
            return obj.get_estado_cobranza_display()
        return '-'
    estado_cobranza_display.short_description = 'Estado Cobranza'


@admin.register(ConfiguracionRecordatorio)
class ConfiguracionRecordatorioAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'email_activo', 'whatsapp_activo', 'dias_antes_vencimiento']
    list_filter = ['email_activo', 'whatsapp_activo']
    search_fields = ['usuario__username', 'usuario__email']

    fieldsets = (
        ('Configuración General', {
            'fields': ('usuario', 'dias_antes_vencimiento')
        }),
        ('Canales de Envío', {
            'fields': ('email_activo', 'whatsapp_activo')
        }),
        ('Plantillas Email', {
            'fields': ('plantilla_email',),
            'classes': ('collapse',)
        }),
        ('Plantillas WhatsApp', {
            'fields': ('plantilla_whatsapp',),
            'classes': ('collapse',)
        }),
    )


@admin.register(HistorialRecordatorio)
class HistorialRecordatorioAdmin(admin.ModelAdmin):
    list_display = ['factura', 'tipo', 'fecha_envio', 'exitoso']
    list_filter = ['tipo', 'exitoso', 'fecha_envio']
    search_fields = ['factura__numero_factura', 'factura__cliente__nombre']
    readonly_fields = ['fecha_envio']
    date_hierarchy = 'fecha_envio'

    fieldsets = (
        ('Información del Recordatorio', {
            'fields': ('factura', 'tipo', 'fecha_envio')
        }),
        ('Resultado', {
            'fields': ('exitoso', 'mensaje_error')
        }),
    )
