from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class RecepcionistasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recepcionistas'
    verbose_name = _('5. Gestión de Recepcionistas / Encargados')