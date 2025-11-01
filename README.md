# Facto-Pro

Sistema de gestión de facturas y cobros para freelancers y pequeñas empresas.

## Características

- Gestión de clientes con información de contacto
- Registro de facturas con múltiples monedas (CLP, USD, EUR, GBP, ARS, MXN, COP, PEN, BRL)
- Seguimiento de pagos y vencimientos
- Sistema de recordatorios automáticos por email
- Formato automático de RUT chileno
- Reportes en PDF y Excel
- Dashboard con métricas clave
- Alertas de facturas vencidas y próximas a vencer

## Tecnologías

- Django 4.x
- Python 3.x
- Bootstrap 5
- Bootstrap Icons
- ReportLab (PDF)
- OpenPyXL (Excel)

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/facto-pro.git
cd facto-pro
```

2. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar base de datos:
```bash
python manage.py migrate
```

5. Crear superusuario:
```bash
python manage.py createsuperuser
```

6. Ejecutar servidor de desarrollo:
```bash
python manage.py runserver
```

7. Abrir en el navegador: http://localhost:8000

## Configuración

- Configurar SMTP para envío de recordatorios en `settings.py`
- Personalizar plantillas de email en la sección de Configuración

## Uso

1. Registrar clientes con sus datos de contacto
2. Crear facturas asociadas a clientes
3. El sistema automáticamente:
   - Detecta facturas vencidas
   - Alerta sobre facturas próximas a vencer
   - Formatea montos según la moneda configurada
   - Formatea RUTs chilenos automáticamente

## Licencia

MIT License
