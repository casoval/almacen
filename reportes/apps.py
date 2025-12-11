from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReportesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reportes'
    verbose_name = _('6. Reportes y Análisis')
    
    def ready(self):
        """
        Código que se ejecuta cuando la app está lista
        Aquí puedes importar señales u otra lógica de inicialización
        """
        pass