import traceback
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Sum, Count, F
from django.db.models.functions import TruncMonth
from datetime import datetime
import csv
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.utils.translation import gettext_lazy as _

from almacenes.models import MovimientoAlmacen, Almacen, DetalleMovimientoAlmacen
from beneficiarios.models import MovimientoCliente, Cliente, DetalleMovimientoCliente
from productos.models import Producto
from reportes.models import ReporteStock, ReporteEntregas, ReporteMovimiento


def obtener_datos_graficos_movimientos(request):
    """
    Retorna datos agregados por mes para graficar Entradas vs Salidas.
    ✅ CORREGIDO: Usa los nombres correctos de campos
    """
    try:
        # 1. Obtener filtros de la solicitud
        fecha_inicio_str = request.GET.get('fecha_inicio')
        fecha_fin_str = request.GET.get('fecha_fin')
        almacen_id = request.GET.get('almacen')
        proveedor_id = request.GET.get('proveedor')
        recepcionista_id = request.GET.get('recepcionista')

        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else None
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else None

        from reportes.models import ReporteMovimiento
        from django.db.models.functions import Coalesce
        
        # 2. Obtener movimientos de ALMACÉN agregados por mes
        movimientos_almacen = ReporteMovimiento.obtener_movimientos_almacen(
            fecha_inicio=fecha_inicio, 
            fecha_fin=fecha_fin, 
            almacen=almacen_id,
            proveedor=proveedor_id, 
            recepcionista=recepcionista_id
        ).annotate(
            mes=TruncMonth('fecha')
        ).values('mes').annotate(
            # ✅ CORRECCIÓN: Usar 'cantidad' en lugar de 'cantidad_buena'
            entradas_almacen=Coalesce(
                Sum('detalles__cantidad', filter=Q(tipo='ENTRADA')),
                Decimal('0')
            ) + Coalesce(
                Sum('detalles__cantidad_danada', filter=Q(tipo='ENTRADA')),
                Decimal('0')
            ),
            salidas_almacen=Coalesce(
                Sum('detalles__cantidad', filter=Q(tipo='SALIDA')),
                Decimal('0')
            ) + Coalesce(
                Sum('detalles__cantidad_danada', filter=Q(tipo='SALIDA')),
                Decimal('0')
            ),
            traslados_enviados=Coalesce(
                Sum('detalles__cantidad', filter=Q(tipo='TRASLADO')),
                Decimal('0')
            ) + Coalesce(
                Sum('detalles__cantidad_danada', filter=Q(tipo='TRASLADO')),
                Decimal('0')
            )
        ).order_by('mes')
        
        # 3. Procesar datos para Chart.js
        fechas = []
        entradas = []
        salidas = []
        traslados = []
        
        for item in movimientos_almacen:
            mes_str = item['mes'].strftime('%Y-%m')
            fechas.append(mes_str)
            entradas.append(float(item['entradas_almacen'] or 0))
            salidas.append(float(item['salidas_almacen'] or 0))
            traslados.append(float(item['traslados_enviados'] or 0))
            
        # 4. Estructura de datos para Chart.js
        datos = {
            'labels': fechas,
            'datasets': [
                {
                    'label': 'Entradas',
                    'data': entradas,
                    'backgroundColor': 'rgba(46, 204, 113, 0.2)',
                    'borderColor': 'rgba(46, 204, 113, 1)',
                    'borderWidth': 2,
                    'fill': True,
                    'tension': 0.4,
                },
                {
                    'label': 'Salidas',
                    'data': salidas,
                    'backgroundColor': 'rgba(231, 76, 60, 0.2)',
                    'borderColor': 'rgba(231, 76, 60, 1)',
                    'borderWidth': 2,
                    'fill': True,
                    'tension': 0.4,
                },
                {
                    'label': 'Traslados',
                    'data': traslados,
                    'backgroundColor': 'rgba(52, 152, 219, 0.2)',
                    'borderColor': 'rgba(52, 152, 219, 1)',
                    'borderWidth': 2,
                    'fill': True,
                    'tension': 0.4,
                }
            ]
        }

        return JsonResponse(datos)

    except Exception as e:
        print(f"❌ ERROR en obtener_datos_graficos_movimientos: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e), 
            'traceback': traceback.format_exc()
        }, status=500)

def exportar_movimientos_excel(request):
    """Exporta los movimientos filtrados a Excel"""
    
# Obtener filtros
    tipo_reporte = request.GET.get('tipo_reporte', 'almacen')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    almacen_id = request.GET.get('almacen')
    cliente_id = request.GET.get('cliente')
    proveedor_id = request.GET.get('proveedor')
    recepcionista_id = request.GET.get('recepcionista')
    producto_id = request.GET.get('producto')
    numero_movimiento = request.GET.get('numero_movimiento', '').strip() # ⭐ CORRECCIÓN: Agregar filtro de número
    
    # Convertir fechas
    fecha_inicio_obj = None
    fecha_fin_obj = None
    
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Construir queryset según tipo de reporte
    if tipo_reporte == 'almacen':
        movimientos = MovimientoAlmacen.objects.all()
        
        if fecha_inicio_obj:
            movimientos = movimientos.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos = movimientos.filter(fecha__lte=fecha_fin_obj)
        if tipo_movimiento:
            movimientos = movimientos.filter(tipo=tipo_movimiento)
        if almacen_id:
            movimientos = movimientos.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if proveedor_id:
            movimientos = movimientos.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos = movimientos.filter(recepcionista_id=recepcionista_id)
        if producto_id:
            movimientos = movimientos.filter(detalles__producto_id=producto_id).distinct()
        
# ⭐ CORRECCIÓN: Aplicar filtro de número de movimiento
        if numero_movimiento:
            movimientos = movimientos.filter(numero_movimiento__icontains=numero_movimiento)
            
        movimientos = movimientos.select_related(
            'almacen_origen', 'almacen_destino', 'proveedor', 'recepcionista'
        ).prefetch_related('detalles__producto__unidad_medida').order_by('-fecha')
        
    else:  # cliente
        movimientos = MovimientoCliente.objects.all()
        
        if fecha_inicio_obj:
            movimientos = movimientos.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos = movimientos.filter(fecha__lte=fecha_fin_obj)
        if tipo_movimiento:
            movimientos = movimientos.filter(tipo=tipo_movimiento)
        if cliente_id:
            movimientos = movimientos.filter(cliente_id=cliente_id)
        if almacen_id:
            movimientos = movimientos.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if proveedor_id:
            movimientos = movimientos.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos = movimientos.filter(recepcionista_id=recepcionista_id)
        if producto_id:
            movimientos = movimientos.filter(detalles__producto_id=producto_id).distinct()
        
 # ⭐ CORRECCIÓN: Aplicar filtro de número de movimiento
        if numero_movimiento:
            movimientos = movimientos.filter(numero_movimiento__icontains=numero_movimiento)
        
        movimientos = movimientos.select_related(
            'cliente', 'almacen_origen', 'almacen_destino', 'proveedor', 'recepcionista'
        ).prefetch_related('detalles__producto__unidad_medida').order_by('-fecha')
    
    # Crear workbook
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Resumen Movimientos"
    
    # Estilos
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados hoja 1
    if tipo_reporte == 'almacen':
        headers = ['N° Movimiento', 'Tipo', 'Fecha', 'Almacén Origen', 'Almacén Destino', 
                   'Proveedor', 'Recepcionista', 'Total Productos']
    else:
        headers = ['N° Movimiento', 'Tipo', 'Fecha', 'Cliente', 'Almacén Origen', 
                   'Almacén Destino', 'Proveedor', 'Recepcionista', 'Total Productos']
    
    for col, header in enumerate(headers, start=1):
        cell = ws1.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos hoja 1
    for row_idx, movimiento in enumerate(movimientos, start=2):
        if tipo_reporte == 'almacen':
            row_data = [
                movimiento.numero_movimiento,
                movimiento.get_tipo_display(),
                movimiento.fecha.strftime('%d/%m/%Y'),
                str(movimiento.almacen_origen) if movimiento.almacen_origen else '-',
                str(movimiento.almacen_destino) if movimiento.almacen_destino else '-',
                str(movimiento.proveedor) if movimiento.proveedor else '-',
                str(movimiento.recepcionista) if movimiento.recepcionista else '-',
                movimiento.detalles.count()
            ]
        else:
            row_data = [
                movimiento.numero_movimiento,
                movimiento.get_tipo_display(),
                movimiento.fecha.strftime('%d/%m/%Y'),
                str(movimiento.cliente) if movimiento.cliente else '-',
                str(movimiento.almacen_origen) if movimiento.almacen_origen else '-',
                str(movimiento.almacen_destino) if movimiento.almacen_destino else '-',
                str(movimiento.proveedor) if movimiento.proveedor else '-',
                str(movimiento.recepcionista) if movimiento.recepcionista else '-',
                movimiento.detalles.count()
            ]
        
        for col, value in enumerate(row_data, start=1):
            cell = ws1.cell(row=row_idx, column=col, value=value)
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Ajustar columnas hoja 1
    for col in ws1.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws1.column_dimensions[column].width = adjusted_width
    
    # Hoja 2: Detalle de productos
    ws2 = wb.create_sheet(title="Detalle Productos")
    
    detail_headers = ['N° Movimiento', 'Fecha', 'Tipo', 'Código', 'Producto', 
                      'Cant. Buena', 'Cant. Dañada', 'Total', 'Unidad']
    
    for col, header in enumerate(detail_headers, start=1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    detail_row = 2
    for movimiento in movimientos:
        for detalle in movimiento.detalles.all():
            total = (detalle.cantidad or 0) + (detalle.cantidad_danada or 0)
            unidad = detalle.producto.unidad_medida.abreviatura if detalle.producto.unidad_medida else 'UND'
            
            row_data = [
                movimiento.numero_movimiento,
                movimiento.fecha.strftime('%d/%m/%Y'),
                movimiento.get_tipo_display(),
                detalle.producto.codigo,
                detalle.producto.nombre,
                detalle.cantidad or 0,
                detalle.cantidad_danada or 0,
                total,
                unidad
            ]
            
            for col, value in enumerate(row_data, start=1):
                cell = ws2.cell(row=detail_row, column=col, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            detail_row += 1
    
    # Ajustar columnas hoja 2
    for col in ws2.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws2.column_dimensions[column].width = adjusted_width
    
    # Respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'movimientos_{tipo_reporte}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    wb.save(response)
    return response


def exportar_movimientos_csv(request):
    """Exporta los movimientos filtrados a CSV"""
    
# Obtener filtros
    tipo_reporte = request.GET.get('tipo_reporte', 'almacen')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    almacen_id = request.GET.get('almacen')
    cliente_id = request.GET.get('cliente')
    proveedor_id = request.GET.get('proveedor')
    recepcionista_id = request.GET.get('recepcionista')
    producto_id = request.GET.get('producto')
    numero_movimiento = request.GET.get('numero_movimiento', '').strip() # ⭐ CORRECCIÓN: Agregar filtro de número
    
    # Convertir fechas
    fecha_inicio_obj = None
    fecha_fin_obj = None
    
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Construir queryset
    if tipo_reporte == 'almacen':
        movimientos = MovimientoAlmacen.objects.all()
        
        if fecha_inicio_obj:
            movimientos = movimientos.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos = movimientos.filter(fecha__lte=fecha_fin_obj)
        if tipo_movimiento:
            movimientos = movimientos.filter(tipo=tipo_movimiento)
        if almacen_id:
            movimientos = movimientos.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if proveedor_id:
            movimientos = movimientos.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos = movimientos.filter(recepcionista_id=recepcionista_id)
        if producto_id:
            movimientos = movimientos.filter(detalles__producto_id=producto_id).distinct()
        
# ⭐ CORRECCIÓN: Aplicar filtro de número de movimiento
        if numero_movimiento:
            movimientos = movimientos.filter(numero_movimiento__icontains=numero_movimiento)

        movimientos = movimientos.select_related(
            'almacen_origen', 'almacen_destino', 'proveedor', 'recepcionista'
        ).prefetch_related('detalles__producto__unidad_medida').order_by('-fecha')
        
    else:  # cliente
        movimientos = MovimientoCliente.objects.all()
        
        if fecha_inicio_obj:
            movimientos = movimientos.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos = movimientos.filter(fecha__lte=fecha_fin_obj)
        if tipo_movimiento:
            movimientos = movimientos.filter(tipo=tipo_movimiento)
        if cliente_id:
            movimientos = movimientos.filter(cliente_id=cliente_id)
        if almacen_id:
            movimientos = movimientos.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if proveedor_id:
            movimientos = movimientos.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos = movimientos.filter(recepcionista_id=recepcionista_id)
        if producto_id:
            movimientos = movimientos.filter(detalles__producto_id=producto_id).distinct()
        
 # ⭐ CORRECCIÓN: Aplicar filtro de número de movimiento
        if numero_movimiento:
            movimientos = movimientos.filter(numero_movimiento__icontains=numero_movimiento)

        movimientos = movimientos.select_related(
            'cliente', 'almacen_origen', 'almacen_destino', 'proveedor', 'recepcionista'
        ).prefetch_related('detalles__producto__unidad_medida').order_by('-fecha')
    
    # Crear respuesta CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f'movimientos_{tipo_reporte}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    # BOM para Excel
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    
    # Encabezados
    if tipo_reporte == 'almacen':
        writer.writerow(['N° Movimiento', 'Tipo', 'Fecha', 'Almacén Origen', 'Almacén Destino',
                        'Proveedor', 'Recepcionista', 'Código', 'Producto',
                        'Cant. Buena', 'Cant. Dañada', 'Total', 'Unidad'])
    else:
        writer.writerow(['N° Movimiento', 'Tipo', 'Fecha', 'Cliente', 'Almacén Origen',
                        'Almacén Destino', 'Proveedor', 'Recepcionista', 'Código',
                        'Producto', 'Cant. Buena', 'Cant. Dañada', 'Total', 'Unidad'])
    
    # Datos
    for movimiento in movimientos:
        for detalle in movimiento.detalles.all():
            total = (detalle.cantidad or 0) + (detalle.cantidad_danada or 0)
            unidad = detalle.producto.unidad_medida.abreviatura if detalle.producto.unidad_medida else 'UND'
            
            if tipo_reporte == 'almacen':
                writer.writerow([
                    movimiento.numero_movimiento,
                    movimiento.get_tipo_display(),
                    movimiento.fecha.strftime('%d/%m/%Y'),
                    str(movimiento.almacen_origen) if movimiento.almacen_origen else '-',
                    str(movimiento.almacen_destino) if movimiento.almacen_destino else '-',
                    str(movimiento.proveedor) if movimiento.proveedor else '-',
                    str(movimiento.recepcionista) if movimiento.recepcionista else '-',
                    detalle.producto.codigo,
                    detalle.producto.nombre,
                    detalle.cantidad or 0,
                    detalle.cantidad_danada or 0,
                    total,
                    unidad
                ])
            else:
                writer.writerow([
                    movimiento.numero_movimiento,
                    movimiento.get_tipo_display(),
                    movimiento.fecha.strftime('%d/%m/%Y'),
                    str(movimiento.cliente) if movimiento.cliente else '-',
                    str(movimiento.almacen_origen) if movimiento.almacen_origen else '-',
                    str(movimiento.almacen_destino) if movimiento.almacen_destino else '-',
                    str(movimiento.proveedor) if movimiento.proveedor else '-',
                    str(movimiento.recepcionista) if movimiento.recepcionista else '-',
                    detalle.producto.codigo,
                    detalle.producto.nombre,
                    detalle.cantidad or 0,
                    detalle.cantidad_danada or 0,
                    total,
                    unidad
                ])
    
    return response

# ========================================
# NUEVA FUNCIÓN - AGREGAR AL FINAL
# ========================================
@staff_member_required
def obtener_detalle_stock(request):
    """
    Vista para obtener el detalle completo de stock de un producto en un almacén específico
    """
    producto_id = request.GET.get('producto_id')
    almacen_id = request.GET.get('almacen_id')
    
    if not producto_id or not almacen_id:
        return JsonResponse({
            'success': False,
            'error': 'Faltan parámetros requeridos'
        })
    
    try:
        producto = Producto.objects.get(id=producto_id)
        almacen = Almacen.objects.get(id=almacen_id)
        
        # Calcular totales de entradas (cuando este almacén es destino)
        entradas = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(
            buenas=Sum('cantidad'),
            danadas=Sum('cantidad_danada')
        )
        
        total_entradas = (entradas['buenas'] or Decimal('0')) + (entradas['danadas'] or Decimal('0'))
        
        # Calcular totales de salidas (cuando este almacén es origen)
        salidas = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(
            buenas=Sum('cantidad'),
            danadas=Sum('cantidad_danada')
        )
        
        total_salidas = (salidas['buenas'] or Decimal('0')) + (salidas['danadas'] or Decimal('0'))
        
        # Calcular traslados recibidos (donde este almacén es el destino)
        traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(
            buenas=Sum('cantidad'),
            danadas=Sum('cantidad_danada')
        )
        
        total_traslados_recibidos = (traslados_recibidos['buenas'] or Decimal('0')) + (traslados_recibidos['danadas'] or Decimal('0'))
        
        # Calcular traslados enviados (donde este almacén es el origen)
        traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(
            buenas=Sum('cantidad'),
            danadas=Sum('cantidad_danada')
        )
        
        total_traslados_enviados = (traslados_enviados['buenas'] or Decimal('0')) + (traslados_enviados['danadas'] or Decimal('0'))
        
        # Calcular stock bueno actual
        stock_bueno = Decimal('0')
        
        # Sumar entradas buenas
        stock_bueno += DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
        
        # Sumar traslados recibidos buenos
        stock_bueno += DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
        
        # Restar salidas buenas
        stock_bueno -= DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
        
        # Restar traslados enviados buenos
        stock_bueno -= DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
        
        # Calcular stock dañado actual
        stock_danado = Decimal('0')
        
        # Sumar entradas dañadas
        stock_danado += DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
        
        # Sumar traslados recibidos dañados
        stock_danado += DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
        
        # Restar salidas dañadas
        stock_danado -= DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
        
        # Restar traslados enviados dañados
        stock_danado -= DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
        
        # Obtener últimos 10 movimientos
        movimientos = MovimientoAlmacen.objects.filter(
            Q(almacen_origen=almacen) | Q(almacen_destino=almacen),
            detalles__producto=producto
        ).select_related(
            'proveedor',
            'recepcionista',
            'almacen_destino',
            'almacen_origen'
        ).prefetch_related('detalles').distinct().order_by('-fecha', '-id')
        
        movimientos_list = []
        for mov in movimientos:
            # Obtener el detalle específico de este producto
            detalle = mov.detalles.filter(producto=producto).first()
            if detalle:
                cantidad_buena = detalle.cantidad or 0
                cantidad_danada = detalle.cantidad_danada or 0
                cantidad_total = cantidad_buena + cantidad_danada
                
                # Determinar el estado
                if cantidad_buena > 0 and cantidad_danada > 0:
                    estado = 'MIXTO'
                elif cantidad_buena > 0:
                    estado = 'BUENO'
                elif cantidad_danada > 0:
                    estado = 'DAÑADO'
                else:
                    estado = '-'
                
                movimientos_list.append({
                    'numero_movimiento': mov.numero_movimiento,  # AGREGADO
                    'tipo': mov.get_tipo_display(),
                    'fecha': mov.fecha.strftime('%d/%m/%Y %H:%M'),
                    'cantidad': str(cantidad_total),
                    'cantidad_buena': str(cantidad_buena),  # AGREGADO para más detalle
                    'cantidad_danada': str(cantidad_danada),  # AGREGADO para más detalle
                    'estado': estado,
                    'proveedor': mov.proveedor.nombre if mov.proveedor else None,
                    'recepcionista': str(mov.recepcionista) if mov.recepcionista else None,
                    'almacen_origen': mov.almacen_origen.nombre if mov.almacen_origen else None,  # AGREGADO
                    'almacen_destino': mov.almacen_destino.nombre if mov.almacen_destino else None,
                })
        
        return JsonResponse({
            'success': True,
            'producto': {
                'nombre': producto.nombre,
                'codigo': producto.codigo,
                'categoria': producto.categoria.nombre if producto.categoria else None,
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'almacen': {
                'nombre': almacen.nombre
            },
            'resumen': {
                'total_entradas': str(total_entradas),
                'total_salidas': str(total_salidas),
                'traslados_recibidos': str(total_traslados_recibidos),
                'traslados_enviados': str(total_traslados_enviados),
                'stock_bueno': str(stock_bueno),
                'stock_danado': str(stock_danado),
                'stock_total': str(stock_bueno + stock_danado)
            },
            'movimientos': movimientos_list
        })
        
    except Producto.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Producto no encontrado'
        })
    except Almacen.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Almacén no encontrado'
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}',
            'traceback': traceback.format_exc()
        })

# ============================================================
# CORRECCIÓN 3: views.py - obtener_detalle_almacen (línea ~550)
# ============================================================
@staff_member_required
def obtener_detalle_almacen(request):
    """
    ✅ CORREGIDO: Muestra TODOS los productos con movimientos, incluso con stock = 0 o negativo
    """
    almacen_id = request.GET.get('almacen_id')
    
    if not almacen_id:
        return JsonResponse({'success': False, 'error': 'Falta el parámetro almacen_id'})
    
    try:
        almacen = Almacen.objects.get(id=almacen_id)
        
        # Obtener todos los productos que tienen movimientos en este almacén
        productos_con_movimientos = set(DetalleMovimientoAlmacen.objects.filter(
            Q(movimiento__almacen_origen=almacen) | Q(movimiento__almacen_destino=almacen)
        ).values_list('producto_id', flat=True))
        
        productos_list = []
        
        for producto_id in productos_con_movimientos:
            try:
                producto = Producto.objects.get(id=producto_id)
                
                # Calcular stock bueno
                stock_bueno = Decimal('0')
                
                stock_bueno += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='ENTRADA',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                stock_bueno += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                stock_bueno -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='SALIDA',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                stock_bueno -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                # Calcular stock dañado
                stock_danado = Decimal('0')
                
                stock_danado += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='ENTRADA',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_danado += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_danado -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='SALIDA',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_danado -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_total = stock_bueno + stock_danado
                
                # ✅ CAMBIO CRÍTICO: Mostrar TODOS los productos con movimientos
                # ANTES: if stock_total > 0:
                # AHORA: Mostrar todos (incluye 0 y negativos)
                
                # Calcular totales de movimientos
                entradas = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='ENTRADA',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(
                    total=Sum('cantidad'),
                    total_danada=Sum('cantidad_danada')
                )
                
                salidas = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='SALIDA',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(
                    total=Sum('cantidad'),
                    total_danada=Sum('cantidad_danada')
                )
                
                traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(
                    total=Sum('cantidad'),
                    total_danada=Sum('cantidad_danada')
                )
                
                traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(
                    total=Sum('cantidad'),
                    total_danada=Sum('cantidad_danada')
                )
                
                total_entradas = (entradas['total'] or Decimal('0')) + (entradas['total_danada'] or Decimal('0'))
                total_salidas = (salidas['total'] or Decimal('0')) + (salidas['total_danada'] or Decimal('0'))
                total_traslados_recibidos = (traslados_recibidos['total'] or Decimal('0')) + (traslados_recibidos['total_danada'] or Decimal('0'))
                total_traslados_enviados = (traslados_enviados['total'] or Decimal('0')) + (traslados_enviados['total_danada'] or Decimal('0'))
                
                productos_list.append({
                    'producto_id': producto.id,
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'categoria': producto.categoria.nombre if producto.categoria else '-',
                    'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND',
                    'stock_bueno': str(stock_bueno),
                    'stock_danado': str(stock_danado),
                    'stock_total': str(stock_total),
                    'total_entradas': str(total_entradas),
                    'total_salidas': str(total_salidas),
                    'total_traslados_recibidos': str(total_traslados_recibidos),
                    'total_traslados_enviados': str(total_traslados_enviados),
                })
                    
            except Producto.DoesNotExist:
                continue
        
        productos_list.sort(key=lambda x: x['codigo'])
        
        return JsonResponse({
            'success': True,
            'almacen': {'id': almacen.id, 'nombre': almacen.nombre},
            'total_productos': len(productos_list),
            'productos': productos_list
        })
        
    except Almacen.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Almacén no encontrado'})
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})

# ============================================================
# CORRECCIÓN 4: views.py - obtener_detalle_producto_almacenes (línea ~700)
# ============================================================
@staff_member_required
def obtener_detalle_producto_almacenes(request):
    producto_id = request.GET.get('producto_id')
    
    if not producto_id:
        return JsonResponse({'success': False, 'error': 'Falta el parámetro producto_id'})
    
    try:
        producto = Producto.objects.get(id=producto_id)
        
        almacenes_con_producto = set(DetalleMovimientoAlmacen.objects.filter(
            Q(movimiento__almacen_origen__isnull=False) | Q(movimiento__almacen_destino__isnull=False),
            producto=producto
        ).values_list('movimiento__almacen_origen_id', 'movimiento__almacen_destino_id'))
        
        almacenes_ids = set()
        for origen_id, destino_id in almacenes_con_producto:
            if origen_id:
                almacenes_ids.add(origen_id)
            if destino_id:
                almacenes_ids.add(destino_id)
        
        almacenes_list = []
        
        for almacen_id in almacenes_ids:
            try:
                almacen = Almacen.objects.get(id=almacen_id)
                
                # Calcular stock bueno
                stock_bueno = Decimal('0')
                
                stock_bueno += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='ENTRADA',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                stock_bueno += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                stock_bueno -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='SALIDA',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                stock_bueno -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                
                # Calcular stock dañado
                stock_danado = Decimal('0')
                
                stock_danado += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='ENTRADA',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_danado += DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_danado -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='SALIDA',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_danado -= DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                
                stock_total = stock_bueno + stock_danado
                
                # Calcular totales
                entradas = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='ENTRADA',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'), total_danada=Sum('cantidad_danada'))
                
                salidas = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='SALIDA',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'), total_danada=Sum('cantidad_danada'))
                
                traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'), total_danada=Sum('cantidad_danada'))
                
                traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'), total_danada=Sum('cantidad_danada'))
                
                total_entradas = (entradas['total'] or Decimal('0')) + (entradas['total_danada'] or Decimal('0'))
                total_salidas = (salidas['total'] or Decimal('0')) + (salidas['total_danada'] or Decimal('0'))
                total_traslados_recibidos = (traslados_recibidos['total'] or Decimal('0')) + (traslados_recibidos['total_danada'] or Decimal('0'))
                total_traslados_enviados = (traslados_enviados['total'] or Decimal('0')) + (traslados_enviados['total_danada'] or Decimal('0'))
                
                almacenes_list.append({
                    'almacen_id': almacen.id,
                    'almacen_nombre': almacen.nombre,
                    'stock_bueno': str(stock_bueno),
                    'stock_danado': str(stock_danado),
                    'stock_total': str(stock_total),
                    'total_entradas': str(total_entradas),
                    'total_salidas': str(total_salidas),
                    'total_traslados_recibidos': str(total_traslados_recibidos),
                    'total_traslados_enviados': str(total_traslados_enviados),
                })
                    
            except Almacen.DoesNotExist:
                continue
        
        almacenes_list.sort(key=lambda x: x['almacen_nombre'])
        
        # ✅ CAMBIO CRÍTICO: NO filtrar, mostrar TODOS los almacenes con movimientos
        # ANTES: almacenes_list = [a for a in almacenes_list if float(a['stock_total']) > 0]
        # AHORA: Mostrar todos, incluidos los negativos
        
        total_stock_bueno = sum(float(a['stock_bueno']) for a in almacenes_list)
        total_stock_danado = sum(float(a['stock_danado']) for a in almacenes_list)
        total_stock_general = sum(float(a['stock_total']) for a in almacenes_list)
        
        return JsonResponse({
            'success': True,
            'producto': {
                'id': producto.id,
                'codigo': producto.codigo,
                'nombre': producto.nombre,
                'categoria': producto.categoria.nombre if producto.categoria else '-',
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'total_almacenes': len(almacenes_list),
            'almacenes': almacenes_list,
            'totales': {
                'stock_bueno': str(total_stock_bueno),
                'stock_danado': str(total_stock_danado),
                'stock_total': str(total_stock_general)
            }
        })
        
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})

# ==========================================
# NUEVA FUNCIÓN: API para números de movimiento
# ==========================================
@staff_member_required
def obtener_numeros_movimiento_json(request):
    """
    Retorna una lista de números de movimiento únicos basada en filtros.
    """
    tipo_reporte = request.GET.get('tipo_reporte', 'almacen')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    almacen_id = request.GET.get('almacen')
    cliente_id = request.GET.get('cliente')
    proveedor_id = request.GET.get('proveedor')
    recepcionista_id = request.GET.get('recepcionista')

    # Convertir fechas
    fecha_inicio_obj = None
    fecha_fin_obj = None
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if tipo_reporte == 'almacen':
        movimientos_query = MovimientoAlmacen.objects.all()
        
        # Aplicar filtros existentes
        if fecha_inicio_obj:
            movimientos_query = movimientos_query.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos_query = movimientos_query.filter(fecha__lte=fecha_fin_obj)
        if almacen_id:
            movimientos_query = movimientos_query.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if tipo_movimiento:
            movimientos_query = movimientos_query.filter(tipo=tipo_movimiento)
        if proveedor_id:
            movimientos_query = movimientos_query.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos_query = movimientos_query.filter(recepcionista_id=recepcionista_id)
            
    else:
        movimientos_query = MovimientoCliente.objects.all()
        
        # Aplicar filtros existentes
        if fecha_inicio_obj:
            movimientos_query = movimientos_query.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos_query = movimientos_query.filter(fecha__lte=fecha_fin_obj)
        if cliente_id:
            movimientos_query = movimientos_query.filter(cliente_id=cliente_id)
        if tipo_movimiento:
            movimientos_query = movimientos_query.filter(tipo=tipo_movimiento)
        if proveedor_id:
            movimientos_query = movimientos_query.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos_query = movimientos_query.filter(recepcionista_id=recepcionista_id)
            
    # Obtener los números de movimiento, limitar a 200 y ordenar
    numeros = movimientos_query.values_list('numero_movimiento', flat=True).distinct().order_by('-numero_movimiento')[:200]
    
    return JsonResponse({
        'numeros': list(numeros)
    })

# ... (función exportar_movimientos_excel ya está implementada) ...

@staff_member_required
def exportar_movimientos_csv(request):
    """Exporta los movimientos filtrados a CSV"""
    
    # Obtener filtros (similar a exportar_movimientos_excel)
    tipo_reporte = request.GET.get('tipo_reporte', 'almacen')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    almacen_id = request.GET.get('almacen')
    cliente_id = request.GET.get('cliente')
    proveedor_id = request.GET.get('proveedor')
    recepcionista_id = request.GET.get('recepcionista')
    producto_id = request.GET.get('producto')
    numero_movimiento = request.GET.get('numero_movimiento', '').strip()

    # Convertir fechas (similar a exportar_movimientos_excel)
    fecha_inicio_obj = None
    fecha_fin_obj = None
    
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Construir queryset según tipo de reporte (similar a exportar_movimientos_excel)
    if tipo_reporte == 'almacen':
        movimientos = MovimientoAlmacen.objects.all()
        
        if fecha_inicio_obj:
            movimientos = movimientos.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos = movimientos.filter(fecha__lte=fecha_fin_obj)
        if tipo_movimiento:
            movimientos = movimientos.filter(tipo=tipo_movimiento)
        if almacen_id:
            movimientos = movimientos.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if proveedor_id:
            movimientos = movimientos.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos = movimientos.filter(recepcionista_id=recepcionista_id)
        if producto_id:
            movimientos = movimientos.filter(detalles__producto_id=producto_id).distinct()
        if numero_movimiento:
            movimientos = movimientos.filter(numero_movimiento__icontains=numero_movimiento)
            
        movimientos = movimientos.select_related(
            'almacen_origen', 'almacen_destino', 'proveedor', 'recepcionista'
        ).prefetch_related('detalles__producto__unidad_medida').order_by('-fecha')
        
    else:  # cliente
        movimientos = MovimientoCliente.objects.all()
        
        if fecha_inicio_obj:
            movimientos = movimientos.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos = movimientos.filter(fecha__lte=fecha_fin_obj)
        if tipo_movimiento:
            movimientos = movimientos.filter(tipo=tipo_movimiento)
        if cliente_id:
            movimientos = movimientos.filter(cliente_id=cliente_id)
        if almacen_id:
            movimientos = movimientos.filter(
                Q(almacen_origen_id=almacen_id) | Q(almacen_destino_id=almacen_id)
            )
        if proveedor_id:
            movimientos = movimientos.filter(proveedor_id=proveedor_id)
        if recepcionista_id:
            movimientos = movimientos.filter(recepcionista_id=recepcionista_id)
        if producto_id:
            movimientos = movimientos.filter(detalles__producto_id=producto_id).distinct()
        if numero_movimiento:
            movimientos = movimientos.filter(numero_movimiento__icontains=numero_movimiento)
        
        movimientos = movimientos.select_related(
            'cliente', 'almacen_origen', 'almacen_destino', 'proveedor', 'recepcionista'
        ).prefetch_related('detalles__producto__unidad_medida').order_by('-fecha')

    # Respuesta HTTP para CSV
    response = HttpResponse(content_type='text/csv')
    filename = f'movimientos_{tipo_reporte}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Encabezados
    if tipo_reporte == 'almacen':
        headers = ['N° Movimiento', 'Tipo', 'Fecha', 'Almacén Origen', 'Almacén Destino', 
                   'Proveedor', 'Recepcionista', 'Código Producto', 'Nombre Producto', 
                   'Cant. Buena', 'Cant. Dañada', 'Total', 'Unidad']
    else:
        headers = ['N° Movimiento', 'Tipo', 'Fecha', 'Cliente', 'Almacén Origen', 
                   'Almacén Destino', 'Proveedor', 'Recepcionista', 'Código Producto', 
                   'Nombre Producto', 'Cant. Buena', 'Cant. Dañada', 'Total', 'Unidad']
        
    writer.writerow(headers)
    
    # Datos
    for movimiento in movimientos:
        for detalle in movimiento.detalles.all():
            total = (detalle.cantidad or Decimal('0')) + (detalle.cantidad_danada or Decimal('0'))
            unidad = detalle.producto.unidad_medida.abreviatura if detalle.producto.unidad_medida else 'UND'
            
            common_data = [
                movimiento.numero_movimiento,
                movimiento.get_tipo_display(),
                movimiento.fecha.strftime('%d/%m/%Y'),
                str(movimiento.almacen_origen) if movimiento.almacen_origen else '-',
                str(movimiento.almacen_destino) if movimiento.almacen_destino else '-',
                str(movimiento.proveedor) if movimiento.proveedor else '-',
                str(movimiento.recepcionista) if movimiento.recepcionista else '-',
                detalle.producto.codigo,
                detalle.producto.nombre,
                detalle.cantidad or 0,
                detalle.cantidad_danada or 0,
                total,
                unidad
            ]
            
            if tipo_reporte == 'almacen':
                row_data = common_data
            else:
                cliente_nombre = str(movimiento.cliente) if movimiento.cliente else '-'
                row_data = [
                    movimiento.numero_movimiento,
                    movimiento.get_tipo_display(),
                    movimiento.fecha.strftime('%d/%m/%Y'),
                    cliente_nombre,
                    str(movimiento.almacen_origen) if movimiento.almacen_origen else '-',
                    str(movimiento.almacen_destino) if movimiento.almacen_destino else '-',
                    str(movimiento.proveedor) if movimiento.proveedor else '-',
                    str(movimiento.recepcionista) if movimiento.recepcionista else '-',
                    detalle.producto.codigo,
                    detalle.producto.nombre,
                    detalle.cantidad or 0,
                    detalle.cantidad_danada or 0,
                    total,
                    unidad
                ]
                
            writer.writerow(row_data)
            
    return response

# ==========================================
# NUEVAS FUNCIONES DE EXPORTACIÓN DE STOCK
# ==========================================

@staff_member_required
def exportar_stock_excel(request):
    """Exporta el reporte de stock filtrado a Excel."""
    
    vista = request.GET.get('vista', 'detallado')
    almacen_id = request.GET.get('almacen', '')
    categoria_id = request.GET.get('categoria', '')
    producto_id = request.GET.get('producto', '')
    solo_con_stock = request.GET.get('solo_con_stock', '') == 'on'
    
    stocks = []
    
    # Obtener almacenes
    almacenes = Almacen.objects.filter(activo=True)
    if almacen_id:
        almacenes = almacenes.filter(id=almacen_id)
    
    # Obtener productos
    productos = Producto.objects.filter(activo=True)
    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)
    if producto_id:
        productos = productos.filter(id=producto_id)
    
    if vista == 'detallado':
        # Vista detallada: calcular stock para cada almacén y producto
        for almacen in almacenes:
            for producto in productos:
                # Calcular ENTRADAS (ENTRADA + TRASLADO donde este almacén es destino)
                entradas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen)
                ).aggregate(
                    buenas=Sum('cantidad'),
                    danadas=Sum('cantidad_danada')
                )
                
                # Calcular SALIDAS (SALIDA + TRASLADO donde este almacén es origen)
                salidas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen)
                ).aggregate(
                    buenas=Sum('cantidad'),
                    danadas=Sum('cantidad_danada')
                )
                
                entradas_buenas = Decimal(str(entradas['buenas'] or 0))
                entradas_danadas = Decimal(str(entradas['danadas'] or 0))
                salidas_buenas = Decimal(str(salidas['buenas'] or 0))
                salidas_danadas = Decimal(str(salidas['danadas'] or 0))
                
                stock_bueno = entradas_buenas - salidas_buenas
                stock_danado = entradas_danadas - salidas_danadas
                stock_total = stock_bueno + stock_danado
                
                entradas_total = entradas_buenas + entradas_danadas
                salidas_total = salidas_buenas + salidas_danadas
                
                # Calcular traslados netos
                traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(
                    total=Sum('cantidad'),
                    danada=Sum('cantidad_danada')
                )
                
                traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(
                    total=Sum('cantidad'),
                    danada=Sum('cantidad_danada')
                )
                
                traslados_netos = (
                    Decimal(str(traslados_recibidos['total'] or 0)) + 
                    Decimal(str(traslados_recibidos['danada'] or 0)) -
                    Decimal(str(traslados_enviados['total'] or 0)) -
                    Decimal(str(traslados_enviados['danada'] or 0))
                )
                
                # Aplicar filtro
                if solo_con_stock and stock_total == 0:
                    continue
                
                stocks.append({
                    'almacen': almacen,
                    'producto': producto,
                    'stock_bueno': float(stock_bueno),
                    'stock_danado': float(stock_danado),
                    'stock_total': float(stock_total),
                    'entradas_total': float(entradas_total),
                    'salidas_total': float(salidas_total),
                    'traslados_netos': float(traslados_netos)
                })
    
    elif vista == 'por_almacen':
        for almacen in almacenes:
            # Obtener todos los productos que tienen movimientos en este almacén
            productos_ids = set(
                list(DetalleMovimientoAlmacen.objects.filter(
                    Q(movimiento__almacen_origen=almacen) | Q(movimiento__almacen_destino=almacen)
                ).values_list('producto_id', flat=True).distinct())
            )
            
            total_productos = 0
            stock_buena_total = Decimal('0')
            stock_danada_total = Decimal('0')
            
            for producto_id_item in productos_ids:
                try:
                    producto = Producto.objects.get(id=producto_id_item)
                    
                    # Calcular stock
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        producto=producto
                    ).filter(
                        Q(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen) |
                        Q(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen)
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        producto=producto
                    ).filter(
                        Q(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen) |
                        Q(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen)
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    stock_bueno = Decimal(str(entradas['buenas'] or 0)) - Decimal(str(salidas['buenas'] or 0))
                    stock_danado = Decimal(str(entradas['danadas'] or 0)) - Decimal(str(salidas['danadas'] or 0))
                    stock_total_prod = stock_bueno + stock_danado
                    
                    if stock_total_prod != 0:
                        total_productos += 1
                        stock_buena_total += stock_bueno
                        stock_danada_total += stock_danado
                        
                except Producto.DoesNotExist:
                    continue
            
            stock_total = stock_buena_total + stock_danada_total
            
            if solo_con_stock and stock_total == 0:
                continue
            
            if total_productos > 0 or stock_total != 0:
                stocks.append({
                    'almacen': almacen,
                    'total_productos': total_productos,
                    'stock_buena_total': float(stock_buena_total),
                    'stock_danada_total': float(stock_danada_total),
                    'stock_total': float(stock_total)
                })
    
    else:  # por_producto
        for producto in productos:
            stock_buena_total = Decimal('0')
            stock_danada_total = Decimal('0')
            total_almacenes = 0
            
            for almacen in Almacen.objects.filter(activo=True):
                entradas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen)
                ).aggregate(
                    buenas=Sum('cantidad'),
                    danadas=Sum('cantidad_danada')
                )
                
                salidas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen)
                ).aggregate(
                    buenas=Sum('cantidad'),
                    danadas=Sum('cantidad_danada')
                )
                
                stock_bueno = Decimal(str(entradas['buenas'] or 0)) - Decimal(str(salidas['buenas'] or 0))
                stock_danado = Decimal(str(entradas['danadas'] or 0)) - Decimal(str(salidas['danadas'] or 0))
                stock_total_alm = stock_bueno + stock_danado
                
                if stock_total_alm != 0:
                    stock_buena_total += stock_bueno
                    stock_danada_total += stock_danado
                    total_almacenes += 1
            
            stock_total_producto = stock_buena_total + stock_danada_total
            
            if solo_con_stock and stock_total_producto == 0:
                continue
            
            if total_almacenes > 0 or stock_total_producto != 0:
                stocks.append({
                    'producto': producto,
                    'total_almacenes': total_almacenes,
                    'stock_buena_total': float(stock_buena_total),
                    'stock_danada_total': float(stock_danada_total),
                    'stock_total': float(stock_total_producto)
                })
    
    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Stock"
    
    # Estilos
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados según vista
    if vista == 'detallado':
        headers = ['Almacén', 'Código', 'Producto', 'Categoría', 'Unidad', 
                   'Entradas', 'Salidas', 'Traslados', 'Stock Bueno', 'Stock Dañado', 'Stock Total']
    elif vista == 'por_almacen':
        headers = ['Almacén', 'Total Productos', 'Stock Bueno', 'Stock Dañado', 'Stock Total']
    else:  # por_producto
        headers = ['Código', 'Producto', 'Categoría', 'Unidad', 'Almacenes', 
                   'Stock Bueno', 'Stock Dañado', 'Stock Total']
    
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for row_idx, stock in enumerate(stocks, start=2):
        if vista == 'detallado':
            row_data = [
                stock['almacen'].nombre,
                stock['producto'].codigo,
                stock['producto'].nombre,
                stock['producto'].categoria.nombre if stock['producto'].categoria else '-',
                stock['producto'].unidad_medida.abreviatura if stock['producto'].unidad_medida else 'UND',
                stock['entradas_total'],
                stock['salidas_total'],
                stock['traslados_netos'],
                stock['stock_bueno'],
                stock['stock_danado'],
                stock['stock_total']
            ]
        elif vista == 'por_almacen':
            row_data = [
                stock['almacen'].nombre,
                stock['total_productos'],
                stock['stock_buena_total'],
                stock['stock_danada_total'],
                stock['stock_total']
            ]
        else:  # por_producto
            row_data = [
                stock['producto'].codigo,
                stock['producto'].nombre,
                stock['producto'].categoria.nombre if stock['producto'].categoria else '-',
                stock['producto'].unidad_medida.abreviatura if stock['producto'].unidad_medida else 'UND',
                stock['total_almacenes'],
                stock['stock_buena_total'],
                stock['stock_danada_total'],
                stock['stock_total']
            ]
        
        for col, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Ajustar columnas
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width
    
    # Respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'stock_{vista}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    wb.save(response)
    return response


@staff_member_required
def exportar_stock_csv(request):
    """Exporta el reporte de stock filtrado a CSV."""
    
    vista = request.GET.get('vista', 'detallado')
    almacen_id = request.GET.get('almacen', '')
    categoria_id = request.GET.get('categoria', '')
    producto_id = request.GET.get('producto', '')
    solo_con_stock = request.GET.get('solo_con_stock', '') == 'on'
    
    stocks = []
    
    # Obtener almacenes
    almacenes = Almacen.objects.filter(activo=True)
    if almacen_id:
        almacenes = almacenes.filter(id=almacen_id)
    
    # Obtener productos
    productos = Producto.objects.filter(activo=True)
    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)
    if producto_id:
        productos = productos.filter(id=producto_id)
    
    if vista == 'detallado':
        for almacen in almacenes:
            for producto in productos:
                # Calcular ENTRADAS
                entradas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen)
                ).aggregate(
                    buenas=Sum('cantidad'),
                    danadas=Sum('cantidad_danada')
                )
                
                # Calcular SALIDAS
                salidas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen)
                ).aggregate(
                    buenas=Sum('cantidad'),
                    danadas=Sum('cantidad_danada')
                )
                
                stock_bueno = Decimal(str(entradas['buenas'] or 0)) - Decimal(str(salidas['buenas'] or 0))
                stock_danado = Decimal(str(entradas['danadas'] or 0)) - Decimal(str(salidas['danadas'] or 0))
                stock_total = stock_bueno + stock_danado
                
                if solo_con_stock and stock_total == 0:
                    continue
                
                entradas_total = Decimal(str(entradas['buenas'] or 0)) + Decimal(str(entradas['danadas'] or 0))
                salidas_total = Decimal(str(salidas['buenas'] or 0)) + Decimal(str(salidas['danadas'] or 0))
                
                # Traslados netos
                traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_destino=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'), danada=Sum('cantidad_danada'))
                
                traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
                    movimiento__tipo='TRASLADO',
                    movimiento__almacen_origen=almacen,
                    producto=producto
                ).aggregate(total=Sum('cantidad'), danada=Sum('cantidad_danada'))
                
                traslados_netos = (
                    Decimal(str(traslados_recibidos['total'] or 0)) + 
                    Decimal(str(traslados_recibidos['danada'] or 0)) -
                    Decimal(str(traslados_enviados['total'] or 0)) -
                    Decimal(str(traslados_enviados['danada'] or 0))
                )
                
                stocks.append({
                    'almacen': almacen,
                    'producto': producto,
                    'stock_bueno': float(stock_bueno),
                    'stock_danado': float(stock_danado),
                    'stock_total': float(stock_total),
                    'entradas_total': float(entradas_total),
                    'salidas_total': float(salidas_total),
                    'traslados_netos': float(traslados_netos)
                })
    
    elif vista == 'por_almacen':
        for almacen in almacenes:
            productos_ids = set(
                list(DetalleMovimientoAlmacen.objects.filter(
                    Q(movimiento__almacen_origen=almacen) | Q(movimiento__almacen_destino=almacen)
                ).values_list('producto_id', flat=True).distinct())
            )
            
            total_productos = 0
            stock_buena_total = Decimal('0')
            stock_danada_total = Decimal('0')
            
            for producto_id_item in productos_ids:
                try:
                    producto = Producto.objects.get(id=producto_id_item)
                    
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        producto=producto
                    ).filter(
                        Q(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen) |
                        Q(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen)
                    ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        producto=producto
                    ).filter(
                        Q(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen) |
                        Q(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen)
                    ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
                    
                    stock_bueno = Decimal(str(entradas['buenas'] or 0)) - Decimal(str(salidas['buenas'] or 0))
                    stock_danado = Decimal(str(entradas['danadas'] or 0)) - Decimal(str(salidas['danadas'] or 0))
                    stock_total_prod = stock_bueno + stock_danado
                    
                    if stock_total_prod != 0:
                        total_productos += 1
                        stock_buena_total += stock_bueno
                        stock_danada_total += stock_danado
                        
                except Producto.DoesNotExist:
                    continue
            
            stock_total = stock_buena_total + stock_danada_total
            
            if solo_con_stock and stock_total == 0:
                continue
            
            if total_productos > 0 or stock_total != 0:
                stocks.append({
                    'almacen': almacen,
                    'total_productos': total_productos,
                    'stock_buena_total': float(stock_buena_total),
                    'stock_danada_total': float(stock_danada_total),
                    'stock_total': float(stock_total)
                })
    
    else:  # por_producto
        for producto in productos:
            stock_buena_total = Decimal('0')
            stock_danada_total = Decimal('0')
            total_almacenes = 0
            
            for almacen in Almacen.objects.filter(activo=True):
                entradas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen)
                ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
                
                salidas = DetalleMovimientoAlmacen.objects.filter(
                    producto=producto
                ).filter(
                    Q(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen) |
                    Q(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen)
                ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
                
                stock_bueno = Decimal(str(entradas['buenas'] or 0)) - Decimal(str(salidas['buenas'] or 0))
                stock_danado = Decimal(str(entradas['danadas'] or 0)) - Decimal(str(salidas['danadas'] or 0))
                stock_total_alm = stock_bueno + stock_danado
                
                if stock_total_alm != 0:
                    stock_buena_total += stock_bueno
                    stock_danada_total += stock_danado
                    total_almacenes += 1
            
            stock_total_producto = stock_buena_total + stock_danada_total
            
            if solo_con_stock and stock_total_producto == 0:
                continue
            
            if total_almacenes > 0 or stock_total_producto != 0:
                stocks.append({
                    'producto': producto,
                    'total_almacenes': total_almacenes,
                    'stock_buena_total': float(stock_buena_total),
                    'stock_danada_total': float(stock_danada_total),
                    'stock_total': float(stock_total_producto)
                })
    
    # Respuesta HTTP
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f'stock_{vista}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    # BOM para Excel
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    
    # Encabezados según vista
    if vista == 'detallado':
        headers = ['Almacén', 'Código', 'Producto', 'Categoría', 'Unidad', 
                   'Entradas', 'Salidas', 'Traslados', 'Stock Bueno', 'Stock Dañado', 'Stock Total']
    elif vista == 'por_almacen':
        headers = ['Almacén', 'Total Productos', 'Stock Bueno', 'Stock Dañado', 'Stock Total']
    else:  # por_producto
        headers = ['Código', 'Producto', 'Categoría', 'Unidad', 'Almacenes', 
                   'Stock Bueno', 'Stock Dañado', 'Stock Total']
    
    writer.writerow(headers)
    
    # Datos
    for stock in stocks:
        if vista == 'detallado':
            row_data = [
                stock['almacen'].nombre,
                stock['producto'].codigo,
                stock['producto'].nombre,
                stock['producto'].categoria.nombre if stock['producto'].categoria else '-',
                stock['producto'].unidad_medida.abreviatura if stock['producto'].unidad_medida else 'UND',
                stock['entradas_total'],
                stock['salidas_total'],
                stock['traslados_netos'],
                stock['stock_bueno'],
                stock['stock_danado'],
                stock['stock_total']
            ]
        elif vista == 'por_almacen':
            row_data = [
                stock['almacen'].nombre,
                stock['total_productos'],
                stock['stock_buena_total'],
                stock['stock_danada_total'],
                stock['stock_total']
            ]
        else:  # por_producto
            row_data = [
                stock['producto'].codigo,
                stock['producto'].nombre,
                stock['producto'].categoria.nombre if stock['producto'].categoria else '-',
                stock['producto'].unidad_medida.abreviatura if stock['producto'].unidad_medida else 'UND',
                stock['total_almacenes'],
                stock['stock_buena_total'],
                stock['stock_danada_total'],
                stock['stock_total']
            ]
        
        writer.writerow(row_data)
    
    return response

# ========================================
# NUEVA FUNCIÓN - AGREGAR AL FINAL
# ========================================
@staff_member_required
def obtener_detalle_stock(request):
    """ 
    Vista para obtener el detalle completo de stock de un producto en un almacén específico
    CORREGIDO: Ahora devuelve los totales de entradas, salidas y traslados para evitar NaN
    """
    producto_id = request.GET.get('producto_id')
    almacen_id = request.GET.get('almacen_id')
    
    if not producto_id or not almacen_id:
        return JsonResponse({
            'success': False, 
            'error': 'Faltan parámetros requeridos'
        })
        
    try:
        producto = Producto.objects.get(id=producto_id)
        almacen = Almacen.objects.get(id=almacen_id)

        # 1. Calcular Totales para el Resumen (Para evitar NaN en el frontend)
        # ------------------------------------------------------------------
        
        # Total Entradas
        entradas_agg = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='ENTRADA',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
        total_entradas = (entradas_agg['buenas'] or Decimal('0')) + (entradas_agg['danadas'] or Decimal('0'))

        # Total Salidas
        salidas_agg = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='SALIDA',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
        total_salidas = (salidas_agg['buenas'] or Decimal('0')) + (salidas_agg['danadas'] or Decimal('0'))

        # Traslados Recibidos
        tras_rec_agg = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_destino=almacen,
            producto=producto
        ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
        total_traslados_recibidos = (tras_rec_agg['buenas'] or Decimal('0')) + (tras_rec_agg['danadas'] or Decimal('0'))

        # Traslados Enviados
        tras_env_agg = DetalleMovimientoAlmacen.objects.filter(
            movimiento__tipo='TRASLADO',
            movimiento__almacen_origen=almacen,
            producto=producto
        ).aggregate(buenas=Sum('cantidad'), danadas=Sum('cantidad_danada'))
        total_traslados_enviados = (tras_env_agg['buenas'] or Decimal('0')) + (tras_env_agg['danadas'] or Decimal('0'))

        # 2. Calcular Stock Actual (Balance)
        # ------------------------------------------------------------------
        stock_bueno = (
            (entradas_agg['buenas'] or Decimal('0')) + 
            (tras_rec_agg['buenas'] or Decimal('0')) - 
            (salidas_agg['buenas'] or Decimal('0')) - 
            (tras_env_agg['buenas'] or Decimal('0'))
        )
        
        stock_danado = (
            (entradas_agg['danadas'] or Decimal('0')) + 
            (tras_rec_agg['danadas'] or Decimal('0')) - 
            (salidas_agg['danadas'] or Decimal('0')) - 
            (tras_env_agg['danadas'] or Decimal('0'))
        )
        
        stock_total = stock_bueno + stock_danado
        
        # 3. Obtener movimientos detallados
        # ------------------------------------------------------------------
        movimientos_qs = MovimientoAlmacen.objects.filter(
            Q(almacen_origen=almacen) | Q(almacen_destino=almacen)
        ).filter(
            detalles__producto=producto
        ).select_related(
            'proveedor', 'recepcionista', 'almacen_origen', 'almacen_destino'
        ).prefetch_related(
            'detalles'
        ).order_by('-fecha', '-numero_movimiento')
        
        movimientos_list = []
        for mov in movimientos_qs:
            detalle = mov.detalles.filter(producto=producto).first()
            if not detalle:
                continue

            cantidad_buena = detalle.cantidad or Decimal('0')
            cantidad_danada = detalle.cantidad_danada or Decimal('0')
            cantidad_total = cantidad_buena + cantidad_danada
            
            # Ajuste de signos visuales según tipo
            if mov.tipo == 'SALIDA' and mov.almacen_origen == almacen:
                cantidad_total = -cantidad_total # Salida resta
            elif mov.tipo == 'TRASLADO' and mov.almacen_origen == almacen:
                cantidad_total = -cantidad_total # Traslado enviado resta
            
            estado = '-'
            if cantidad_buena > 0 and cantidad_danada == 0: estado = 'BUENO'
            elif cantidad_buena == 0 and cantidad_danada > 0: estado = 'DAÑADO'
            elif cantidad_buena > 0 and cantidad_danada > 0: estado = 'MIXTO'

            movimientos_list.append({
                'numero_movimiento': mov.numero_movimiento,
                'tipo': mov.get_tipo_display(),
                'fecha': mov.fecha.strftime('%d/%m/%Y %H:%M'),
                'cantidad': str(cantidad_total),
                'cantidad_buena': str(cantidad_buena),
                'cantidad_danada': str(cantidad_danada),
                'estado': estado,
                'proveedor': mov.proveedor.nombre if mov.proveedor else None,
                'recepcionista': str(mov.recepcionista) if mov.recepcionista else None,
                'almacen_origen': mov.almacen_origen.nombre if mov.almacen_origen else None,
                'almacen_destino': mov.almacen_destino.nombre if mov.almacen_destino else None,
            })
            
        return JsonResponse({
            'success': True,
            'producto': {
                'nombre': producto.nombre,
                'codigo': producto.codigo,
                'categoria': producto.categoria.nombre if producto.categoria else None,
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'almacen': {
                'nombre': almacen.nombre
            },
            'resumen': {
                # Aquí enviamos los datos que faltaban y causaban el NaN
                'total_entradas': str(total_entradas),
                'total_salidas': str(total_salidas),
                'traslados_recibidos': str(total_traslados_recibidos),
                'traslados_enviados': str(total_traslados_enviados),
                # Datos de stock
                'stock_bueno': str(stock_bueno),
                'stock_danado': str(stock_danado),
                'stock_total': str(stock_total)
            },
            'movimientos': movimientos_list
        })
        
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    except Almacen.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Almacén no encontrado'})
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}', 'traceback': traceback.format_exc()})

# ==========================================
# ⭐ NUEVA FUNCIÓN - AGREGAR AL FINAL DEL ARCHIVO
# ==========================================

@staff_member_required
def obtener_detalle_estadistica(request):
    """
    Endpoint AJAX para obtener detalles de las estadísticas del dashboard
    ✅ CORREGIDO: Muestra stocks negativos y cero con advertencias
    """
    tipo = request.GET.get('tipo')
    
    try:
        if tipo == 'total_productos':
            total_productos = Producto.objects.filter(activo=True).count()
            
            productos_con_movimientos = DetalleMovimientoAlmacen.objects.values('producto').distinct().count()
            productos_sin_movimientos = total_productos - productos_con_movimientos
            
            # ✅ Calcular productos con stock (incluye negativos)
            productos_ids_con_stock = set()
            productos_ids_con_stock_negativo = set()
            
            for producto in Producto.objects.filter(activo=True):
                almacenes = Almacen.objects.filter(activo=True)
                stock_total_producto = Decimal('0')
                
                for almacen in almacenes:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(
                        total=Sum('cantidad'),
                        total_danada=Sum('cantidad_danada')
                    )
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(
                        total=Sum('cantidad'),
                        total_danada=Sum('cantidad_danada')
                    )
                    
                    stock_almacen = (
                        (entradas['total'] or Decimal('0')) + 
                        (entradas['total_danada'] or Decimal('0')) -
                        (salidas['total'] or Decimal('0')) - 
                        (salidas['total_danada'] or Decimal('0'))
                    )
                    
                    stock_total_producto += stock_almacen
                
                if stock_total_producto > 0:
                    productos_ids_con_stock.add(producto.id)
                elif stock_total_producto < 0:
                    productos_ids_con_stock_negativo.add(producto.id)
            
            productos_con_stock = len(productos_ids_con_stock)
            productos_sin_stock = total_productos - productos_con_stock - len(productos_ids_con_stock_negativo)
            
            # Distribución por categoría
            por_categoria = Producto.objects.filter(activo=True).values(
                categoria_nombre=F('categoria__nombre')
            ).annotate(
                total=Count('id')
            ).order_by('-total')
            
            categorias_list = []
            for cat in por_categoria:
                categorias_list.append({
                    'categoria': cat['categoria_nombre'] if cat['categoria_nombre'] else 'Sin Categoría',
                    'total': cat['total']
                })
            
            return JsonResponse({
                'success': True,
                'total_productos': total_productos,
                'productos_con_stock': productos_con_stock,
                'productos_sin_stock': productos_sin_stock,
                'productos_con_stock_negativo': len(productos_ids_con_stock_negativo),  # ✅ NUEVO
                'por_categoria': categorias_list
            })
        
        elif tipo == 'stock_bueno':
            # ✅ Incluir stocks negativos y cero
            total_stock_bueno = Decimal('0')
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True)
            
            for almacen in almacenes:
                for producto in productos:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    stock_bueno = entradas - salidas
                    total_stock_bueno += stock_bueno
            
            productos_con_stock_bueno = 0
            productos_con_stock_bueno_negativo = 0  # ✅ NUEVO
            
            for producto in productos:
                stock_producto = Decimal('0')
                for almacen in almacenes:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    stock_producto += (entradas - salidas)
                
                if stock_producto > 0:
                    productos_con_stock_bueno += 1
                elif stock_producto < 0:
                    productos_con_stock_bueno_negativo += 1
            
            # ✅ Mostrar TODOS los almacenes
            almacenes_list = []
            for almacen in almacenes:
                stock_bueno_almacen = Decimal('0')
                
                for producto in productos:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    stock_bueno_almacen += (entradas - salidas)
                
                almacenes_list.append({
                    'almacen': almacen.nombre,
                    'almacen_id': almacen.id,
                    'stock_bueno': float(stock_bueno_almacen),
                    'es_negativo': stock_bueno_almacen < 0,
                    'es_cero': stock_bueno_almacen == 0
                })
            
            # Ordenar: negativos primero
            almacenes_list.sort(key=lambda x: (not x['es_negativo'], -abs(x['stock_bueno'])))
            
            return JsonResponse({
                'success': True,
                'total_stock_bueno': float(total_stock_bueno),
                'productos_con_stock_bueno': productos_con_stock_bueno,
                'productos_con_stock_bueno_negativo': productos_con_stock_bueno_negativo,
                'por_almacen': almacenes_list
            })
        
        elif tipo == 'stock_danado':
            # ✅ Similar al stock_bueno
            total_stock_danado = Decimal('0')
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True)
            
            for almacen in almacenes:
                for producto in productos:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    stock_danado = entradas - salidas
                    total_stock_danado += stock_danado
            
            productos_con_stock_danado = 0
            productos_con_stock_danado_negativo = 0
            
            for producto in productos:
                stock_producto = Decimal('0')
                for almacen in almacenes:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    stock_producto += (entradas - salidas)
                
                if stock_producto > 0:
                    productos_con_stock_danado += 1
                elif stock_producto < 0:
                    productos_con_stock_danado_negativo += 1
            
            almacenes_list = []
            for almacen in almacenes:
                stock_danado_almacen = Decimal('0')
                
                for producto in productos:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    stock_danado_almacen += (entradas - salidas)
                
                almacenes_list.append({
                    'almacen': almacen.nombre,
                    'almacen_id': almacen.id,
                    'stock_danado': float(stock_danado_almacen),
                    'es_negativo': stock_danado_almacen < 0,
                    'es_cero': stock_danado_almacen == 0
                })
            
            almacenes_list.sort(key=lambda x: (not x['es_negativo'], -abs(x['stock_danado'])))
            
            # Top productos dañados
            productos_danados = []
            for producto in productos:
                stock_danado_producto = Decimal('0')
                
                for almacen in almacenes:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    stock_danado_producto += (entradas - salidas)
                
                if stock_danado_producto != 0:
                    productos_danados.append({
                        'producto': producto.nombre,
                        'codigo': producto.codigo,
                        'producto_id': producto.id,
                        'stock_danado': float(stock_danado_producto),
                        'es_negativo': stock_danado_producto < 0
                    })
            
            productos_danados.sort(key=lambda x: (not x['es_negativo'], -abs(x['stock_danado'])))
            productos_list = productos_danados[:10]
            
            return JsonResponse({
                'success': True,
                'total_stock_danado': float(total_stock_danado),
                'productos_con_stock_danado': productos_con_stock_danado,
                'productos_con_stock_danado_negativo': productos_con_stock_danado_negativo,
                'por_almacen': almacenes_list,
                'productos_mas_danados': productos_list
            })
        
        elif tipo == 'total_almacenes':
            # Total de almacenes activos
            almacenes = Almacen.objects.filter(activo=True)
            total_almacenes = almacenes.count()
            
            # Detalle de cada almacén con sus estadísticas
            almacenes_list = []
            productos = Producto.objects.filter(activo=True)
            
            for almacen in almacenes:
                total_productos_almacen = 0
                stock_total = Decimal('0')
                stock_bueno = Decimal('0')
                stock_danado = Decimal('0')
                
                for producto in productos:
                    # Stock bueno
                    entradas_buenas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    salidas_buenas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
                    
                    stock_bueno_prod = entradas_buenas - salidas_buenas
                    
                    # Stock dañado
                    entradas_danadas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    salidas_danadas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(total=Sum('cantidad_danada'))['total'] or Decimal('0')
                    
                    stock_danado_prod = entradas_danadas - salidas_danadas
                    
                    stock_total_prod = stock_bueno_prod + stock_danado_prod
                    
                    if stock_total_prod > 0:
                        total_productos_almacen += 1
                        stock_bueno += stock_bueno_prod
                        stock_danado += stock_danado_prod
                        stock_total += stock_total_prod
                
                almacenes_list.append({
                    'id': almacen.id,
                    'nombre': almacen.nombre,
                    'total_productos': total_productos_almacen,
                    'stock_total': float(stock_total),
                    'stock_bueno': float(stock_bueno),
                    'stock_danado': float(stock_danado)
                })
            
            return JsonResponse({
                'success': True,
                'total_almacenes': total_almacenes,
                'almacenes': almacenes_list
            })
        
        elif tipo == 'bajo_minimo':
            # Productos bajo stock mínimo
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True, stock_minimo__isnull=False, stock_minimo__gt=0)
            
            productos_list = []
            
            for producto in productos:
                for almacen in almacenes:
                    # Calcular stock actual
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    stock_actual = (
                        (entradas['buenas'] or Decimal('0')) +
                        (entradas['danadas'] or Decimal('0')) -
                        (salidas['buenas'] or Decimal('0')) -
                        (salidas['danadas'] or Decimal('0'))
                    )
                    
                    # Verificar si está bajo el mínimo
                    if stock_actual < producto.stock_minimo:
                        productos_list.append({
                            'producto': producto.nombre,
                            'codigo': producto.codigo,
                            'producto_id': producto.id,
                            'almacen': almacen.nombre,
                            'almacen_id': almacen.id,
                            'stock_actual': float(stock_actual),
                            'stock_minimo': float(producto.stock_minimo),
                        })
            
            total_bajo_minimo = len(productos_list)
            
            return JsonResponse({
                'success': True,
                'total_bajo_minimo': total_bajo_minimo,
                'productos': productos_list
            })
        
        elif tipo == 'valor_inventario':
            # Total de productos únicos
            total_productos = Producto.objects.filter(activo=True).count()
            
            # Total de items en stock (suma de todo el stock en todos los almacenes)
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True)
            
            total_items = Decimal('0')
            
            for almacen in almacenes:
                for producto in productos:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    stock = (
                        (entradas['buenas'] or Decimal('0')) +
                        (entradas['danadas'] or Decimal('0')) -
                        (salidas['buenas'] or Decimal('0')) -
                        (salidas['danadas'] or Decimal('0'))
                    )
                    
                    if stock > 0:
                        total_items += stock
            
            # Valoración por categoría
            categorias_dict = {}
            
            for producto in productos:
                categoria_nombre = producto.categoria.nombre if producto.categoria else 'Sin Categoría'
                
                if categoria_nombre not in categorias_dict:
                    categorias_dict[categoria_nombre] = Decimal('0')
                
                for almacen in almacenes:
                    entradas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['ENTRADA', 'TRASLADO'],
                        movimiento__almacen_destino=almacen,
                        producto=producto
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    salidas = DetalleMovimientoAlmacen.objects.filter(
                        movimiento__tipo__in=['SALIDA', 'TRASLADO'],
                        movimiento__almacen_origen=almacen,
                        producto=producto
                    ).aggregate(
                        buenas=Sum('cantidad'),
                        danadas=Sum('cantidad_danada')
                    )
                    
                    stock = (
                        (entradas['buenas'] or Decimal('0')) +
                        (entradas['danadas'] or Decimal('0')) -
                        (salidas['buenas'] or Decimal('0')) -
                        (salidas['danadas'] or Decimal('0'))
                    )
                    
                    if stock > 0:
                        categorias_dict[categoria_nombre] += stock
            
            categorias_list = []
            for categoria, total in categorias_dict.items():
                if total > 0:
                    categorias_list.append({
                        'categoria': categoria,
                        'total_items': float(total)
                    })
            
            # Ordenar por total descendente
            categorias_list.sort(key=lambda x: x['total_items'], reverse=True)
            
            return JsonResponse({
                'success': True,
                'total_productos': total_productos,
                'total_items': float(total_items),
                'por_categoria': categorias_list
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Tipo de estadística no válido'
            }, status=400)
    
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@staff_member_required
def obtener_detalle_entrega_cliente(request):
    """
    Vista para obtener el detalle completo de entregas de un producto a un cliente específico
    CORREGIDO: Entrada (+), Salida (-), Traslado (según dirección).
    Se eliminó la resta por defecto en traslados ambiguos.
    """
    cliente_id = request.GET.get('cliente_id')
    producto_id = request.GET.get('producto_id')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    if not cliente_id or not producto_id:
        return JsonResponse({'success': False, 'error': 'Faltan parámetros requeridos'})
    
    try:
        from beneficiarios.models import Cliente, DetalleMovimientoCliente, MovimientoCliente
        from productos.models import Producto
        
        cliente = Cliente.objects.get(id=cliente_id)
        producto = Producto.objects.get(id=producto_id)
        
        # Convertir fechas
        fecha_inicio_obj = None
        fecha_fin_obj = None
        if fecha_inicio:
            try: fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            except ValueError: pass
        if fecha_fin:
            try: fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            except ValueError: pass
        
        # Filtrar movimientos: Buscamos movimientos donde el cliente sea el actor principal, origen o destino
        movimientos_qs = MovimientoCliente.objects.filter(
            Q(cliente=cliente) | Q(cliente_origen=cliente) | Q(cliente_destino=cliente)
        ).select_related(
            'proveedor', 'recepcionista', 'almacen_origen', 'almacen_destino'
        ).prefetch_related('detalles')
        
        if fecha_inicio_obj: movimientos_qs = movimientos_qs.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj: movimientos_qs = movimientos_qs.filter(fecha__lte=fecha_fin_obj)
        
        # Filtrar solo movimientos con este producto
        movimientos_qs = movimientos_qs.filter(detalles__producto=producto).distinct()
        
        total_entregas = movimientos_qs.count()
        
        # Calcular Stock Neto (Balance)
        stock_bueno = Decimal('0')
        stock_danado = Decimal('0')
        
        cantidad_entrada = Decimal('0')
        cantidad_salida = Decimal('0')
        cantidad_traslado = Decimal('0')
        
        movimientos_list = []
        
        # Iterar sobre movimientos ordenados por fecha descendente para obtener un balance acumulativo
        for mov in movimientos_qs.order_by('fecha', 'id'): # Cambié a ascendente para calcular stock correctamente
            detalle = mov.detalles.filter(producto=producto).first()
            if not detalle: continue
            
            cant_b = detalle.cantidad or Decimal('0')
            cant_d = detalle.cantidad_danada or Decimal('0')
            cant_total = cant_b + cant_d
            
            # --- LÓGICA DE CÁLCULO DE STOCK ---
            signo = 0
            
            if mov.tipo == 'ENTRADA':
                # Entrada SUMA
                stock_bueno += cant_b
                stock_danado += cant_d
                cantidad_entrada += cant_total
                signo = 1
                
            elif mov.tipo == 'SALIDA':
                # Salida RESTA
                stock_bueno -= cant_b
                stock_danado -= cant_d
                cantidad_salida += cant_total
                signo = -1
                
            elif mov.tipo == 'TRASLADO':
                cantidad_traslado += cant_total
                
                # Verificar dirección para este cliente
                cliente_id_int = int(cliente_id)
                es_origen = mov.cliente_origen_id == cliente_id_int
                es_destino = mov.cliente_destino_id == cliente_id_int
                
                if es_origen:
                    # Sale del cliente -> Resta
                    stock_bueno -= cant_b
                    stock_danado -= cant_d
                    signo = -1
                elif es_destino:
                    # Entra al cliente -> Suma
                    stock_bueno += cant_b
                    stock_danado += cant_d
                    signo = 1
                # ELSE: Si no es ni origen ni destino (aunque esté en el filtro Q), es neutro para el stock de este cliente.
                # No se aplica ninguna operación de suma/resta al stock.
            
            # Preparar datos para la lista (se muestran con stock acumulado)
            
            estado = '-'
            if cant_b > 0 and cant_d > 0: estado = 'MIXTO'
            elif cant_b > 0: estado = 'BUENO'
            elif cant_d > 0: estado = 'DAÑADO'
            
            # Formatear la cantidad visualmente con el signo correcto
            cant_visual = cant_total * signo
            
            # ✅ Preparar información de clientes para traslados
            cliente_origen_nombre = None
            cliente_destino_nombre = None
            
            if mov.tipo == 'TRASLADO':
                cliente_origen_nombre = mov.cliente_origen.nombre if mov.cliente_origen else None
                cliente_destino_nombre = mov.cliente_destino.nombre if mov.cliente_destino else None
            
            movimientos_list.append({
                'numero_movimiento': mov.numero_movimiento,
                'tipo': mov.get_tipo_display(),
                'fecha_ordenamiento': mov.fecha,
                'fecha': mov.fecha.strftime('%d/%m/%Y %H:%M'),
                'cantidad': str(cant_visual), # Cantidad con signo visual
                'cantidad_buena': str(cant_b),
                'cantidad_danada': str(cant_d),
                'stock_bueno_actual': str(stock_bueno), # Stock acumulado al momento del movimiento
                'stock_danado_actual': str(stock_danado), # Stock acumulado al momento del movimiento
                'stock_total_actual': str(stock_bueno + stock_danado), # Stock total acumulado
                'estado': estado,
                'proveedor': mov.proveedor.nombre if mov.proveedor else None,
                'recepcionista': str(mov.recepcionista) if mov.recepcionista else None,
                'almacen': mov.almacen_origen.nombre if mov.almacen_origen else (mov.almacen_destino.nombre if mov.almacen_destino else None),
                'cliente_origen': cliente_origen_nombre,  # ✅ NUEVO
                'cliente_destino': cliente_destino_nombre,  # ✅ NUEVO
                'observaciones': mov.observaciones if hasattr(mov, 'observaciones') else None,
            })
        
        stock_total = stock_bueno + stock_danado
        
        # Invertir la lista para que los movimientos más recientes se muestren primero en el modal
        movimientos_list.reverse()
        
        return JsonResponse({
            'success': True,
            'cliente': {
                'nombre': cliente.nombre,
                'codigo': cliente.codigo,
                'direccion': cliente.direccion or '-',
                'telefono': cliente.telefono or '-'
            },
            'producto': {
                'nombre': producto.nombre,
                'codigo': producto.codigo,
                'categoria': producto.categoria.nombre if producto.categoria else '-',
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'resumen': {
                'total_entregas': total_entregas,
                'cantidad_total': str(stock_total), # Stock Neto final
                'cantidad_buena': str(stock_bueno), # Stock Bueno Neto final
                'cantidad_danada': str(stock_danado), # Stock Dañado Neto final
                'cantidad_entrada': str(cantidad_entrada), # Volumen de entradas
                'cantidad_salida': str(cantidad_salida), # Volumen de salidas
                'cantidad_traslado': str(cantidad_traslado), # Volumen de traslados
                'stock_bueno': str(stock_bueno),
                'stock_danado': str(stock_danado),
                'stock_total': str(stock_total)
            },
            'movimientos': movimientos_list
        })
        
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cliente no encontrado'})
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}', 'traceback': traceback.format_exc()})

@staff_member_required
def obtener_productos_cliente(request):
    """
    Obtiene el resumen de productos (saldo) de un cliente específico 
    basado en sus movimientos de ENTRADA, SALIDA y TRASLADO.
    """
    cliente_id = request.GET.get('cliente_id')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if not cliente_id:
        return JsonResponse({'error': 'Falta el parámetro cliente_id'}, status=400)

    try:
        # 1. Obtener el cliente y preparar el ID
        cliente = Cliente.objects.get(id=cliente_id)
        cli_id_param = int(cliente_id)

        # 2. Queryset principal: Filtra todos los detalles de movimientos 
        #    donde el cliente esté involucrado (como cliente principal, origen o destino).
        detalles_qs = DetalleMovimientoCliente.objects.filter(
            # 1. Movimientos ENTRADA y SALIDA (usando el campo 'cliente' principal)
            Q(movimiento__cliente_id=cli_id_param) | 
            
            # 2. Movimientos TRASLADO donde el cliente es ORIGEN (Salida/Resta)
            Q(movimiento__cliente_origen_id=cli_id_param, movimiento__tipo='TRASLADO') |
            
            # 3. Movimientos TRASLADO donde el cliente es DESTINO (Entrada/Suma)
            Q(movimiento__cliente_destino_id=cli_id_param, movimiento__tipo='TRASLADO')
            
        ).select_related(
            'producto__categoria', 
            'producto__unidad_medida', 
            'movimiento'
        ).order_by('producto__codigo', 'movimiento__fecha')

        # 3. Aplicar filtros de fecha si existen
        filtros_movimiento = Q()
        if fecha_inicio:
            # Se usa .date() para comparar solo la parte de la fecha
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            filtros_movimiento &= Q(movimiento__fecha__gte=fecha_inicio_obj)
        if fecha_fin:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            # Asegura que se incluya todo el día final (hasta las 23:59:59 si se usa un campo datetime)
            filtros_movimiento &= Q(movimiento__fecha__lte=fecha_fin_obj)

        if filtros_movimiento:
             detalles_qs = detalles_qs.filter(filtros_movimiento)
        
        # 4. Agrupar por producto y calcular el saldo (con la lógica de suma/resta)
        productos_dict = {}
        
        for detalle in detalles_qs:
            producto_id = detalle.producto.id
            mov = detalle.movimiento
            
            if producto_id not in productos_dict:
                productos_dict[producto_id] = {
                    'producto_id': producto_id,
                    'codigo': detalle.producto.codigo,
                    'nombre': detalle.producto.nombre,
                    'categoria': detalle.producto.categoria.nombre if detalle.producto.categoria else '-',
                    'unidad': detalle.producto.unidad_medida.abreviatura if detalle.producto.unidad_medida else 'UND',
                    'movimientos': set(),
                    'cantidad_buena': Decimal('0'),
                    'cantidad_danada': Decimal('0'),
                }
            
            productos_dict[producto_id]['movimientos'].add(mov.id)
            
            cant_b = detalle.cantidad or Decimal('0')
            cant_d = detalle.cantidad_danada or Decimal('0')
            
            # === LÓGICA DE SALDO (Suma o Resta) ===
            
            # Caso 1: ENTRADA directa al cliente (SUMA)
            if mov.tipo == 'ENTRADA' and mov.cliente_id == cli_id_param:
                productos_dict[producto_id]['cantidad_buena'] += cant_b
                productos_dict[producto_id]['cantidad_danada'] += cant_d
                
            # Caso 2: SALIDA directa del cliente (RESTA)
            elif mov.tipo == 'SALIDA' and mov.cliente_id == cli_id_param:
                productos_dict[producto_id]['cantidad_buena'] -= cant_b
                productos_dict[producto_id]['cantidad_danada'] -= cant_d
                
            # Caso 3: TRASLADO
            elif mov.tipo == 'TRASLADO':
                es_origen = (mov.cliente_origen_id == cli_id_param)
                es_destino = (mov.cliente_destino_id == cli_id_param)
                
                if es_origen:
                    # Cliente envía producto (RESTA)
                    productos_dict[producto_id]['cantidad_buena'] -= cant_b
                    productos_dict[producto_id]['cantidad_danada'] -= cant_d
                elif es_destino:
                    # Cliente recibe producto (SUMA)
                    productos_dict[producto_id]['cantidad_buena'] += cant_b
                    productos_dict[producto_id]['cantidad_danada'] += cant_d

        # 5. Convertir a lista y calcular totales
        productos_list = []
        total_buena = Decimal('0')
        total_danada = Decimal('0')

        for prod_id, data in productos_dict.items():
            data['total_movimientos'] = len(data['movimientos'])
            data['cantidad_total'] = data['cantidad_buena'] + data['cantidad_danada']
            
            # Solo incluir productos con stock distinto de cero o con movimientos en el rango
            if data['cantidad_total'] != Decimal('0') or len(data['movimientos']) > 0:
                productos_list.append({
                    'producto_id': data['producto_id'],
                    'codigo': data['codigo'],
                    'nombre': data['nombre'],
                    'categoria': data['categoria'],
                    'unidad': data['unidad'],
                    'total_movimientos': data['total_movimientos'],
                    # Convertir Decimal a float para JsonResponse (puede haber pérdida de precisión)
                    'cantidad_buena': float(data['cantidad_buena']), 
                    'cantidad_danada': float(data['cantidad_danada']),
                    'cantidad_total': float(data['cantidad_total']),
                })
                
                total_buena += data['cantidad_buena']
                total_danada += data['cantidad_danada']
        
        # Respuesta de éxito
        return JsonResponse({
            'success': True,  # ✅ CORRECCIÓN: Cambiar 'status' por 'success'
            'cliente': {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'codigo': cliente.codigo,
                'direccion': cliente.direccion or '-',
                'telefono': cliente.telefono or '-'
            },
            'total_productos': len(productos_list),
            'productos': productos_list,
            'totales': {
                'total_entregas': sum(p['total_movimientos'] for p in productos_list),
                'cantidad_buena': float(total_buena),
                'cantidad_danada': float(total_danada),
                'cantidad_total': float(total_buena + total_danada)
            }
        })
            
    # --- Manejo de errores ---
    except Cliente.DoesNotExist:
        # Error 404
        return JsonResponse({
            'success': False,
            'error': 'Cliente no encontrado'
        }, status=404)
        
    except Exception as e:
        # Error 500
        print("ERROR en obtener_productos_cliente:")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

@staff_member_required
def obtener_clientes_producto(request):
    """
    Vista para obtener todos los clientes que recibieron un producto específico
    """
    try:
        producto_id = request.GET.get('producto_id')
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')
        
        if not producto_id:
            return JsonResponse({
                'success': False,
                'error': 'Falta el parámetro producto_id'
            })
        
        from beneficiarios.models import Cliente, DetalleMovimientoCliente, MovimientoCliente
        from productos.models import Producto
        
        producto = Producto.objects.get(id=producto_id)
        
        # Convertir fechas
        fecha_inicio_obj = None
        fecha_fin_obj = None
        
        if fecha_inicio:
            try:
                fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if fecha_fin:
            try:
                fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Filtrar movimientos
        movimientos_qs = MovimientoCliente.objects.all()
        
        if fecha_inicio_obj:
            movimientos_qs = movimientos_qs.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos_qs = movimientos_qs.filter(fecha__lte=fecha_fin_obj)
        
        # Obtener detalles de este producto
        detalles_qs = DetalleMovimientoCliente.objects.filter(
            movimiento__in=movimientos_qs,
            producto=producto
        ).select_related('movimiento', 'movimiento__cliente')
        
        # Agrupar por cliente
        clientes_dict = {}
        
        for detalle in detalles_qs:
            mov = detalle.movimiento
            # Determinar cuál es el cliente principal de esta fila para el reporte
            # Nota: En traslados, un solo movimiento involucra 2 clientes. 
            # Esta lógica agrupa por el cliente "principal" del movimiento o evalúa origen/destino.
            
            # Para simplificar y asegurar que aparezcan AMBOS clientes en un traslado,
            # deberíamos procesar origen y destino por separado si es traslado.
            
            clientes_a_procesar = []
            
            cant_b = detalle.cantidad or Decimal('0')
            cant_d = detalle.cantidad_danada or Decimal('0')
            
            if mov.tipo == 'TRASLADO':
                if mov.cliente_origen:
                    clientes_a_procesar.append({
                        'cliente': mov.cliente_origen,
                        'signo': -1 # Resta
                    })
                if mov.cliente_destino:
                    clientes_a_procesar.append({
                        'cliente': mov.cliente_destino,
                        'signo': 1 # Suma
                    })
            elif mov.tipo == 'ENTRADA':
                if mov.cliente:
                    clientes_a_procesar.append({'cliente': mov.cliente, 'signo': 1}) # Suma
            elif mov.tipo == 'SALIDA':
                if mov.cliente:
                    clientes_a_procesar.append({'cliente': mov.cliente, 'signo': -1}) # Resta

            # Procesar los clientes identificados
            for item in clientes_a_procesar:
                cli = item['cliente']
                signo = item['signo']
                cli_id = cli.id
                
                if cli_id not in clientes_dict:
                    clientes_dict[cli_id] = {
                        'cliente_id': cli_id,
                        'codigo': cli.codigo,
                        'nombre': cli.nombre,
                        'direccion': cli.direccion or '-',
                        'telefono': cli.telefono or '-',
                        'movimientos': set(),
                        'cantidad_buena': Decimal('0'),
                        'cantidad_danada': Decimal('0'),
                    }
                
                clientes_dict[cli_id]['movimientos'].add(mov.id)
                
                # Aplicar suma o resta según el signo
                clientes_dict[cli_id]['cantidad_buena'] += (cant_b * signo)
                clientes_dict[cli_id]['cantidad_danada'] += (cant_d * signo)
        
        # Convertir a lista
        clientes_list = []
        total_entregas_general = 0
        total_cantidad_buena = Decimal('0')
        total_cantidad_danada = Decimal('0')
        
        for cliente_id, item in clientes_dict.items():
            item['total_entregas'] = len(item['movimientos'])
            item['cantidad_total'] = item['cantidad_buena'] + item['cantidad_danada']
            
            total_entregas_general += item['total_entregas']
            total_cantidad_buena += item['cantidad_buena']
            total_cantidad_danada += item['cantidad_danada']
            
            # Limpiar sets
            del item['movimientos']
            
            clientes_list.append(item)
        
        # Ordenar por cantidad descendente
        clientes_list.sort(key=lambda x: x['codigo'])
        
        return JsonResponse({
            'success': True,
            'producto': {
                'id': producto.id,
                'codigo': producto.codigo,
                'nombre': producto.nombre,
                'categoria': producto.categoria.nombre if producto.categoria else '-',
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'total_clientes': len(clientes_list),
            'clientes': clientes_list,
            'totales': {
                'total_entregas': total_entregas_general,
                'cantidad_buena': str(total_cantidad_buena),
                'cantidad_danada': str(total_cantidad_danada),
                'cantidad_total': str(total_cantidad_buena + total_cantidad_danada)
            }
        })
        
    except Producto.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Producto no encontrado'
        })
    except Exception as e:
        import traceback
        print("ERROR en obtener_clientes_producto:")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

# ==============================================================================
# VISTAS AJAX PARA REPORTE DE STOCK REAL
# ==============================================================================

@staff_member_required
def obtener_detalle_stock_real(request):
    """
    Vista AJAX para obtener el detalle completo de stock REAL de un producto en un almacén
    Incluye movimientos de almacén Y de clientes
    """
    producto_id = request.GET.get('producto_id')
    almacen_id = request.GET.get('almacen_id')
    
    if not producto_id or not almacen_id:
        return JsonResponse({
            'success': False,
            'error': 'Faltan parámetros requeridos'
        })
    
    try:
        from reportes.models import ReporteStockReal
        
        producto = Producto.objects.get(id=producto_id)
        almacen = Almacen.objects.get(id=almacen_id)
        
        # Calcular stock real
        stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(producto, almacen)
        
        # ✅ OBTENER TODOS LOS MOVIMIENTOS DE ALMACÉN (sin límite [:10])
        movimientos_almacen = MovimientoAlmacen.objects.filter(
            Q(almacen_origen=almacen) | Q(almacen_destino=almacen),
            detalles__producto=producto
        ).select_related(
            'proveedor',
            'recepcionista',
            'almacen_destino',
            'almacen_origen'
        ).prefetch_related('detalles').distinct().order_by('-fecha', '-id')  # ✅ Sin límite
        
        # ✅ OBTENER TODOS LOS MOVIMIENTOS DE CLIENTE (sin límite [:10])
        from beneficiarios.models import MovimientoCliente
        movimientos_cliente = MovimientoCliente.objects.filter(
            Q(almacen_origen=almacen) | Q(almacen_destino=almacen),
            detalles__producto=producto
        ).exclude(tipo='TRASLADO').select_related(
            'cliente',
            'proveedor',
            'recepcionista',
            'almacen_origen',
            'almacen_destino'
        ).prefetch_related('detalles').distinct().order_by('-fecha', '-id')  # ✅ Sin límite
        
        # Procesar movimientos de almacén
        movimientos_alm_list = []
        for mov in movimientos_almacen:
            detalle = mov.detalles.filter(producto=producto).first()
            if detalle:
                cantidad_buena = detalle.cantidad or 0
                cantidad_danada = detalle.cantidad_danada or 0
                cantidad_total = cantidad_buena + cantidad_danada
                
                if cantidad_buena > 0 and cantidad_danada > 0:
                    estado = 'MIXTO'
                elif cantidad_buena > 0:
                    estado = 'BUENO'
                elif cantidad_danada > 0:
                    estado = 'DAÑADO'
                else:
                    estado = '-'
                
                movimientos_alm_list.append({
                    'numero_movimiento': mov.numero_movimiento,
                    'tipo': f"ALM-{mov.get_tipo_display()}",
                    'fecha': mov.fecha.strftime('%d/%m/%Y'),
                    'fecha_ordenamiento': mov.fecha,  # ✅ AGREGADO: Para ordenar después
                    'cantidad': str(cantidad_total),
                    'cantidad_buena': str(cantidad_buena),
                    'cantidad_danada': str(cantidad_danada),
                    'estado': estado,
                    'proveedor': mov.proveedor.nombre if mov.proveedor else None,
                    'recepcionista': str(mov.recepcionista) if mov.recepcionista else None,
                    'almacen_origen': mov.almacen_origen.nombre if mov.almacen_origen else None,
                    'almacen_destino': mov.almacen_destino.nombre if mov.almacen_destino else None,
                })
        
        # Procesar movimientos de cliente
        movimientos_cli_list = []
        for mov in movimientos_cliente:
            detalle = mov.detalles.filter(producto=producto).first()
            if detalle:
                cantidad_buena = detalle.cantidad or 0
                cantidad_danada = detalle.cantidad_danada or 0
                cantidad_total = cantidad_buena + cantidad_danada
                
                if cantidad_buena > 0 and cantidad_danada > 0:
                    estado = 'MIXTO'
                elif cantidad_buena > 0:
                    estado = 'BUENO'
                elif cantidad_danada > 0:
                    estado = 'DAÑADO'
                else:
                    estado = '-'
                
                movimientos_cli_list.append({
                    'numero_movimiento': mov.numero_movimiento,
                    'tipo': f"CLI-{mov.get_tipo_display()}",
                    'fecha': mov.fecha.strftime('%d/%m/%Y'),
                    'fecha_ordenamiento': mov.fecha,  # ✅ AGREGADO: Para ordenar después
                    'cantidad': str(cantidad_total),
                    'cantidad_buena': str(cantidad_buena),
                    'cantidad_danada': str(cantidad_danada),
                    'estado': estado,
                    'cliente': mov.cliente.nombre if mov.cliente else None,
                    'proveedor': mov.proveedor.nombre if mov.proveedor else None,
                    'recepcionista': str(mov.recepcionista) if mov.recepcionista else None,
                    'almacen_origen': mov.almacen_origen.nombre if mov.almacen_origen else None,
                    'almacen_destino': mov.almacen_destino.nombre if mov.almacen_destino else None,
                })
        
        # ✅ Combinar TODOS los movimientos (sin límite [:20])
        todos_movimientos = movimientos_alm_list + movimientos_cli_list
        
        # ✅ Ordenar por fecha descendente (más recientes primero)
        todos_movimientos.sort(key=lambda x: x['fecha_ordenamiento'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'producto': {
                'nombre': producto.nombre,
                'codigo': producto.codigo,
                'categoria': producto.categoria.nombre if producto.categoria else None,
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'almacen': {
                'nombre': almacen.nombre
            },
            'resumen': {
                'entradas_almacen': str(stock_data['entradas_almacen_total']),
                'salidas_almacen': str(stock_data['salidas_almacen_total']),
                'traslados_recibidos': str(stock_data['traslados_recibidos_total']),
                'traslados_enviados': str(stock_data['traslados_enviados_total']),
                'entradas_cliente': str(stock_data['entradas_cliente_total']),
                'salidas_cliente': str(stock_data['salidas_cliente_total']),
                'stock_bueno': str(stock_data['stock_bueno']),
                'stock_danado': str(stock_data['stock_danado']),
                'stock_total': str(stock_data['stock_total'])
            },
            'movimientos': todos_movimientos  # ✅ TODOS los movimientos
        })
        
    except Producto.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Producto no encontrado'
        })
    except Almacen.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Almacén no encontrado'
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}',
            'traceback': traceback.format_exc()
        })


@staff_member_required
def obtener_detalle_almacen_real(request):
    """
    Vista AJAX para obtener todos los productos de un almacén con stock REAL
    ✅ CORREGIDO: Muestra productos con stock = 0 si tienen movimientos
    """
    almacen_id = request.GET.get('almacen_id')
    
    if not almacen_id:
        return JsonResponse({
            'success': False,
            'error': 'Falta el parámetro almacen_id'
        })
    
    try:
        from reportes.models import ReporteStockReal
        from almacenes.models import DetalleMovimientoAlmacen
        from beneficiarios.models import DetalleMovimientoCliente
        
        almacen = Almacen.objects.get(id=almacen_id)
        
        # ✅ Obtener todos los productos que tienen movimientos en este almacén
        # (de almacén O de cliente)
        productos_ids_almacen = set(DetalleMovimientoAlmacen.objects.filter(
            Q(movimiento__almacen_origen=almacen) | Q(movimiento__almacen_destino=almacen)
        ).values_list('producto_id', flat=True).distinct())
        
        productos_ids_cliente = set(DetalleMovimientoCliente.objects.filter(
            Q(movimiento__almacen_origen=almacen) | Q(movimiento__almacen_destino=almacen)
        ).exclude(movimiento__tipo='TRASLADO').values_list('producto_id', flat=True).distinct())
        
        # Combinar ambos conjuntos
        productos_ids = productos_ids_almacen | productos_ids_cliente
        
        productos_list = []
        
        for producto_id in productos_ids:
            try:
                producto = Producto.objects.get(id=producto_id, activo=True)
                
                stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                    producto, almacen
                )
                
                # ✅ CAMBIO: Mostrar TODOS los productos con movimientos, incluso con stock = 0
                productos_list.append({
                    'producto_id': producto.id,
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'categoria': producto.categoria.nombre if producto.categoria else '-',
                    'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND',
                    'stock_bueno': str(stock_data['stock_bueno']),
                    'stock_danado': str(stock_data['stock_danado']),
                    'stock_total': str(stock_data['stock_total']),
                    'entradas_almacen': str(stock_data['entradas_almacen_total']),
                    'salidas_almacen': str(stock_data['salidas_almacen_total']),
                    'traslados_recibidos': str(stock_data['traslados_recibidos_total']),
                    'traslados_enviados': str(stock_data['traslados_enviados_total']),
                    'entradas_cliente': str(stock_data['entradas_cliente_total']),
                    'salidas_cliente': str(stock_data['salidas_cliente_total']),
                })
            except Producto.DoesNotExist:
                continue
        
        # Ordenar por código de producto
        productos_list.sort(key=lambda x: x['codigo'])
        
        return JsonResponse({
            'success': True,
            'almacen': {
                'id': almacen.id,
                'nombre': almacen.nombre
            },
            'total_productos': len(productos_list),
            'productos': productos_list
        })
        
    except Almacen.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Almacén no encontrado'
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}',
            'traceback': traceback.format_exc()
        })


@staff_member_required
def obtener_detalle_producto_almacenes_real(request):
    """
    Vista AJAX para obtener la distribución REAL de un producto en todos los almacenes
    ✅ CORREGIDO: Muestra almacenes con stock = 0 si tienen movimientos
    """
    producto_id = request.GET.get('producto_id')
    
    if not producto_id:
        return JsonResponse({
            'success': False,
            'error': 'Falta el parámetro producto_id'
        })
    
    try:
        from reportes.models import ReporteStockReal
        from almacenes.models import DetalleMovimientoAlmacen
        from beneficiarios.models import DetalleMovimientoCliente
        
        producto = Producto.objects.get(id=producto_id)
        
        # ✅ Obtener todos los almacenes que tienen movimientos de este producto
        # (de almacén O de cliente)
        almacenes_ids_alm = set()
        for detalle in DetalleMovimientoAlmacen.objects.filter(producto=producto).select_related('movimiento'):
            if detalle.movimiento.almacen_origen:
                almacenes_ids_alm.add(detalle.movimiento.almacen_origen.id)
            if detalle.movimiento.almacen_destino:
                almacenes_ids_alm.add(detalle.movimiento.almacen_destino.id)
        
        almacenes_ids_cli = set()
        for detalle in DetalleMovimientoCliente.objects.filter(producto=producto).exclude(movimiento__tipo='TRASLADO').select_related('movimiento'):
            if detalle.movimiento.almacen_origen:
                almacenes_ids_cli.add(detalle.movimiento.almacen_origen.id)
            if detalle.movimiento.almacen_destino:
                almacenes_ids_cli.add(detalle.movimiento.almacen_destino.id)
        
        # Combinar ambos conjuntos
        almacenes_ids = almacenes_ids_alm | almacenes_ids_cli
        
        almacenes_list = []
        total_stock_bueno = Decimal('0')
        total_stock_danado = Decimal('0')
        total_stock_general = Decimal('0')
        
        for almacen_id in almacenes_ids:
            try:
                almacen = Almacen.objects.get(id=almacen_id, activo=True)
                
                stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                    producto, almacen
                )
                
                # ✅ CAMBIO: Mostrar TODOS los almacenes con movimientos, incluso con stock = 0
                almacenes_list.append({
                    'almacen_id': almacen.id,
                    'almacen_nombre': almacen.nombre,
                    'stock_bueno': str(stock_data['stock_bueno']),
                    'stock_danado': str(stock_data['stock_danado']),
                    'stock_total': str(stock_data['stock_total']),
                    'entradas_almacen': str(stock_data['entradas_almacen_total']),
                    'salidas_almacen': str(stock_data['salidas_almacen_total']),
                    'traslados_recibidos': str(stock_data['traslados_recibidos_total']),
                    'traslados_enviados': str(stock_data['traslados_enviados_total']),
                    'entradas_cliente': str(stock_data['entradas_cliente_total']),
                    'salidas_cliente': str(stock_data['salidas_cliente_total']),
                })
                
                total_stock_bueno += Decimal(str(stock_data['stock_bueno']))
                total_stock_danado += Decimal(str(stock_data['stock_danado']))
                total_stock_general += Decimal(str(stock_data['stock_total']))
            except Almacen.DoesNotExist:
                continue
        
        # Ordenar por nombre de almacén
        almacenes_list.sort(key=lambda x: x['almacen_nombre'])
        
        return JsonResponse({
            'success': True,
            'producto': {
                'id': producto.id,
                'codigo': producto.codigo,
                'nombre': producto.nombre,
                'categoria': producto.categoria.nombre if producto.categoria else '-',
                'unidad': producto.unidad_medida.abreviatura if producto.unidad_medida else 'UND'
            },
            'total_almacenes': len(almacenes_list),
            'almacenes': almacenes_list,
            'totales': {
                'stock_bueno': str(total_stock_bueno),
                'stock_danado': str(total_stock_danado),
                'stock_total': str(total_stock_general)
            }
        })
        
    except Producto.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Producto no encontrado'
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}',
            'traceback': traceback.format_exc()
        })


@staff_member_required
def obtener_detalle_estadistica_real(request):
    """
    Vista AJAX para obtener detalles de estadísticas del reporte de stock REAL
    ✅ CORREGIDO: Muestra stocks negativos y cero con advertencias
    """
    tipo = request.GET.get('tipo')
    
    try:
        from reportes.models import ReporteStockReal
        
        if tipo == 'total_productos':
            total_productos = Producto.objects.filter(activo=True).count()
            
            productos_ids_con_stock = set()
            productos_ids_con_stock_negativo = set()  # ✅ NUEVO
            
            for producto in Producto.objects.filter(activo=True):
                almacenes = Almacen.objects.filter(activo=True)
                stock_total_producto = Decimal('0')
                
                for almacen in almacenes:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    stock_total_producto += Decimal(str(stock_data['stock_total']))
                
                if stock_total_producto > 0:
                    productos_ids_con_stock.add(producto.id)
                elif stock_total_producto < 0:
                    productos_ids_con_stock_negativo.add(producto.id)
            
            productos_con_stock = len(productos_ids_con_stock)
            productos_sin_stock = total_productos - productos_con_stock - len(productos_ids_con_stock_negativo)
            
            por_categoria = Producto.objects.filter(activo=True).values(
                categoria_nombre=F('categoria__nombre')
            ).annotate(
                total=Count('id')
            ).order_by('-total')
            
            categorias_list = []
            for cat in por_categoria:
                categorias_list.append({
                    'categoria': cat['categoria_nombre'] if cat['categoria_nombre'] else 'Sin Categoría',
                    'total': cat['total']
                })
            
            return JsonResponse({
                'success': True,
                'total_productos': total_productos,
                'productos_con_stock': productos_con_stock,
                'productos_sin_stock': productos_sin_stock,
                'productos_con_stock_negativo': len(productos_ids_con_stock_negativo),  # ✅ NUEVO
                'por_categoria': categorias_list
            })
        
        elif tipo == 'stock_bueno':
            # ✅ Similar a la versión anterior, con cambios para incluir negativos
            total_stock_bueno = Decimal('0')
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True)
            
            for almacen in almacenes:
                for producto in productos:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    total_stock_bueno += Decimal(str(stock_data['stock_bueno']))
            
            productos_con_stock_bueno = 0
            productos_con_stock_bueno_negativo = 0  # ✅ NUEVO
            
            for producto in productos:
                stock_producto = Decimal('0')
                for almacen in almacenes:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    stock_producto += Decimal(str(stock_data['stock_bueno']))
                
                if stock_producto > 0:
                    productos_con_stock_bueno += 1
                elif stock_producto < 0:
                    productos_con_stock_bueno_negativo += 1
            
            # ✅ CAMBIO: Mostrar TODOS los almacenes
            almacenes_list = []
            for almacen in almacenes:
                stock_bueno_almacen = Decimal('0')
                
                for producto in productos:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    stock_bueno_almacen += Decimal(str(stock_data['stock_bueno']))
                
                almacenes_list.append({
                    'almacen': almacen.nombre,
                    'almacen_id': almacen.id,
                    'stock_bueno': float(stock_bueno_almacen),
                    'es_negativo': stock_bueno_almacen < 0,
                    'es_cero': stock_bueno_almacen == 0
                })
            
            # Ordenar: negativos primero
            almacenes_list.sort(key=lambda x: (not x['es_negativo'], -abs(x['stock_bueno'])))
            
            return JsonResponse({
                'success': True,
                'total_stock_bueno': float(total_stock_bueno),
                'productos_con_stock_bueno': productos_con_stock_bueno,
                'productos_con_stock_bueno_negativo': productos_con_stock_bueno_negativo,  # ✅ NUEVO
                'por_almacen': almacenes_list
            })
        
        elif tipo == 'stock_danado':
            # ✅ Similar implementación
            total_stock_danado = Decimal('0')
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True)
            
            for almacen in almacenes:
                for producto in productos:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    total_stock_danado += Decimal(str(stock_data['stock_danado']))
            
            productos_con_stock_danado = 0
            productos_con_stock_danado_negativo = 0  # ✅ NUEVO
            
            for producto in productos:
                stock_producto = Decimal('0')
                for almacen in almacenes:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    stock_producto += Decimal(str(stock_data['stock_danado']))
                
                if stock_producto > 0:
                    productos_con_stock_danado += 1
                elif stock_producto < 0:
                    productos_con_stock_danado_negativo += 1
            
            almacenes_list = []
            for almacen in almacenes:
                stock_danado_almacen = Decimal('0')
                
                for producto in productos:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    stock_danado_almacen += Decimal(str(stock_data['stock_danado']))
                
                almacenes_list.append({
                    'almacen': almacen.nombre,
                    'almacen_id': almacen.id,
                    'stock_danado': float(stock_danado_almacen),
                    'es_negativo': stock_danado_almacen < 0,
                    'es_cero': stock_danado_almacen == 0
                })
            
            almacenes_list.sort(key=lambda x: (not x['es_negativo'], -abs(x['stock_danado'])))
            
            # Top productos
            productos_danados = []
            for producto in productos:
                stock_danado_producto = Decimal('0')
                
                for almacen in almacenes:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    stock_danado_producto += Decimal(str(stock_data['stock_danado']))
                
                if stock_danado_producto != 0:
                    productos_danados.append({
                        'producto': producto.nombre,
                        'codigo': producto.codigo,
                        'producto_id': producto.id,
                        'stock_danado': float(stock_danado_producto),
                        'es_negativo': stock_danado_producto < 0
                    })
            
            productos_danados.sort(key=lambda x: (not x['es_negativo'], -abs(x['stock_danado'])))
            productos_list = productos_danados[:10]
            
            return JsonResponse({
                'success': True,
                'total_stock_danado': float(total_stock_danado),
                'productos_con_stock_danado': productos_con_stock_danado,
                'productos_con_stock_danado_negativo': productos_con_stock_danado_negativo,  # ✅ NUEVO
                'por_almacen': almacenes_list,
                'productos_mas_danados': productos_list
            })
        
        elif tipo == 'total_almacenes':
            almacenes = Almacen.objects.filter(activo=True)
            total_almacenes = almacenes.count()
            productos = Producto.objects.filter(activo=True)
            
            almacenes_list = []
            
            for almacen in almacenes:
                total_productos_almacen = 0
                stock_total = Decimal('0')
                stock_bueno = Decimal('0')
                stock_danado = Decimal('0')
                
                for producto in productos:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    
                    if stock_data['stock_total'] > 0:
                        total_productos_almacen += 1
                        stock_bueno += Decimal(str(stock_data['stock_bueno']))
                        stock_danado += Decimal(str(stock_data['stock_danado']))
                        stock_total += Decimal(str(stock_data['stock_total']))
                
                almacenes_list.append({
                    'id': almacen.id,
                    'nombre': almacen.nombre,
                    'total_productos': total_productos_almacen,
                    'stock_total': float(stock_total),
                    'stock_bueno': float(stock_bueno),
                    'stock_danado': float(stock_danado)
                })
            
            return JsonResponse({
                'success': True,
                'total_almacenes': total_almacenes,
                'almacenes': almacenes_list
            })
        
        elif tipo == 'bajo_minimo':
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True, stock_minimo__isnull=False, stock_minimo__gt=0)
            
            productos_list = []
            
            for producto in productos:
                for almacen in almacenes:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    
                    stock_bueno_actual = stock_data['stock_bueno']
                    
                    if stock_bueno_actual < producto.stock_minimo:
                        productos_list.append({
                            'producto': producto.nombre,
                            'codigo': producto.codigo,
                            'producto_id': producto.id,
                            'almacen': almacen.nombre,
                            'almacen_id': almacen.id,
                            'stock_actual': float(stock_bueno_actual),
                            'stock_minimo': float(producto.stock_minimo),
                            'diferencia': float(producto.stock_minimo - stock_bueno_actual)
                        })
            
            # Ordenar por diferencia descendente
            productos_list.sort(key=lambda x: x['diferencia'], reverse=True)
            
            total_bajo_minimo = len(productos_list)
            
            return JsonResponse({
                'success': True,
                'total_bajo_minimo': total_bajo_minimo,
                'productos': productos_list[:20]  # Limitar a 20 para rendimiento
            })
        
        elif tipo == 'valor_inventario':
            total_productos = Producto.objects.filter(activo=True).count()
            almacenes = Almacen.objects.filter(activo=True)
            productos = Producto.objects.filter(activo=True)
            
            total_items = Decimal('0')
            
            for almacen in almacenes:
                for producto in productos:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    
                    if stock_data['stock_total'] > 0:
                        total_items += Decimal(str(stock_data['stock_total']))
            
            # Valoración por categoría
            categorias_dict = {}
            
            for producto in productos:
                categoria_nombre = producto.categoria.nombre if producto.categoria else 'Sin Categoría'
                
                if categoria_nombre not in categorias_dict:
                    categorias_dict[categoria_nombre] = Decimal('0')
                
                for almacen in almacenes:
                    stock_data = ReporteStockReal.calcular_stock_real_producto_almacen(
                        producto, almacen
                    )
                    
                    if stock_data['stock_total'] > 0:
                        categorias_dict[categoria_nombre] += Decimal(str(stock_data['stock_total']))
            
            categorias_list = []
            for categoria, total in categorias_dict.items():
                if total > 0:
                    categorias_list.append({
                        'categoria': categoria,
                        'total_items': float(total)
                    })
            
            # Ordenar por total descendente
            categorias_list.sort(key=lambda x: x['total_items'], reverse=True)
            
            return JsonResponse({
                'success': True,
                'total_productos': total_productos,
                'total_items': float(total_items),
                'por_categoria': categorias_list
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Tipo de estadística no válido'
            }, status=400)
    
    except Exception as e:
        import traceback
        print("ERROR en obtener_detalle_estadistica_real:")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@staff_member_required
def exportar_stock_real_excel(request):
    """
    Exporta el reporte de Stock Real a Excel (.xlsx) de manera optimizada
    usando ReporteStockReal.obtener_data_masiva.
    """
    try:
        # 1. Recuperar Filtros y Conversión de tipos
        almacen_id = request.GET.get('almacen', '')
        categoria_id = request.GET.get('categoria', '')
        producto_id = request.GET.get('producto', '')
        stock_minimo = request.GET.get('stock_minimo', '')
        solo_con_stock = request.GET.get('solo_con_stock', '')
        
        # Conversión de tipos
        almacen_id_int = int(almacen_id) if almacen_id else None
        categoria_id_int = int(categoria_id) if categoria_id else None
        producto_id_int = int(producto_id) if producto_id else None

        # 2. 🚀 OBTENER DATOS MASIVOS OPTIMIZADOS (Una sola consulta grande)
        dataset_completo = ReporteStockReal.obtener_data_masiva(
            almacen_id=almacen_id_int,
            categoria_id=categoria_id_int,
            producto_id=producto_id_int,
            stock_minimo=(stock_minimo=='on'),
            solo_con_stock=(solo_con_stock=='on')
        )
        
        # 3. Preparar el archivo Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "ReporteStockReal"
        
        # Estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="337AB7", end_color="337AB7", fill_type="solid")
        right_alignment = Alignment(horizontal="right", vertical="center")
        center_alignment = Alignment(horizontal="center", vertical="center")

        # Encabezados
        headers = [
            _("Almacén"), _("Código Producto"), _("Nombre Producto"), _("Categoría"), 
            _("U/M"), _("Stock Mínimo"), 
            _("E. Almacén"), _("S. Almacén"), 
            _("T. Recibidos"), _("T. Enviados"), 
            _("E. Cliente"), _("S. Cliente"), 
            _("Stock Bueno"), _("Stock Dañado"), _("Stock Total")
        ]
        ws.append(headers)

        # Aplicar estilos a la cabecera
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            cell = ws[f'{col_letter}1']
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_alignment
        
        # Ajustar ancho de columnas para mejor visualización (opcional)
        ws.column_dimensions['C'].width = 40
        ws.column_dimensions['E'].width = 10
        
        # 4. Iterar sobre la lista optimizada y escribir filas
        for row_num, data in enumerate(dataset_completo, 2):
            producto = data['producto']
            almacen = data['almacen']
            
            row = [
                almacen.nombre,
                producto.codigo,
                producto.nombre,
                producto.categoria.nombre if producto.categoria else '',
                producto.unidad_medida.nombre if producto.unidad_medida else '',
                producto.stock_minimo,
                # Totales de Movimientos
                data['entradas_almacen_total'],
                data['salidas_almacen_total'],
                data['traslados_recibidos_total'],
                data['traslados_enviados_total'],
                data['entradas_cliente_total'], 
                data['salidas_cliente_total'],  
                # Stock Final
                data['stock_bueno'],
                data['stock_danado'],
                data['stock_total']
            ]
            ws.append(row)
            
            # Aplicar formato de números (columnas G a O) y alineación
            for col_idx in range(7, 16): 
                col_letter = get_column_letter(col_idx)
                cell = ws[f'{col_letter}{row_num}']
                cell.number_format = '#,##0.00'
                cell.alignment = right_alignment
                
            # Resaltar si está bajo stock mínimo
            if producto.stock_minimo and data['stock_bueno'] <= producto.stock_minimo:
                 red_fill = PatternFill(start_color="F5C3C2", end_color="F5C3C2", fill_type="solid")
                 for col_idx in range(1, 16):
                    col_letter = get_column_letter(col_idx)
                    ws[f'{col_letter}{row_num}'].fill = red_fill

        # 5. Configurar y devolver la respuesta HTTP
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="ReporteStockReal_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        
        wb.save(response)
        return response

    except Exception as e:
        # Esto ayuda a diagnosticar errores en producción
        return HttpResponse(f"Error al exportar a Excel: {e}\n{traceback.format_exc()}", status=500)

@staff_member_required
def exportar_stock_real_csv(request):
    """
    Exporta el reporte de Stock Real a CSV de manera optimizada.
    """
    try:
        # 1. Recuperar Filtros
        almacen_id = request.GET.get('almacen', '')
        categoria_id = request.GET.get('categoria', '')
        producto_id = request.GET.get('producto', '')
        stock_minimo = request.GET.get('stock_minimo', '')
        solo_con_stock = request.GET.get('solo_con_stock', '')
        
        # Conversión de tipos
        almacen_id_int = int(almacen_id) if almacen_id else None
        categoria_id_int = int(categoria_id) if categoria_id else None
        producto_id_int = int(producto_id) if producto_id else None

        # 2. 🚀 OBTENER DATOS MASIVOS OPTIMIZADOS (Una sola consulta grande)
        dataset_completo = ReporteStockReal.obtener_data_masiva(
            almacen_id=almacen_id_int,
            categoria_id=categoria_id_int,
            producto_id=producto_id_int,
            stock_minimo=(stock_minimo=='on'),
            solo_con_stock=(solo_con_stock=='on')
        )
        
        # 3. Preparar la respuesta HTTP para CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="ReporteStockReal_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        response.write(u'\ufeff'.encode('utf8')) # BOM para UTF-8 y compatibilidad con Excel
        
        writer = csv.writer(response)

        # 4. Escribir la cabecera
        headers = [
            _("Almacén"), _("Código Producto"), _("Nombre Producto"), _("Categoría"), 
            _("U/M"), _("Stock Mínimo"), 
            _("E. Almacén"), _("S. Almacén"), 
            _("T. Recibidos"), _("T. Enviados"), 
            _("E. Cliente"), _("S. Cliente"), 
            _("Stock Bueno"), _("Stock Dañado"), _("Stock Total")
        ]
        writer.writerow(headers)

        # 5. Iterar sobre la lista optimizada y escribir filas
        for data in dataset_completo:
            producto = data['producto']
            almacen = data['almacen']
            
            row = [
                almacen.nombre,
                producto.codigo,
                producto.nombre,
                producto.categoria.nombre if producto.categoria else '',
                producto.unidad_medida.nombre if producto.unidad_medida else '',
                str(data['producto'].stock_minimo or ''), # Convertir a string para CSV
                str(data['entradas_almacen_total']),
                str(data['salidas_almacen_total']),
                str(data['traslados_recibidos_total']),
                str(data['traslados_enviados_total']),
                str(data['entradas_cliente_total']),
                str(data['salidas_cliente_total']),
                str(data['stock_bueno']),
                str(data['stock_danado']),
                str(data['stock_total'])
            ]
            writer.writerow(row)

        return response

    except Exception as e:
        return HttpResponse(f"Error al exportar a CSV: {e}\n{traceback.format_exc()}", status=500)

@staff_member_required
def obtener_detalle_estadistica_entregas(request):
    """
    Vista AJAX para obtener detalles de las estadísticas del reporte de entregas
    Similar a obtener_detalle_estadistica pero para entregas a clientes
    """
    tipo = request.GET.get('tipo')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    # Convertir fechas
    fecha_inicio_obj = None
    fecha_fin_obj = None
    
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    try:
        # Query base
        movimientos_qs = MovimientoCliente.objects.all()
        
        if fecha_inicio_obj:
            movimientos_qs = movimientos_qs.filter(fecha__gte=fecha_inicio_obj)
        if fecha_fin_obj:
            movimientos_qs = movimientos_qs.filter(fecha__lte=fecha_fin_obj)
        
        if tipo == 'total_clientes':
            # Total de clientes únicos con entregas
            clientes_ids = set()
            
            for mov in movimientos_qs:
                if mov.tipo == 'TRASLADO':
                    if mov.cliente_origen_id:
                        clientes_ids.add(mov.cliente_origen_id)
                    if mov.cliente_destino_id:
                        clientes_ids.add(mov.cliente_destino_id)
                else:
                    if mov.cliente_id:
                        clientes_ids.add(mov.cliente_id)
            
            total_clientes = len(clientes_ids)
            
            # Detalle de cada cliente
            clientes_list = []
            for cliente_id in clientes_ids:
                try:
                    cliente = Cliente.objects.get(id=cliente_id)
                    
                    # Calcular movimientos de este cliente
                    movs_cliente = movimientos_qs.filter(
                        Q(cliente_id=cliente_id) |
                        Q(cliente_origen_id=cliente_id) |
                        Q(cliente_destino_id=cliente_id)
                    ).count()
                    
                    # Calcular productos únicos
                    productos_ids = set(DetalleMovimientoCliente.objects.filter(
                        movimiento__in=movimientos_qs.filter(
                            Q(cliente_id=cliente_id) |
                            Q(cliente_origen_id=cliente_id) |
                            Q(cliente_destino_id=cliente_id)
                        )
                    ).values_list('producto_id', flat=True))
                    
                    clientes_list.append({
                        'id': cliente.id,
                        'nombre': cliente.nombre,
                        'codigo': cliente.codigo,
                        'total_movimientos': movs_cliente,
                        'total_productos': len(productos_ids)
                    })
                except Cliente.DoesNotExist:
                    continue
            
            # Ordenar por total de movimientos
            clientes_list.sort(key=lambda x: x['total_movimientos'], reverse=True)
            
            return JsonResponse({
                'success': True,
                'total_clientes': total_clientes,
                'clientes': clientes_list[:20]  # Top 20
            })
        
        elif tipo == 'total_entregas':
            # Total de movimientos
            total_entregas = movimientos_qs.count()
            
            # Por tipo de movimiento
            por_tipo = []
            for tipo_mov in ['ENTRADA', 'SALIDA', 'TRASLADO']:
                count = movimientos_qs.filter(tipo=tipo_mov).count()
                if count > 0:
                    por_tipo.append({
                        'tipo': tipo_mov,
                        'total': count
                    })
            
            # Por mes (últimos 6 meses)
            from django.db.models.functions import TruncMonth
            por_mes = movimientos_qs.annotate(
                mes=TruncMonth('fecha')
            ).values('mes').annotate(
                total=Count('id')
            ).order_by('-mes')[:6]
            
            meses_list = []
            for item in por_mes:
                meses_list.append({
                    'mes': item['mes'].strftime('%Y-%m'),
                    'total': item['total']
                })
            
            return JsonResponse({
                'success': True,
                'total_entregas': total_entregas,
                'por_tipo': por_tipo,
                'por_mes': list(reversed(meses_list))
            })
        
        elif tipo == 'total_productos':
            # Productos diferentes entregados
            productos_ids = set(DetalleMovimientoCliente.objects.filter(
                movimiento__in=movimientos_qs
            ).values_list('producto_id', flat=True))
            
            total_productos = len(productos_ids)
            
            # Top productos por cantidad
            productos_dict = {}
            
            for detalle in DetalleMovimientoCliente.objects.filter(
                movimiento__in=movimientos_qs
            ).select_related('producto', 'movimiento'):
                
                prod_id = detalle.producto.id
                mov = detalle.movimiento
                
                if prod_id not in productos_dict:
                    productos_dict[prod_id] = {
                        'producto_id': prod_id,
                        'nombre': detalle.producto.nombre,
                        'codigo': detalle.producto.codigo,
                        'cantidad': Decimal('0')
                    }
                
                cant = (detalle.cantidad or Decimal('0')) + (detalle.cantidad_danada or Decimal('0'))
                
                # Aplicar lógica de suma/resta
                if mov.tipo == 'ENTRADA':
                    productos_dict[prod_id]['cantidad'] += cant
                elif mov.tipo == 'SALIDA':
                    productos_dict[prod_id]['cantidad'] -= cant
                elif mov.tipo == 'TRASLADO':
                    # Neutral globalmente
                    pass
            
            productos_list = []
            for prod_id, data in productos_dict.items():
                if data['cantidad'] != 0:
                    productos_list.append({
                        'producto_id': data['producto_id'],
                        'nombre': data['nombre'],
                        'codigo': data['codigo'],
                        'cantidad': float(data['cantidad'])
                    })
            
            productos_list.sort(key=lambda x: abs(x['cantidad']), reverse=True)
            
            return JsonResponse({
                'success': True,
                'total_productos': total_productos,
                'top_productos': productos_list[:20]
            })
        
        elif tipo == 'cantidad_total':
            # Cantidad total entregada (neto)
            cantidad_total = Decimal('0')
            
            for detalle in DetalleMovimientoCliente.objects.filter(
                movimiento__in=movimientos_qs
            ).select_related('movimiento'):
                
                mov = detalle.movimiento
                cant = (detalle.cantidad or Decimal('0')) + (detalle.cantidad_danada or Decimal('0'))
                
                if mov.tipo == 'ENTRADA':
                    cantidad_total += cant
                elif mov.tipo == 'SALIDA':
                    cantidad_total -= cant
            
            # Por categoría
            categorias_dict = {}
            
            for detalle in DetalleMovimientoCliente.objects.filter(
                movimiento__in=movimientos_qs
            ).select_related('producto__categoria', 'movimiento'):
                
                cat_nombre = detalle.producto.categoria.nombre if detalle.producto.categoria else 'Sin Categoría'
                mov = detalle.movimiento
                cant = (detalle.cantidad or Decimal('0')) + (detalle.cantidad_danada or Decimal('0'))
                
                if cat_nombre not in categorias_dict:
                    categorias_dict[cat_nombre] = Decimal('0')
                
                if mov.tipo == 'ENTRADA':
                    categorias_dict[cat_nombre] += cant
                elif mov.tipo == 'SALIDA':
                    categorias_dict[cat_nombre] -= cant
            
            categorias_list = []
            for cat, cantidad in categorias_dict.items():
                if cantidad != 0:
                    categorias_list.append({
                        'categoria': cat,
                        'cantidad': float(cantidad)
                    })
            
            categorias_list.sort(key=lambda x: abs(x['cantidad']), reverse=True)
            
            return JsonResponse({
                'success': True,
                'cantidad_total': float(cantidad_total),
                'por_categoria': categorias_list
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Tipo de estadística no válido'
            }, status=400)
    
    except Exception as e:
        import traceback
        print("ERROR en obtener_detalle_estadistica_entregas:")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)