from django.db import models
from django.utils.translation import gettext_lazy as _

class Proveedor(models.Model):
    nombre = models.CharField(
        max_length=150, 
        unique=True, 
        verbose_name=_("* Nombre")
    )
    direccion = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Dirección")
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
        verbose_name = _("Proveedor")
        verbose_name_plural = _("4.1. Proveedores / Transporte")
        ordering = ['nombre']

    def __str__(self):
        return self.nombre