# Desplegar en PythonAnywhere (100% Gratis)

## Paso 1: Crear Cuenta
1. Ve a https://www.pythonanywhere.com
2. Click en "Pricing & signup"
3. Selecciona "Create a Beginner account" (Gratis)
4. Completa el registro (NO requiere tarjeta)

## Paso 2: Subir el Código
```bash
# En PythonAnywhere Bash Console
git clone https://github.com/brUnoanalist/main-facto-pro.git
cd main-facto-pro
```

## Paso 3: Crear Entorno Virtual
```bash
mkvirtualenv --python=/usr/bin/python3.10 factopro
pip install -r requirements-pythonanywhere.txt
```

**Importante:** El virtualenv debe llamarse `factopro` (sin guión).

## Paso 4: Configurar Base de Datos
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
```

## Paso 5: Configurar Web App
1. Ve a "Web" tab
2. Click "Add a new web app"
3. Selecciona "Manual configuration"
4. Python 3.10
5. En "Code" section:
   - Source code: `/home/TU_USUARIO/main-facto-pro`
   - Working directory: `/home/TU_USUARIO/main-facto-pro`
   - WSGI file: Click para editar y pega:

```python
import os
import sys

path = '/home/TU_USUARIO/main-facto-pro'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'morosidad_project.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

6. En "Virtualenv" section:
   - Path: `/home/TU_USUARIO/.virtualenvs/facto-pro`

7. En "Static files":
   - URL: `/static/`
   - Directory: `/home/TU_USUARIO/main-facto-pro/staticfiles`

## Paso 6: Variables de Entorno
En Bash console:
```bash
echo 'export DEBUG=False' >> ~/.bashrc
echo 'export ALLOWED_HOSTS=TU_USUARIO.pythonanywhere.com' >> ~/.bashrc
source ~/.bashrc
```

## Paso 7: Reload y Listo!
Click en el botón verde "Reload" en la página Web

Tu app estará en: https://TU_USUARIO.pythonanywhere.com

## Limitaciones Plan Gratis
- 512 MB disk space
- 1 web app
- SQLite database (suficiente para empezar)
- TU_USUARIO.pythonanywhere.com domain
