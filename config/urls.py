from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# Función para redirigir la raíz
def home_redirect(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin:index')
        else:
            return redirect('dashboard')
    else:
        return redirect('login')

urlpatterns = [
    path('', home_redirect, name='home'),  # ← NUEVA LÍNEA
    path('admin/', admin.site.urls),
    path('usuarios/', include('usuarios.urls')),
    path('reportes/', include('reportes.urls')),
    path('productos/', include('productos.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)