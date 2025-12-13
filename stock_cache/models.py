from django.db import models
from django.utils.translation import gettext_lazy as _
from productos.models import Producto
from almacenes.models import Almacen


class StockCache(models.Model):
    """
    Tabla optimizada que mantiene el stock actualizado en tiempo real.
    Actualizada automáticamente por triggers en movimientos.
    """
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        verbose_name=_("Producto")
    )
    almacen = models.ForeignKey(
        Almacen,
        on_delete=models.CASCADE,
        verbose_name=_("Almacén")
    )
    stock_bueno = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Stock Bueno")
    )
    stock_danado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Stock Dañado")
    )
    stock_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Stock Total")
    )
    ultima_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Última Actualización")
    )

    class Meta:
        verbose_name = _("Stock Cache")
        verbose_name_plural = _("Stock Cache")
        unique_together = [['producto', 'almacen']]
        # 🚀 OPTIMIZACIÓN EXTREMA: Índices para acceso instantáneo
        indexes = [
            models.Index(fields=['producto'], name='stock_cache_prod_idx'),
            models.Index(fields=['almacen'], name='stock_cache_alm_idx'),
            models.Index(fields=['producto', 'almacen'], name='stock_cache_prod_alm_idx'),
            models.Index(fields=['stock_total'], name='stock_cache_total_idx'),
            models.Index(fields=['ultima_actualizacion'], name='stock_cache_update_idx'),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.almacen.nombre}: {self.stock_total}"

    @property
    def stock_real_bueno(self):
        """Stock real = físico + ajustes de clientes"""
        # Para stock real, necesitamos considerar movimientos de cliente
        # Por simplicidad, por ahora devolvemos el físico
        # Se puede extender después si es necesario
        return self.stock_bueno

    @property
    def stock_real_danado(self):
        """Stock real = físico + ajustes de clientes"""
        return self.stock_danado

    @property
    def stock_real_total(self):
        """Stock real = físico + ajustes de clientes"""
        return self.stock_total
