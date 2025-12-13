from django.db import models
from django.utils.translation import gettext_lazy as _

class Recepcionista(models.Model):
    nombre = models.CharField(
        max_length=150, 
        unique=True, 
        verbose_name=_("* Nombre")  # ← Agregado asterisco
    )
    telefono = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name=_("Teléfono")
    )
    email = models.EmailField(
        blank=True, 
        null=True, 
        verbose_name=_("Correo Electrónico")
    )
    activo = models.BooleanField(
        default=True, 
        verbose_name=_("Activo")
    )

    class Meta:
        verbose_name = _("Recepcionista")
        verbose_name_plural = _("5.1. Recepcionistas / Encargados")
        ordering = ['nombre']
        # 🚀 OPTIMIZACIÓN: Índices para búsquedas
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['activo']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.nombre