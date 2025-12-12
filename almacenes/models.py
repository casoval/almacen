from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from productos.models import Producto
from django.utils import timezone
from proveedores.models import Proveedor
from recepcionistas.models import Recepcionista
from django.db.models import Sum, Q


class Almacen(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name=_("Nombre"))
    codigo = models.CharField(
        max_length=20, 
        unique=True, 
        blank=False,
        null=False,
        verbose_name=_("Código")
    )
    direccion = models.TextField(blank=True, null=True, verbose_name=_("Dirección"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Almacén")
        verbose_name_plural = _("1.1. Almacenes")
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def get_stock_producto(self, producto):
        """
        Calcula el stock actual de un producto en este almacén
        """
        # 1. ENTRADAS: Movimientos tipo ENTRADA donde este almacén es el DESTINO
        entradas = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_destino=self,
            producto=producto
        ).aggregate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada')
        )
        
        entradas_buena = float(entradas['cantidad_buena'] or 0)
        entradas_danada = float(entradas['cantidad_danada'] or 0)
        
        # 2. SALIDAS: Movimientos tipo SALIDA donde este almacén es el ORIGEN
        salidas = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_origen=self,
            producto=producto
        ).aggregate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada')
        )
        
        salidas_buena = float(salidas['cantidad_buena'] or 0)
        salidas_danada = float(salidas['cantidad_danada'] or 0)
        
        # 3. TRASLADOS RECIBIDOS: Movimientos tipo TRASLADO donde este almacén es el DESTINO
        traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_destino=self,
            producto=producto
        ).aggregate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada')
        )
        
        traslados_recibidos_buena = float(traslados_recibidos['cantidad_buena'] or 0)
        traslados_recibidos_danada = float(traslados_recibidos['cantidad_danada'] or 0)
        
        # 4. TRASLADOS ENVIADOS: Movimientos tipo TRASLADO donde este almacén es el ORIGEN
        traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_origen=self,
            producto=producto
        ).aggregate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada')
        )
        
        traslados_enviados_buena = float(traslados_enviados['cantidad_buena'] or 0)
        traslados_enviados_danada = float(traslados_enviados['cantidad_danada'] or 0)
        
        # 5. CALCULAR STOCK FINAL
        stock_bueno = (entradas_buena - salidas_buena + 
                      traslados_recibidos_buena - traslados_enviados_buena)
        
        stock_danado = (entradas_danada - salidas_danada + 
                       traslados_recibidos_danada - traslados_enviados_danada)
        
        # 6. TRASLADOS NETOS
        traslados_netos_buena = traslados_recibidos_buena - traslados_enviados_buena
        traslados_netos_danada = traslados_recibidos_danada - traslados_enviados_danada
        
        return {
            'entradas_buena': entradas_buena,
            'entradas_danada': entradas_danada,
            'entradas_total': entradas_buena + entradas_danada,
            'salidas_buena': salidas_buena,
            'salidas_danada': salidas_danada,
            'salidas_total': salidas_buena + salidas_danada,
            'traslados_recibidos_buena': traslados_recibidos_buena,
            'traslados_recibidos_danada': traslados_recibidos_danada,
            'traslados_recibidos_total': traslados_recibidos_buena + traslados_recibidos_danada,
            'traslados_enviados_buena': traslados_enviados_buena,
            'traslados_enviados_danada': traslados_enviados_danada,
            'traslados_enviados_total': traslados_enviados_buena + traslados_enviados_danada,
            'traslados_netos_buena': traslados_netos_buena,
            'traslados_netos_danada': traslados_netos_danada,
            'traslados_netos_total': traslados_netos_buena + traslados_netos_danada,
            'stock_bueno': stock_bueno,
            'stock_danado': stock_danado,
            'stock_total': stock_bueno + stock_danado
        }

    def get_todos_los_stocks(self):
        """
        Retorna un diccionario con el stock de todos los productos en este almacén.
        """
        productos_con_movimientos = Producto.objects.filter(
            Q(detallemovimientoalmacen__movimiento__almacen_origen=self) |
            Q(detallemovimientoalmacen__movimiento__almacen_destino=self)
        ).distinct()
        
        stocks = {}
        for producto in productos_con_movimientos:
            stock_data = self.get_stock_producto(producto)
            stocks[producto] = stock_data
        
        return stocks


class MovimientoAlmacen(models.Model):
    TIPO_MOVIMIENTO = (
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('TRASLADO', 'Traslado entre almacenes'),
    )

    almacen_origen = models.ForeignKey(
        Almacen, 
        related_name='salidas', 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        verbose_name=_("Almacén Origen")
    )
    almacen_destino = models.ForeignKey(
        Almacen, 
        related_name='entradas', 
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
        blank=False,
        null=False,
        related_name='movimientos_almacen',
        verbose_name=_("Proveedor"),
        help_text=_("Proveedor del que se reciben los productos")
    )
    recepcionista = models.ForeignKey(
        Recepcionista,
        on_delete=models.PROTECT,
        blank=False,
        null=False,
        related_name='movimientos_almacen',
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
        verbose_name = _("Movimiento de Almacén")
        verbose_name_plural = _("1.2. Movimientos de Almacén")
        ordering = ['tipo', '-numero_movimiento']
        # =========================================================
        # 🚀 OPTIMIZACIÓN: ÍNDICES PARA BÚSQUEDAS RÁPIDAS
        # =========================================================
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['tipo']),
            models.Index(fields=['almacen_origen']),
            models.Index(fields=['almacen_destino']),
            models.Index(fields=['proveedor']),
            models.Index(fields=['recepcionista']),
            # Índice compuesto para el dashboard (filtrar por fecha Y tipo a la vez)
            models.Index(fields=['fecha', 'tipo']),
        ]

    def __str__(self):
        return f"{self.numero_movimiento} - {self.tipo}"

    def clean(self):
        """Validación de lógica de negocio"""
        if self.tipo == 'ENTRADA' and not self.almacen_destino:
            raise ValidationError({
                'almacen_destino': _("Una entrada debe tener almacén destino")
            })
        
        if self.tipo == 'SALIDA' and not self.almacen_origen:
            raise ValidationError({
                'almacen_origen': _("Una salida debe tener almacén origen")
            })
        
        if self.tipo == 'TRASLADO':
            if not self.almacen_origen or not self.almacen_destino:
                raise ValidationError(
                    _("Un traslado requiere almacén origen y destino")
                )
            if self.almacen_origen == self.almacen_destino:
                raise ValidationError(
                    _("El almacén origen y destino no pueden ser el mismo")
                )

    def save(self, *args, **kwargs):
        """Genera el número de movimiento automáticamente POR ALMACÉN"""
        if not self.numero_movimiento:
            almacen_referencia = None
            
            if self.tipo == 'ENTRADA':
                almacen_referencia = self.almacen_destino
            elif self.tipo == 'SALIDA':
                almacen_referencia = self.almacen_origen
            elif self.tipo == 'TRASLADO':
                almacen_referencia = self.almacen_origen
            
            if not almacen_referencia:
                raise ValidationError(_("No se puede generar número de movimiento sin almacén"))
            
            filtro_query = {'tipo': self.tipo}
            
            if self.tipo == 'ENTRADA':
                filtro_query['almacen_destino'] = almacen_referencia
            elif self.tipo == 'SALIDA':
                filtro_query['almacen_origen'] = almacen_referencia
            elif self.tipo == 'TRASLADO':
                filtro_query['almacen_origen'] = almacen_referencia
            
            ultimo_movimiento = MovimientoAlmacen.objects.filter(
                **filtro_query
            ).order_by('-id').first()
            
            if ultimo_movimiento and ultimo_movimiento.numero_movimiento:
                try:
                    ultimo_numero = int(ultimo_movimiento.numero_movimiento.split('-')[-1])
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
            
            codigo_almacen = almacen_referencia.codigo or almacen_referencia.nombre[:3].upper()
            self.numero_movimiento = f"{codigo_almacen}/{prefijo}-{nuevo_numero:04d}"
        
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


class DetalleMovimientoAlmacen(models.Model):
    movimiento = models.ForeignKey(
        MovimientoAlmacen,
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
        verbose_name_plural = _("1.3. Detalles de Movimientos")
        ordering = ['movimiento__tipo', '-movimiento__numero_movimiento', 'id']
        unique_together = [['movimiento', 'producto']]
        # =========================================================
        # 🚀 OPTIMIZACIÓN: ÍNDICES PARA CÁLCULOS DE STOCK
        # =========================================================
        indexes = [
            models.Index(fields=['producto']),
            models.Index(fields=['movimiento']),
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