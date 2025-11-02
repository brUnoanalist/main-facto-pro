# Desplegar en Glitch (Gratis, sin tarjeta)

## Características
- Gratis, sin tarjeta
- 1 GB disk
- 4000 horas/mes
- Se "duerme" después de 5 minutos sin actividad

## Pasos

1. Ve a https://glitch.com
2. Click "Sign up" (usa GitHub)
3. Click "New Project" → "Import from GitHub"
4. Pega: `https://github.com/brUnoanalist/main-facto-pro`

5. Crea archivo `glitch.json`:
```json
{
  "install": "pip3 install -r requirements-minimal.txt",
  "start": "python3 manage.py migrate && python3 manage.py collectstatic --noinput && gunicorn morosidad_project.wsgi:application",
  "watch": {
    "restart": {
      "include": [
        "**/*.py"
      ]
    }
  }
}
```

6. En `.env` file (Settings → Environment Variables):
```
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=False
ALLOWED_HOSTS=tu-proyecto.glitch.me
```

7. Click "Share" → "Live App"

Tu app estará en: https://tu-proyecto.glitch.me

**Nota:** Glitch es mejor para proyectos de prueba, se duerme cuando no hay actividad.
