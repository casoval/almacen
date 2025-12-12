from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count, Q, F, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
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

    @staticmethod
    def obtener_estadisticas_rapidas(fecha_inicio=None, fecha_fin=None):
        """
        Versión optimizada que hace una sola query para estadísticas
        en lugar de múltiples counts separados.
        """
        from almacenes.models import MovimientoAlmacen
        from beneficiarios.models import MovimientoCliente
        
        filtros = Q()
        if fecha_inicio: filtros &= Q(fecha__gte=fecha_inicio)
        if fecha_fin: filtros &= Q(fecha__lte=fecha_fin)
        
        # 1. Stats Almacén (1 sola query)
        stats_alm = MovimientoAlmacen.objects.filter(filtros).aggregate(
            total=Count('id'),
            entradas=Count('id', filter=Q(tipo='ENTRADA')),
            salidas=Count('id', filter=Q(tipo='SALIDA')),
            traslados=Count('id', filter=Q(tipo='TRASLADO'))
        )
        
        # 2. Stats Clientes (1 sola query)
        stats_cli = MovimientoCliente.objects.filter(filtros).aggregate(
            total=Count('id'),
            entradas=Count('id', filter=Q(tipo='ENTRADA')),
            salidas=Count('id', filter=Q(tipo='SALIDA')),
            traslados=Count('id', filter=Q(tipo='TRASLADO'))
        )
        
        return {
            'total_global': (stats_alm['total'] or 0) + (stats_cli['total'] or 0),
            'almacen': stats_alm,
            'cliente': stats_cli
        }

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

    @staticmethod
    def obtener_entregas_optimizadas(fecha_inicio=None, fecha_fin=None, cliente_id=None, categoria_id=None, producto_id=None):
        """
        Realiza la agregación en Base de Datos usando Conditional Aggregation.
        Evita recorrer fila por fila en Python.
        """
        from beneficiarios.models import DetalleMovimientoCliente, Cliente
        from productos.models import Producto

        # 1. Filtros Base
        filtros = Q()
        if fecha_inicio: filtros &= Q(movimiento__fecha__gte=fecha_inicio)
        if fecha_fin: filtros &= Q(movimiento__fecha__lte=fecha_fin)
        if categoria_id: filtros &= Q(producto__categoria_id=categoria_id)
        if producto_id: filtros &= Q(producto_id=producto_id)
        
        # Filtros de cliente (complejo porque puede ser origen, destino o principal)
        if cliente_id:
            filtros &= (
                Q(movimiento__cliente_id=cliente_id) | 
                Q(movimiento__cliente_origen_id=cliente_id) | 
                Q(movimiento__cliente_destino_id=cliente_id)
            )

        # 2. Queryset Base
        qs = DetalleMovimientoCliente.objects.filter(filtros).select_related(
            'movimiento', 'producto', 'producto__unidad_medida', 'producto__categoria'
        )

        # 3. Diccionario para agrupar en memoria (pero con datos ya pre-filtrados)
        # Hacemos esto en memoria porque agrupar por "Cliente Efectivo" (que cambia según si es origen/destino)
        # es muy complejo en una sola query SQL pura sin subqueries lentas.
        
        reporte = {} 

        # Optimizamos iterando sobre values() que es más rápido que crear objetos Modelo
        datos_raw = qs.annotate(
            cli_principal=F('movimiento__cliente_id'),
            cli_origen=F('movimiento__cliente_origen_id'),
            cli_destino=F('movimiento__cliente_destino_id'),
            tipo_mov=F('movimiento__tipo'),
            prod_id=F('producto_id'),
            cant=F('cantidad'),
            cant_dan=F('cantidad_danada')
        ).values(
            'cli_principal', 'cli_origen', 'cli_destino', 'tipo_mov', 'prod_id', 
            'cant', 'cant_dan', 'movimiento_id'
        )

        # Cache de nombres para no hacer N queries
        clientes_cache = {c.id: c for c in Cliente.objects.filter(activo=True)}
        productos_cache = {p.id: p for p in Producto.objects.select_related('categoria', 'unidad_medida').all()}

        for row in datos_raw:
            pid = row['prod_id']
            tipo = row['tipo_mov']
            total = (row['cant'] or 0) + (row['cant_dan'] or 0)
            bueno = (row['cant'] or 0)
            danado = (row['cant_dan'] or 0)
            mov_id = row['movimiento_id']

            # Función helper para procesar la fila
            def agregar_registro(cid, tipo_registro):
                if not cid or cid not in clientes_cache or pid not in productos_cache: return
                
                key = (cid, pid)
                if key not in reporte:
                    reporte[key] = {
                        'cliente': clientes_cache[cid],
                        'producto': productos_cache[pid],
                        'total_entregas_ids': set(),
                        'cantidad_entrada': 0, 'cantidad_salida': 0,
                        'cantidad_traslado_origen': 0, 'cantidad_traslado_destino': 0,
                        'stock_bueno': 0, 'stock_danado': 0, 'stock_total': 0
                    }
                
                r = reporte[key]
                r['total_entregas_ids'].add(mov_id)
                
                if tipo_registro == 'ENTRADA':
                    r['cantidad_entrada'] += total
                    r['stock_bueno'] += bueno
                    r['stock_danado'] += danado
                elif tipo_registro == 'SALIDA':
                    r['cantidad_salida'] += total
                    r['stock_bueno'] -= bueno
                    r['stock_danado'] -= danado
                elif tipo_registro == 'T_ORIGEN': # Sale del cliente
                    r['cantidad_traslado_origen'] += total
                    r['stock_bueno'] -= bueno
                    r['stock_danado'] -= danado
                elif tipo_registro == 'T_DESTINO': # Entra al cliente
                    r['cantidad_traslado_destino'] += total
                    r['stock_bueno'] += bueno
                    r['stock_danado'] += danado

            # Lógica de distribución
            if tipo == 'TRASLADO':
                if row['cli_origen']: agregar_registro(row['cli_origen'], 'T_ORIGEN')
                if row['cli_destino']: agregar_registro(row['cli_destino'], 'T_DESTINO')
            elif tipo == 'ENTRADA':
                agregar_registro(row['cli_principal'], 'ENTRADA')
            elif tipo == 'SALIDA':
                agregar_registro(row['cli_principal'], 'SALIDA')

        # Convertir a lista plana
        resultado = []
        for data in reporte.values():
            data['total_entregas'] = len(data['total_entregas_ids'])
            data['stock_total'] = data['stock_bueno'] + data['stock_danado']
            del data['total_entregas_ids'] # Limpiar memoria
            resultado.append(data)
            
        return resultado

# ==============================================================================
# REPORTE DE STOCK (OPTIMIZADO)
# ==============================================================================
class ReporteStock(models.Model):
    class Meta:
        managed = False
        verbose_name = _("Reporte de Stock")
        verbose_name_plural = _("6.2. Reporte Exclusivo de Movimientos de Almacenes")
        
    @staticmethod
    def obtener_data_stock_masivo(almacen_id=None, categoria_id=None, producto_id=None, stock_minimo=False, solo_con_stock=False):
        """
        OPTIMIZACIÓN: Realiza una sola consulta agrupada para obtener el stock.
        Reduce de N*M consultas a 1 sola consulta.
        """
        from almacenes.models import DetalleMovimientoAlmacen
        from productos.models import Producto

        # 1. Base de productos
        productos = Producto.objects.filter(activo=True).select_related('categoria', 'unidad_medida')
        if categoria_id:
            productos = productos.filter(categoria_id=categoria_id)
        if producto_id:
            productos = productos.filter(id=producto_id)
            
        productos_map = {p.id: p for p in productos}
        producto_ids = list(productos_map.keys())

        # 2. Consulta Agregada (El corazón de la optimización)
        # Filtramos por los productos seleccionados para no traer toda la DB
        qs = DetalleMovimientoAlmacen.objects.filter(producto_id__in=producto_ids)
        
        # Filtro de almacén previo a la agregación
        filtros_destino = Q()
        filtros_origen = Q()
        
        if almacen_id:
            filtros_destino = Q(movimiento__almacen_destino_id=almacen_id)
            filtros_origen = Q(movimiento__almacen_origen_id=almacen_id)

        # Agrupamos por Producto y Almacén
        # Calculamos Entradas (Donde el almacén es Destino)
        entradas = qs.filter(
            filtros_destino,
            movimiento__tipo__in=['ENTRADA', 'TRASPASO', 'TRASLADO']
        ).values('producto_id', 'movimiento__almacen_destino_id').annotate(
            cant_buena=Sum('cantidad'),
            cant_danada=Sum('cantidad_danada')
        )

        # Calculamos Salidas (Donde el almacén es Origen)
        salidas = qs.filter(
            filtros_origen,
            movimiento__tipo__in=['SALIDA', 'TRASPASO', 'TRASLADO']
        ).values('producto_id', 'movimiento__almacen_origen_id').annotate(
            cant_buena=Sum('cantidad'),
            cant_danada=Sum('cantidad_danada')
        )

        # 3. Procesamiento en Memoria (Mucho más rápido que DB hits repetidos)
        reporte = {} # Key: (almacen_id, producto_id)

        # Procesar Entradas
        for e in entradas:
            alm_id = e['movimiento__almacen_destino_id']
            if not alm_id: continue
            prod_id = e['producto_id']
            key = (alm_id, prod_id)
            
            if key not in reporte: reporte[key] = _init_stock_struct()
            
            reporte[key]['entradas_total'] += (e['cant_buena'] or 0) + (e['cant_danada'] or 0)
            reporte[key]['stock_bueno'] += (e['cant_buena'] or 0)
            reporte[key]['stock_danado'] += (e['cant_danada'] or 0)

        # Procesar Salidas
        for s in salidas:
            alm_id = e['movimiento__almacen_origen_id'] if 'movimiento__almacen_origen_id' in s else s.get('movimiento__almacen_origen_id') # Safety check
            # Nota: en .values() el nombre del campo debe ser exacto.
            # Corrigiendo lógica de acceso:
            alm_id = s['movimiento__almacen_origen_id']

            if not alm_id: continue
            prod_id = s['producto_id']
            key = (alm_id, prod_id)
            
            if key not in reporte: reporte[key] = _init_stock_struct()
            
            reporte[key]['salidas_total'] += (s['cant_buena'] or 0) + (s['cant_danada'] or 0)
            reporte[key]['stock_bueno'] -= (s['cant_buena'] or 0)
            reporte[key]['stock_danado'] -= (s['cant_danada'] or 0)

        # 4. Construir lista final con objetos Producto y Almacén reales
        from almacenes.models import Almacen
        almacenes_map = {a.id: a for a in Almacen.objects.filter(activo=True)}
        
        resultado_final = []
        
        for (alm_id, prod_id), data in reporte.items():
            if alm_id not in almacenes_map or prod_id not in productos_map:
                continue
                
            data['stock_total'] = data['stock_bueno'] + data['stock_danado']
            data['almacen'] = almacenes_map[alm_id]
            data['producto'] = productos_map[prod_id]
            
            # Filtros post-cálculo
            if solo_con_stock and data['stock_total'] == 0:
                continue
                
            prod_obj = productos_map[prod_id]
            if stock_minimo and prod_obj.stock_minimo and data['stock_bueno'] > prod_obj.stock_minimo:
                continue

            resultado_final.append(data)
            
        return resultado_final

def _init_stock_struct():
    return {
        'entradas_total': Decimal('0'),
        'salidas_total': Decimal('0'),
        'stock_bueno': Decimal('0'),
        'stock_danado': Decimal('0'),
        'stock_total': Decimal('0'),
        'traslados_netos_total': Decimal('0') # Simplificado para este reporte
    }

# ==============================================================================
# REPORTE DE STOCK REAL (OPTIMIZADO EXTREMO)
# ==============================================================================
class ReporteStockReal(models.Model):
    class Meta:
        managed = False
        verbose_name = _("Reporte de Stock Real")
        verbose_name_plural = _("6.4. Reporte de Stock Real de Almacenes")
    
    @staticmethod
    def obtener_data_masiva(almacen_id=None, categoria_id=None, producto_id=None, stock_minimo=False, solo_con_stock=False):
        """
        Obtiene el stock real cruzando almacenes y clientes en una sola pasada.
        Evita 6 subconsultas por fila.
        """
        from almacenes.models import DetalleMovimientoAlmacen, Almacen
        from beneficiarios.models import DetalleMovimientoCliente
        from productos.models import Producto
        
        # 1. Preparar catálogos en memoria (Cache local)
        filtros_prod = {'activo': True}
        if categoria_id: filtros_prod['categoria_id'] = categoria_id
        if producto_id: filtros_prod['id'] = producto_id
        
        productos_map = {p.id: p for p in Producto.objects.filter(**filtros_prod).select_related('categoria', 'unidad_medida')}
        producto_ids_list = list(productos_map.keys())
        
        filtros_alm = {'activo': True}
        if almacen_id: filtros_alm['id'] = almacen_id
        almacenes_map = {a.id: a for a in Almacen.objects.filter(**filtros_alm)}
        almacen_ids_list = list(almacenes_map.keys())

        # Estructura de datos: dict[(almacen_id, producto_id)] = {datos...}
        stock_map = {}

        def get_node(aid, pid):
            key = (aid, pid)
            if key not in stock_map:
                stock_map[key] = {
                    'entradas_almacen_total': Decimal(0), 'salidas_almacen_total': Decimal(0),
                    'traslados_recibidos_total': Decimal(0), 'traslados_enviados_total': Decimal(0),
                    'entradas_cliente_total': Decimal(0), 'salidas_cliente_total': Decimal(0),
                    'stock_bueno': Decimal(0), 'stock_danado': Decimal(0), 'stock_total': Decimal(0)
                }
            return stock_map[key]

        # ---------------------------------------------------------
        # FASE 1: AGREGACIÓN DE ALMACÉN (Base de datos hace la suma)
        # ---------------------------------------------------------
        qs_alm = DetalleMovimientoAlmacen.objects.filter(
            producto_id__in=producto_ids_list
        ).values(
            'producto_id', 'movimiento__tipo', 
            'movimiento__almacen_origen_id', 'movimiento__almacen_destino_id'
        ).annotate(
            total_bueno=Sum('cantidad'),
            total_danado=Sum('cantidad_danada')
        )
        
        for item in qs_alm:
            pid = item['producto_id']
            tipo = item['movimiento__tipo']
            origen_id = item['movimiento__almacen_origen_id']
            destino_id = item['movimiento__almacen_destino_id']
            cant_b = item['total_bueno'] or 0
            cant_d = item['total_danado'] or 0
            total = cant_b + cant_d

            # Lógica de signos
            # Si el almacén es DESTINO (Entrada/Recibe)
            if destino_id and destino_id in almacenes_map:
                node = get_node(destino_id, pid)
                if tipo == 'ENTRADA':
                    node['entradas_almacen_total'] += total
                    node['stock_bueno'] += cant_b
                    node['stock_danado'] += cant_d
                elif tipo == 'TRASLADO':
                    node['traslados_recibidos_total'] += total
                    node['stock_bueno'] += cant_b
                    node['stock_danado'] += cant_d
            
            # Si el almacén es ORIGEN (Salida/Envía)
            if origen_id and origen_id in almacenes_map:
                node = get_node(origen_id, pid)
                if tipo == 'SALIDA':
                    node['salidas_almacen_total'] += total
                    node['stock_bueno'] -= cant_b
                    node['stock_danado'] -= cant_d
                elif tipo == 'TRASLADO':
                    node['traslados_enviados_total'] += total
                    node['stock_bueno'] -= cant_b
                    node['stock_danado'] -= cant_d

        # ---------------------------------------------------------
        # FASE 2: AGREGACIÓN DE CLIENTES
        # ---------------------------------------------------------
        qs_cli = DetalleMovimientoCliente.objects.filter(
            producto_id__in=producto_ids_list
        ).values(
            'producto_id', 'movimiento__tipo',
            'movimiento__almacen_origen_id', 'movimiento__almacen_destino_id'
        ).annotate(
            total_bueno=Sum('cantidad'),
            total_danado=Sum('cantidad_danada')
        )

        for item in qs_cli:
            pid = item['producto_id']
            tipo = item['movimiento__tipo']
            origen_id = item['movimiento__almacen_origen_id']
            destino_id = item['movimiento__almacen_destino_id']
            cant_b = item['total_bueno'] or 0
            cant_d = item['total_danado'] or 0
            total = cant_b + cant_d

            # Ojo: En clientes, "ENTRADA" significa que SALE del almacén hacia el cliente (RESTA del almacén)
            if origen_id and origen_id in almacenes_map and tipo == 'ENTRADA':
                node = get_node(origen_id, pid)
                node['entradas_cliente_total'] += total
                node['stock_bueno'] -= cant_b
                node['stock_danado'] -= cant_d
            
            # Ojo: En clientes, "SALIDA" significa que regresa del cliente (SUMA al almacén)
            if destino_id and destino_id in almacenes_map and tipo == 'SALIDA':
                node = get_node(destino_id, pid)
                node['salidas_cliente_total'] += total
                node['stock_bueno'] += cant_b
                node['stock_danado'] += cant_d

        # ---------------------------------------------------------
        # FASE 3: CONSTRUCCIÓN DE LA LISTA FINAL
        # ---------------------------------------------------------
        resultado = []
        for (aid, pid), data in stock_map.items():
            # Filtros finales
            data['stock_total'] = data['stock_bueno'] + data['stock_danado']
            
            # Filtro solo con stock (incluye negativos para alertar)
            if solo_con_stock and data['stock_total'] == 0:
                continue

            # Inyectar objetos reales
            data['almacen'] = almacenes_map[aid]
            data['producto'] = productos_map[pid]
            
            # Filtro stock mínimo
            if stock_minimo and productos_map[pid].stock_minimo and data['stock_bueno'] > productos_map[pid].stock_minimo:
                continue

            resultado.append(data)
            
        return resultado
        
    @staticmethod
    def calcular_stock_real_producto_almacen(producto, almacen):
        """Mantiene compatibilidad con vistas individuales, pero no usar en listas."""
        # Se puede reimplementar llamando a obtener_data_masiva filtrado
        res = ReporteStockReal.obtener_data_masiva(almacen_id=almacen.id, producto_id=producto.id)
        if res:
            return res[0]
        return {
             'entradas_almacen_total': 0, 'salidas_almacen_total': 0,
             'traslados_recibidos_total': 0, 'traslados_enviados_total': 0,
             'entradas_cliente_total': 0, 'salidas_cliente_total': 0,
             'stock_bueno': 0, 'stock_danado': 0, 'stock_total': 0
        }