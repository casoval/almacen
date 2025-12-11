from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ProveedoresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'proveedores'
    verbose_name = _('4. Gestión de Proveedores / Transporte')