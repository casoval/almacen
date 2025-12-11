from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AlmacenesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'almacenes'
    verbose_name = _('1. Gestión y Movimiento de Almacenes')