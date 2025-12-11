from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count, Q, F
from decimal import Decimal


class ReporteMovimiento(models.Model):
    """
    Modelo proxy para facilitar consultas y reportes de movimientos
    No crea tabla en la base de datos, solo agrupa lógica de negocio
    """
    
    class Meta:
        managed = False  # No crear tabla
        verbose_name = _("Reporte de Movimientos")
        verbose_name_plural = _("6.1. Reporte de Movimientos de Almacenes y Clientes")
    
    @staticmethod
    def obtener_movimientos_almacen(fecha_inicio=None, fecha_fin=None, almacen=None, 
                                    tipo=None, proveedor=None, recepcionista=None):
        """
        Obtiene movimientos de almacén con filtros opcionales
        """
        from almacenes.models import MovimientoAlmacen
        
        qs = MovimientoAlmacen.objects.select_related(
            'almacen_origen',
            'almacen_destino',
            'proveedor',
            'recepcionista'
        ).prefetch_related(
            'detalles__producto__categoria',
            'detalles__producto__unidad_medida'
        )
        
        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)
        if almacen:
            qs = qs.filter(Q(almacen_origen=almacen) | Q(almacen_destino=almacen))
        if tipo:
            qs = qs.filter(tipo=tipo)
        if proveedor:
            qs = qs.filter(proveedor=proveedor)
        if recepcionista:
            qs = qs.filter(recepcionista=recepcionista)
        
        return qs.order_by('-fecha', '-numero_movimiento')
    
    @staticmethod
    def obtener_movimientos_cliente(fecha_inicio=None, fecha_fin=None, cliente=None,
                                    tipo=None, proveedor=None, recepcionista=None):
        """
        Obtiene movimientos de cliente con filtros opcionales
        """
        from beneficiarios.models import MovimientoCliente
        
        qs = MovimientoCliente.objects.select_related(
            'cliente',
            'cliente_origen',
            'cliente_destino',
            'almacen_origen',
            'almacen_destino',
            'proveedor',
            'recepcionista'
        ).prefetch_related(
            'detalles__producto__categoria',
            'detalles__producto__unidad_medida'
        )
        
        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)
        if cliente:
            qs = qs.filter(Q(cliente=cliente) | Q(cliente_origen=cliente) | Q(cliente_destino=cliente))
        if tipo:
            qs = qs.filter(tipo=tipo)
        if proveedor:
            qs = qs.filter(proveedor=proveedor)
        if recepcionista:
            qs = qs.filter(recepcionista=recepcionista)
        
        return qs.order_by('-fecha', '-numero_movimiento')
    
    @staticmethod
    def estadisticas_generales(fecha_inicio=None, fecha_fin=None):
        """
        Retorna estadísticas generales de movimientos
        """
        from almacenes.models import DetalleMovimientoAlmacen
        from beneficiarios.models import DetalleMovimientoCliente
        
        # Filtros de fecha
        filtros_almacen = Q()
        filtros_cliente = Q()
        
        if fecha_inicio:
            filtros_almacen &= Q(movimiento__fecha__gte=fecha_inicio)
            filtros_cliente &= Q(movimiento__fecha__gte=fecha_inicio)
        if fecha_fin:
            filtros_almacen &= Q(movimiento__fecha__lte=fecha_fin)
            filtros_cliente &= Q(movimiento__fecha__lte=fecha_fin)
        
        # Estadísticas de almacén
        stats_almacen = DetalleMovimientoAlmacen.objects.filter(filtros_almacen).aggregate(
            total_movimientos=Count('movimiento', distinct=True),
            total_productos_buena=Sum('cantidad'),
            total_productos_danada=Sum('cantidad_danada'),
            entradas=Count('movimiento', filter=Q(movimiento__tipo='ENTRADA'), distinct=True),
            salidas=Count('movimiento', filter=Q(movimiento__tipo='SALIDA'), distinct=True),
            traslados=Count('movimiento', filter=Q(movimiento__tipo='TRASLADO'), distinct=True)
        )
        
        # Estadísticas de cliente
        stats_cliente = DetalleMovimientoCliente.objects.filter(filtros_cliente).aggregate(
            total_movimientos=Count('movimiento', distinct=True),
            total_productos_buena=Sum('cantidad'),
            total_productos_danada=Sum('cantidad_danada'),
            entradas=Count('movimiento', filter=Q(movimiento__tipo='ENTRADA'), distinct=True),
            salidas=Count('movimiento', filter=Q(movimiento__tipo='SALIDA'), distinct=True),
            traslados=Count('movimiento', filter=Q(movimiento__tipo='TRASLADO'), distinct=True)
        )
        
        return {
            'almacen': stats_almacen,
            'cliente': stats_cliente,
            'total_movimientos': (stats_almacen['total_movimientos'] or 0) + (stats_cliente['total_movimientos'] or 0),
            'total_productos': (stats_almacen['total_productos_buena'] or 0) + (stats_cliente['total_productos_buena'] or 0)
        }
    
    @staticmethod
    def productos_mas_movidos(fecha_inicio=None, fecha_fin=None, limite=10):
        """
        Retorna los productos con más movimientos
        """
        from almacenes.models import DetalleMovimientoAlmacen
        from beneficiarios.models import DetalleMovimientoCliente
    
        filtros = Q()
        if fecha_inicio:
            filtros &= Q(movimiento__fecha__gte=fecha_inicio)
        if fecha_fin:
            filtros &= Q(movimiento__fecha__lte=fecha_fin)
    
    # ✅ Combinar datos de almacén - CORREGIDO
        productos_almacen = DetalleMovimientoAlmacen.objects.filter(filtros).values(
            'producto__id',
            'producto__codigo',
            'producto__nombre',
            'producto__unidad_medida__abreviatura'
        ).annotate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada'),
            total_movimientos=Count('movimiento', distinct=True)
        )
    
    # ✅ Combinar datos de cliente - CORREGIDO
        productos_cliente = DetalleMovimientoCliente.objects.filter(filtros).values(
            'producto__id',
            'producto__codigo',
            'producto__nombre',
            'producto__unidad_medida__abreviatura'
        ).annotate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada'),
            total_movimientos=Count('movimiento', distinct=True)
        )
    
    # ✅ Combinar resultados y calcular total_cantidad en Python
        productos_dict = {}
    
        for item in productos_almacen:
            pid = item['producto__id']
            total_cantidad = (item['cantidad_buena'] or 0) + (item['cantidad_danada'] or 0)
            productos_dict[pid] = {
                'id': pid,
                'codigo': item['producto__codigo'],
                'nombre': item['producto__nombre'],
                'unidad': item['producto__unidad_medida__abreviatura'],
                'total_cantidad': total_cantidad,
                'total_movimientos': item['total_movimientos'] or 0
            }
    
        for item in productos_cliente:
            pid = item['producto__id']
            total_cantidad = (item['cantidad_buena'] or 0) + (item['cantidad_danada'] or 0)
        
            if pid in productos_dict:
                productos_dict[pid]['total_cantidad'] += total_cantidad
                productos_dict[pid]['total_movimientos'] += item['total_movimientos'] or 0
            else:
                productos_dict[pid] = {
                    'id': pid,
                    'codigo': item['producto__codigo'],
                    'nombre': item['producto__nombre'],
                    'unidad': item['producto__unidad_medida__abreviatura'],
                    'total_cantidad': total_cantidad,
                    'total_movimientos': item['total_movimientos'] or 0
                }
    
        # Ordenar por cantidad total y limitar
        resultado = sorted(productos_dict.values(), key=lambda x: x['total_cantidad'], reverse=True)
        return resultado[:limite]


# ==============================================================================
# REPORTE DE ENTREGAS (Implementación corregida) ⭐
# ==============================================================================

class ReporteEntregas(models.Model):
    """
    Modelo proxy para reportes de entregas a clientes
    """
    
    class Meta:
        managed = False
        verbose_name = _("Reporte de Entregas")
        verbose_name_plural = _("6.3. Reporte Exclusivo de Movimientos de Clientes / Beneficiarios")

    @staticmethod
    def obtener_reporte(fecha_inicio=None, fecha_fin=None, cliente_id=None, 
                         producto_id=None, vista='detallado', mostrar_todos=False): # <--- Asegurar parámetro
        """
        Calcula el resumen de entregas a clientes
        """
        from beneficiarios.models import MovimientoCliente, DetalleMovimientoCliente
    
        qs = MovimientoCliente.objects.filter(tipo='SALIDA')
    
        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)
    
        # 1. Resumen General
        resumen_movimientos = qs.aggregate(
            total_movimientos=Count('id'),
            total_clientes=Count('cliente', distinct=True),
        )
    
        # 2. Productos Entregados
        productos_entregados = DetalleMovimientoCliente.objects.filter(
            movimiento__in=qs
        ).aggregate(
            total_cantidad=Sum('cantidad'),
            total_danada=Sum('cantidad_danada')
        )
    
        total_productos = (productos_entregados['total_cantidad'] or 0) + (productos_entregados['total_danada'] or 0)
    
        resumen_general = {
            'total_entregas': resumen_movimientos['total_movimientos'] or 0,
            'total_clientes': resumen_movimientos['total_clientes'] or 0,
            'total_productos': total_productos,
        }
    
        # 3. Top Clientes
        top_clientes_qs = qs.values(
            'cliente__codigo',
            'cliente__nombre'
        ).annotate(
            total_entregas=Count('id'),
            cantidad_buena=Sum('detalles__cantidad'),
            cantidad_danada=Sum('detalles__cantidad_danada')
        ).order_by('-cantidad_buena')[:10]
    
        # Calcular total_productos manualmente
        top_clientes_list = []
        for cliente in top_clientes_qs:
            total_productos = (cliente['cantidad_buena'] or 0) + (cliente['cantidad_danada'] or 0)
            top_clientes_list.append({
                'cliente__codigo': cliente['cliente__codigo'],
                'cliente__nombre': cliente['cliente__nombre'],
                'total_entregas': cliente['total_entregas'],
                'total_productos': total_productos
            })
    
        # 4. Top Productos
        top_productos_qs = DetalleMovimientoCliente.objects.filter(
            movimiento__in=qs
        ).values(
            'producto__codigo',
            'producto__nombre',
            'producto__unidad_medida__abreviatura'
        ).annotate(
            cantidad_buena=Sum('cantidad'),
            cantidad_danada=Sum('cantidad_danada'),
            total_movimientos=Count('movimiento', distinct=True)
        ).order_by('-cantidad_buena')[:10]
    
        # Calcular total_cantidad manualmente
        top_productos_list = []
        for producto in top_productos_qs:
            total_cantidad = (producto['cantidad_buena'] or 0) + (producto['cantidad_danada'] or 0)
            top_productos_list.append({
                'producto__codigo': producto['producto__codigo'],
                'producto__nombre': producto['producto__nombre'],
                'producto__unidad_medida__abreviatura': producto['producto__unidad_medida__abreviatura'],
                'total_cantidad': total_cantidad,
                'total_movimientos': producto['total_movimientos']
            })
    
        return {
            'resumen_general': resumen_general,
            'resumen_clientes': top_clientes_list,
            'resumen_productos_top': top_productos_list,
        }

# ==============================================================================
# REPORTE DE STOCK (Implementación completa) ⭐
# ==============================================================================

class ReporteStock(models.Model):
    """
    Modelo proxy para reportes de stock actual
    """
    
    class Meta:
        managed = False
        verbose_name = _("Reporte de Stock")
        verbose_name_plural = _("6.2. Reporte Exclusivo de Movimientos de Almacenes")
        
    # ⭐ Implementación del método que trae los datos de stock
    @staticmethod
    def obtener_data_stock_actual(almacen_id=None, categoria_id=None, producto_id=None):
        """
        Obtiene el stock actual agrupado por producto, filtrando por almacén y/o categoría.
        Stock = Suma(Entradas) - Suma(Salidas)
        """
        from almacenes.models import DetalleMovimientoAlmacen
        from productos.models import Producto
        
        qs_productos = Producto.objects.filter(activo=True).select_related('categoria', 'unidad_medida')
        
        if categoria_id:
            qs_productos = qs_productos.filter(categoria_id=categoria_id)
        if producto_id:
            qs_productos = qs_productos.filter(id=producto_id)
            
        data = []
        for producto in qs_productos:
            # 1. Calcular Entradas para este producto
            # Entradas: Movimiento tipo ENTRADA o TRASPASO con almacen_destino_id
            q_entradas = Q(movimiento__tipo__in=['ENTRADA', 'TRASPASO']) & Q(producto=producto)
            if almacen_id:
                # Si se filtra por almacén, las entradas son aquellas que TIENEN ese almacén como DESTINO
                q_entradas &= Q(movimiento__almacen_destino_id=almacen_id)

            entradas_agg = DetalleMovimientoAlmacen.objects.filter(q_entradas).aggregate(
                total_cantidad=Sum('cantidad'),
                total_danada=Sum('cantidad_danada')
            )
            
            # 2. Calcular Salidas para este producto
            # Salidas: Movimiento tipo SALIDA o TRASPASO con almacen_origen_id
            q_salidas = Q(movimiento__tipo__in=['SALIDA', 'TRASPASO']) & Q(producto=producto)
            if almacen_id:
                # Si se filtra por almacén, las salidas son aquellas que TIENEN ese almacén como ORIGEN
                q_salidas &= Q(movimiento__almacen_origen_id=almacen_id)

            salidas_agg = DetalleMovimientoAlmacen.objects.filter(q_salidas).aggregate(
                total_cantidad=Sum('cantidad'),
                total_danada=Sum('cantidad_danada')
            )
            
            stock_bueno = (entradas_agg['total_cantidad'] or 0) - (salidas_agg['total_cantidad'] or 0)
            stock_danado = (entradas_agg['total_danada'] or 0) - (salidas_agg['total_danada'] or 0)
            stock_total = stock_bueno + stock_danado
            
            # Solo incluir productos con stock total > 0 (opcional, pero útil)
            if stock_total > 0:
                data.append({
                    'id': producto.id,
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else '-',
                    'categoria': producto.categoria.nombre if producto.categoria else '-',
                    'stock_bueno': stock_bueno,
                    'stock_danado': stock_danado,
                    'stock_total': stock_total,
                })
        
        return data

# ==============================================================================
# REPORTE DE STOCK REAL DE ALMACENES (considera movimientos de clientes)
# ==============================================================================

class ReporteStockReal(models.Model):
    """
    Modelo proxy para reportes de stock real de almacenes
    Calcula el stock considerando TANTO movimientos de almacén COMO de clientes
    """
    
    class Meta:
        managed = False
        verbose_name = _("Reporte de Stock Real")
        verbose_name_plural = _("6.4. Reporte de Stock Real de Almacenes")
    
    @staticmethod
    def calcular_stock_real_producto_almacen(producto, almacen):
        """
        Calcula el stock REAL de un producto en un almacén específico
        Considera movimientos de almacén Y movimientos de clientes
        
        FÓRMULA:
        Stock Real = 
          + Entradas de Almacén
          - Salidas de Almacén
          + Traslados Recibidos (de otros almacenes)
          - Traslados Enviados (a otros almacenes)
          - Entradas de Cliente (salen del almacén hacia cliente)
          + Salidas de Cliente (regresan del cliente al almacén)
        """
        from almacenes.models import DetalleMovimientoAlmacen
        from beneficiarios.models import DetalleMovimientoCliente
        from decimal import Decimal
        
        # ====== MOVIMIENTOS DE ALMACÉN ======
        
        # 1. ENTRADAS de almacén (productos que ingresan)
        entradas_almacen = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(
            buena=Sum('cantidad'),
            danada=Sum('cantidad_danada')
        )
        
        entradas_alm_buena = Decimal(str(entradas_almacen['buena'] or 0))
        entradas_alm_danada = Decimal(str(entradas_almacen['danada'] or 0))
        
        # 2. SALIDAS de almacén (productos que salen)
        salidas_almacen = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(
            buena=Sum('cantidad'),
            danada=Sum('cantidad_danada')
        )
        
        salidas_alm_buena = Decimal(str(salidas_almacen['buena'] or 0))
        salidas_alm_danada = Decimal(str(salidas_almacen['danada'] or 0))
        
        # 3. TRASLADOS RECIBIDOS (de otros almacenes hacia este)
        traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(
            buena=Sum('cantidad'),
            danada=Sum('cantidad_danada')
        )
        
        traslados_rec_buena = Decimal(str(traslados_recibidos['buena'] or 0))
        traslados_rec_danada = Decimal(str(traslados_recibidos['danada'] or 0))
        
        # 4. TRASLADOS ENVIADOS (desde este almacén a otros)
        traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(
            buena=Sum('cantidad'),
            danada=Sum('cantidad_danada')
        )
        
        traslados_env_buena = Decimal(str(traslados_enviados['buena'] or 0))
        traslados_env_danada = Decimal(str(traslados_enviados['danada'] or 0))
        
        # ====== MOVIMIENTOS DE CLIENTE ======
        
        # 5. ENTRADAS de cliente (productos que SALEN del almacén hacia clientes)
        entradas_cliente = DetalleMovimientoCliente.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(
            buena=Sum('cantidad'),
            danada=Sum('cantidad_danada')
        )
        
        entradas_cli_buena = Decimal(str(entradas_cliente['buena'] or 0))
        entradas_cli_danada = Decimal(str(entradas_cliente['danada'] or 0))
        
        # 6. SALIDAS de cliente (productos que REGRESAN del cliente al almacén)
        salidas_cliente = DetalleMovimientoCliente.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(
            buena=Sum('cantidad'),
            danada=Sum('cantidad_danada')
        )
        
        salidas_cli_buena = Decimal(str(salidas_cliente['buena'] or 0))
        salidas_cli_danada = Decimal(str(salidas_cliente['danada'] or 0))
        
        # NOTA: Ignoramos TRASLADO entre clientes (no afectan stock de almacén)
        
        # ====== CÁLCULO FINAL ======
        
        stock_bueno = (
            entradas_alm_buena +           # Suma: entradas de almacén
            traslados_rec_buena -          # Suma: traslados recibidos
            salidas_alm_buena -            # Resta: salidas de almacén
            traslados_env_buena -          # Resta: traslados enviados
            entradas_cli_buena +           # Resta: entradas de cliente (salen del almacén)
            salidas_cli_buena              # Suma: salidas de cliente (regresan al almacén)
        )
        
        stock_danado = (
            entradas_alm_danada +
            traslados_rec_danada -
            salidas_alm_danada -
            traslados_env_danada -
            entradas_cli_danada +
            salidas_cli_danada
        )
        
        return {
            # Movimientos de Almacén
            'entradas_almacen_buena': float(entradas_alm_buena),
            'entradas_almacen_danada': float(entradas_alm_danada),
            'entradas_almacen_total': float(entradas_alm_buena + entradas_alm_danada),
            
            'salidas_almacen_buena': float(salidas_alm_buena),
            'salidas_almacen_danada': float(salidas_alm_danada),
            'salidas_almacen_total': float(salidas_alm_buena + salidas_alm_danada),
            
            'traslados_recibidos_buena': float(traslados_rec_buena),
            'traslados_recibidos_danada': float(traslados_rec_danada),
            'traslados_recibidos_total': float(traslados_rec_buena + traslados_rec_danada),
            
            'traslados_enviados_buena': float(traslados_env_buena),
            'traslados_enviados_danada': float(traslados_env_danada),
            'traslados_enviados_total': float(traslados_env_buena + traslados_env_danada),
            
            # Movimientos de Cliente
            'entradas_cliente_buena': float(entradas_cli_buena),
            'entradas_cliente_danada': float(entradas_cli_danada),
            'entradas_cliente_total': float(entradas_cli_buena + entradas_cli_danada),
            
            'salidas_cliente_buena': float(salidas_cli_buena),
            'salidas_cliente_danada': float(salidas_cli_danada),
            'salidas_cliente_total': float(salidas_cli_buena + salidas_cli_danada),
            
            # Stock Real Final
            'stock_bueno': float(stock_bueno),
            'stock_danado': float(stock_danado),
            'stock_total': float(stock_bueno + stock_danado)
        }