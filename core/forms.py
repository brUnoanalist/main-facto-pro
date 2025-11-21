from django import forms
from .models import Cliente, Factura, ConfiguracionRecordatorio, validar_rut_chileno

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'rut', 'email', 'telefono', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12.345.678-9'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }
        help_texts = {
            'rut': 'Formato: 12.345.678-9 o 12345678-9'
        }

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if rut:
            validar_rut_chileno(rut)
        return rut


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