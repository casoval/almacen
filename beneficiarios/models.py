from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from productos.models import Producto
from django.utils import timezone
from proveedores.models import Proveedor
from recepcionistas.models import Recepcionista


class Cliente(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name=_("Código"))
    nombre = models.CharField(max_length=150, verbose_name=_("Nombre"))
    direccion = models.TextField(blank=False, null=False, verbose_name=_("Dirección/Comunidad"))
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Teléfono"))
    observaciones = models.TextField(blank=True, null=True, verbose_name=_("Observaciones"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Cliente")
        verbose_name_plural = _("2.1. Clientes / Beneficiarios")
        ordering = ['codigo']
        # Índices para búsquedas rápidas de clientes
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['activo']),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class MovimientoCliente(models.Model):
    TIPO_MOVIMIENTO = (
        ('ENTRADA', 'Entrada desde almacén'),
        ('SALIDA', 'Salida hacia almacén'),
        ('TRASLADO', 'Traslado entre clientes'),
    )

    # Cliente principal del movimiento
    cliente = models.ForeignKey(
        Cliente,
        related_name='movimientos',
        on_delete=models.CASCADE,
        verbose_name=_("Cliente")
    )
    
    # Para traslados entre clientes
    cliente_origen = models.ForeignKey(
        Cliente, 
        related_name='salidas', 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        verbose_name=_("Cliente Origen")
    )
    cliente_destino = models.ForeignKey(
        Cliente, 
        related_name='entradas', 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        verbose_name=_("Cliente Destino")
    )
    
    # Para movimientos con almacenes
    almacen_origen = models.ForeignKey(
        'almacenes.Almacen',
        related_name='salidas_cliente',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Almacén Origen")
    )
    almacen_destino = models.ForeignKey(
        'almacenes.Almacen',
        related_name='entradas_cliente',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Almacén Destino")
    )
    
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_MOVIMIENTO, 
        verbose_name=_("Tipo de Movimiento")
    )
    
    fecha = models.DateField(
        verbose_name=_('Fecha'),
        default=timezone.now
    )
    
    numero_movimiento = models.CharField(
        max_length=50, 
        unique=True,
        editable=False,
        verbose_name=_("N° de movimiento")
    )
    
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='movimientos_cliente',
        verbose_name=_("Proveedor"),
        help_text=_("Proveedor/Transporte del que se reciben los productos")
    )
    
    recepcionista = models.ForeignKey(
        Recepcionista,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='movimientos_cliente',
        verbose_name=_("Recepcionista"),
        help_text=_("Persona que recepciona el movimiento")
    )
    
    observaciones_movimiento = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Observaciones del Movimiento")
    )
    
    comentario = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Comentario general")
    )

    class Meta:
        verbose_name = _("Movimiento de Cliente")
        verbose_name_plural = _("2.2 Movimientos de Cliente / Beneficiario")
        ordering = ['cliente__codigo', 'tipo', '-numero_movimiento']
        # =========================================================
        # 🚀 OPTIMIZACIÓN: ÍNDICES PARA REPORTES Y FILTROS RÁPIDOS
        # =========================================================
        indexes = [
            models.Index(fields=['fecha'], name='mov_cli_fecha_idx'),
            models.Index(fields=['tipo'], name='mov_cli_tipo_idx'),
            models.Index(fields=['cliente'], name='mov_cli_cliente_idx'),
            models.Index(fields=['cliente_origen'], name='mov_cli_orig_idx'),
            models.Index(fields=['cliente_destino'], name='mov_cli_dest_idx'),
            models.Index(fields=['almacen_origen'], name='mov_cli_alm_orig_idx'),
            models.Index(fields=['almacen_destino'], name='mov_cli_alm_dest_idx'),
            # Índice compuesto para filtrar por fecha y tipo simultáneamente (Dashboard)
            models.Index(fields=['fecha', 'tipo'], name='mov_cli_fecha_tipo_idx'),
            # 🚀 OPTIMIZACIÓN: Índices críticos para cálculos de stock real
            models.Index(fields=['tipo', 'almacen_origen'], name='mov_cli_tipo_alm_orig_idx'),
            models.Index(fields=['tipo', 'almacen_destino'], name='mov_cli_tipo_alm_dest_idx'),
            models.Index(fields=['almacen_origen', 'almacen_destino'], name='mov_cli_alm_orig_dest_idx'),
            models.Index(fields=['fecha', 'almacen_origen'], name='mov_cli_fecha_alm_orig_idx'),
            models.Index(fields=['fecha', 'almacen_destino'], name='mov_cli_fecha_alm_dest_idx'),
        ]

    def __str__(self):
        if self.numero_movimiento:
            return f"{self.numero_movimiento} - {self.tipo}"
        return f"Movimiento {self.tipo} (pendiente)"

    def clean(self):
        """Validación de lógica de negocio"""
        if self.tipo == 'ENTRADA' and not self.almacen_origen:
            raise ValidationError({
                'almacen_origen': _("Una entrada debe tener almacén origen")
            })
        
        if self.tipo == 'SALIDA' and not self.almacen_destino:
            raise ValidationError({
                'almacen_destino': _("Una salida debe tener almacén destino")
            })
        
        if self.tipo == 'TRASLADO':
            if not self.cliente_origen or not self.cliente_destino:
                raise ValidationError(
                    _("Un traslado requiere cliente origen y destino")
                )
            if self.cliente_origen == self.cliente_destino:
                raise ValidationError(
                    _("El cliente origen y destino no pueden ser el mismo")
                )
            if self.cliente_origen != self.cliente:
                raise ValidationError({
                    'cliente_origen': _("El cliente origen debe ser igual al cliente del reporte")
                })

    def save(self, *args, **kwargs):
        """Genera el número de movimiento automáticamente SOLO si es nuevo"""
        if not self.pk and not self.numero_movimiento and self.cliente:
            ultimo_movimiento = MovimientoCliente.objects.filter(
                cliente=self.cliente,
                tipo=self.tipo
            ).order_by('-id').first()
            
            if ultimo_movimiento and ultimo_movimiento.numero_movimiento:
                try:
                    numero_limpio = ultimo_movimiento.numero_movimiento.replace('/', '-')
                    ultimo_numero = int(numero_limpio.split('-')[-1])
                    nuevo_numero = ultimo_numero + 1
                except (ValueError, IndexError):
                    nuevo_numero = 1
            else:
                nuevo_numero = 1
            
            prefijo = {
                'ENTRADA': 'ENT',
                'SALIDA': 'SAL',
                'TRASLADO': 'TRA'
            }.get(self.tipo, 'MOV')
            
            self.numero_movimiento = f"{self.cliente.codigo}/{prefijo}-{nuevo_numero:04d}"
        
        self.full_clean()
        super().save(*args, **kwargs)

    def get_total_productos(self):
        return self.detalles.count()

    def get_total_cantidad_buena(self):
        return self.detalles.aggregate(
            total=models.Sum('cantidad')
        )['total'] or 0

    def get_total_cantidad_danada(self):
        return self.detalles.aggregate(
            total=models.Sum('cantidad_danada')
        )['total'] or 0

    def get_total_cantidad_general(self):
        return self.get_total_cantidad_buena() + self.get_total_cantidad_danada()


class DetalleMovimientoCliente(models.Model):
    movimiento = models.ForeignKey(
        MovimientoCliente,
        related_name='detalles',
        on_delete=models.CASCADE,
        verbose_name=_("Movimiento")
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        verbose_name=_("Producto")
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Cantidad en buen estado")
    )
    cantidad_danada = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Cantidad dañada")
    )
    observaciones_producto = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Observaciones del producto")
    )

    class Meta:
        verbose_name = _("Detalle de Movimiento")
        verbose_name_plural = _("2.3. Detalles de Movimientos")
        ordering = ['movimiento__cliente__codigo', 'movimiento__tipo', '-movimiento__numero_movimiento', 'id']
        unique_together = [['movimiento', 'producto']]
        # =========================================================
        # 🚀 OPTIMIZACIÓN: ÍNDICES PARA JOINs RÁPIDOS
        # =========================================================
        indexes = [
            models.Index(fields=['producto'], name='det_mov_cli_prod_idx'),
            models.Index(fields=['movimiento'], name='det_mov_cli_mov_idx'),
            # 🚀 OPTIMIZACIÓN: Índices críticos para raw SQL de stock real
            models.Index(fields=['producto', 'movimiento'], name='det_mov_cli_prod_mov_idx'),
            models.Index(fields=['movimiento', 'producto'], name='det_mov_cli_mov_prod_idx'),
            models.Index(fields=['producto', 'cantidad'], name='det_mov_cli_prod_cant_idx'),
            models.Index(fields=['producto', 'cantidad_danada'], name='det_mov_cli_prod_dan_idx'),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - Buena: {self.cantidad} / Dañada: {self.cantidad_danada}"

    def clean(self):
        if self.cantidad < 0:
            raise ValidationError({
                'cantidad': _("La cantidad no puede ser negativa")
            })
        
        if self.cantidad_danada < 0:
            raise ValidationError({
                'cantidad_danada': _("La cantidad dañada no puede ser negativa")
            })
        
        if self.cantidad == 0 and self.cantidad_danada == 0:
            raise ValidationError(
                _("Debe ingresar al menos una cantidad (buena o dañada)")
            )

    def get_cantidad_total(self):
        return self.cantidad + self.cantidad_danada

    def get_porcentaje_danado(self):
        total = self.get_cantidad_total()
        if total > 0:
            return (self.cantidad_danada / total) * 100
        return 0

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)