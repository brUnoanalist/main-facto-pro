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

## Despliegue en Render (Gratis)

### Opción 1: Usando render.yaml (Automático)

1. Haz push de tu código a GitHub
2. Ve a [Render.com](https://render.com) y crea una cuenta
3. Click en "New +" → "Blueprint"
4. Conecta tu repositorio de GitHub
5. Render detectará automáticamente el `render.yaml` y configurará todo
6. Click en "Apply" y espera a que se despliegue

### Opción 2: Manual

1. Ve a [Render.com](https://render.com) y crea una cuenta
2. Crea una nueva PostgreSQL Database (gratis)
3. Crea un nuevo Web Service
   - Conecta tu repositorio de GitHub
   - Build Command: `./build.sh`
   - Start Command: `gunicorn morosidad_project.wsgi:application`
4. Agrega variables de entorno:
   - `DATABASE_URL`: (Render la configurará automáticamente)
   - `SECRET_KEY`: (genera una nueva con Django)
   - `DEBUG`: `False`
   - `ALLOWED_HOSTS`: `tu-app.onrender.com`

## Otras Opciones de Despliegue Gratuito

### Railway
- Hasta 500 horas/mes gratis
- PostgreSQL incluido
- Deploy automático desde GitHub
- URL: https://railway.app

### PythonAnywhere
- Plan gratuito disponible
- 512 MB storage
- URL: https://www.pythonanywhere.com

### Fly.io
- 3 VMs pequeñas gratis
- PostgreSQL gratis
- URL: https://fly.io

## Licencia

MIT License
