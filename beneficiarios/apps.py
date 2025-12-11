from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class BeneficiariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'beneficiarios'
    verbose_name = '2. Gestión y Movimiento de Clientes / Beneficiarios'
    
    def ready(self):
        # Importar las señales cuando la aplicación esté lista
        import beneficiarios.signals
