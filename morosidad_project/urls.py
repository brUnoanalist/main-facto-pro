from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

# Custom error handlers
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
