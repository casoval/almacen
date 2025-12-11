from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ProductosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'productos'
    verbose_name = _('3. Gestión de Productos')