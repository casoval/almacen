from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from django.utils import timezone
from django.conf import settings
import os


def get_logo_path():
    """
    Función helper para obtener la ruta del logo de forma robusta
    """
    # Opción 1: Usar STATIC_ROOT (para producción con collectstatic)
    if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
        logo_path = os.path.join(settings.STATIC_ROOT, 'logo_casoval.png')
        if os.path.exists(logo_path):
            return logo_path
    
    # Opción 2: Usar STATICFILES_DIRS (para desarrollo)
    if hasattr(settings, 'STATICFILES_DIRS'):
        for static_dir in settings.STATICFILES_DIRS:
            logo_path = os.path.join(static_dir, 'logo_casoval.png')
            if os.path.exists(logo_path):
                return logo_path
    
    # Opción 3: Usar BASE_DIR (ruta relativa al proyecto)
    if hasattr(settings, 'BASE_DIR'):
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo_casoval.png')
        if os.path.exists(logo_path):
            return logo_path
    
    # Opción 4: Buscar en la carpeta de la app
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, 'static', 'logo_casoval.png')
    if os.path.exists(logo_path):
        return logo_path
    
    # Opción 5: Buscar un nivel arriba
    parent_dir = os.path.dirname(current_dir)
    logo_path = os.path.join(parent_dir, 'static', 'logo_casoval.png')
    if os.path.exists(logo_path):
        return logo_path
    
    return None


class NumberedCanvasCliente(canvas.Canvas):
    """Canvas personalizado para reportes de cliente"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.logo_path = get_logo_path()

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_watermark()
            self.draw_header()
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_watermark(self):
        """Dibuja la marca de agua en el centro de la página"""
        if not self.logo_path:
            return
        
        try:
            self.saveState()
            self.setFillAlpha(0.1)
            
            page_width = letter[0]
            page_height = letter[1]
            watermark_size = 4 * inch
            x = (page_width - watermark_size) / 2
            y = (page_height - watermark_size) / 2
            
            self.drawImage(self.logo_path, x, y, width=watermark_size, height=watermark_size, 
                          mask='auto', preserveAspectRatio=True)
            
            self.restoreState()
        except Exception as e:
            print(f"Error al dibujar marca de agua: {e}")

    def draw_header(self):
        """Dibuja el encabezado en cada página"""
        self.saveState()
        
        # Logo en el encabezado
        if self.logo_path:
            try:
                logo_x = letter[0] - 2.2 * inch
                logo_y = letter[1] - 1.45 * inch
                logo_width = 1.5 * inch
                logo_height = 1.5 * inch
                
                self.drawImage(
                    self.logo_path, 
                    logo_x, logo_y,
                    width=logo_width, 
                    height=logo_height,
                    mask='auto', 
                    preserveAspectRatio=True
                )
            except Exception as e:
                print(f"Error al dibujar logo en encabezado: {e}")
        
        # Texto del encabezado
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor('#718096'))
        self.drawString(1.7 * inch, letter[1] - 0.60 * inch, 
                       "INGENIERÍA & CONSTRUCCIÓN CASOVAL S.R.L.")
        
        # Línea separadora
        self.setStrokeColor(colors.HexColor('#718096'))
        self.setLineWidth(1.0)
        self.line(0.75 * inch, letter[1] - 0.70 * inch, 
                 letter[0] - 2.2 * inch, letter[1] - 0.70 * inch)
        
        self.restoreState()

    def draw_page_number(self, page_count):
        """Dibuja el número de página"""
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#718096'))
        self.drawRightString(
            letter[0] - 0.75 * inch,
            0.5 * inch,
            f"Página {self._pageNumber} de {page_count}"
        )

        self.setFont("Helvetica-Oblique", 7)
        fecha_generacion = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        self.drawString(
            0.75 * inch,
            0.35 * inch,
            f"Reporte generado el {fecha_generacion}"
        )


def generar_reporte_cliente_pdf(movimiento):
    """
    Genera un reporte PDF detallado del movimiento de cliente
    """
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.8*inch,
        bottomMargin=0.70*inch,
        title=f'Movimiento Cliente {movimiento.numero_movimiento}'
    )
    
    elementos = []
    estilos = getSampleStyleSheet()
    
    # Estilos personalizados - COLORES INVERTIDOS
    estilo_titulo = ParagraphStyle(
        'CustomTitle',
        parent=estilos['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#6b1f3d'),  # Guindo oscuro (era azul #1a365d)
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    estilo_subtitulo = ParagraphStyle(
        'CustomSubtitle',
        parent=estilos['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    estilo_normal = ParagraphStyle(
        'CustomNormal',
        parent=estilos['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_LEFT
    )
    
    # ==================== ENCABEZADO ====================
    
    tipo_movimiento = movimiento.get_tipo_display().upper()
    titulo = Paragraph(
        f'REPORTE DE MOVIMIENTO DE CLIENTE<br/>{tipo_movimiento}',
        estilo_titulo
    )
    elementos.append(titulo)
    elementos.append(Spacer(1, 0.1*inch))
    
    # Información destacada
    datos_destacados = []
    
    # Cliente
    if movimiento.cliente:
        datos_destacados.append(['CLIENTE:', f"{movimiento.cliente.codigo} - {movimiento.cliente.nombre}"])
    
    # Dependiendo del tipo, mostrar origen/destino
    if movimiento.tipo == 'ENTRADA' and movimiento.almacen_origen:
        datos_destacados.append(['DESDE ALMACÉN:', str(movimiento.almacen_origen)])
    elif movimiento.tipo == 'SALIDA' and movimiento.almacen_destino:
        datos_destacados.append(['HACIA ALMACÉN:', str(movimiento.almacen_destino)])
    elif movimiento.tipo == 'TRASLADO':
        if movimiento.cliente_origen:
            datos_destacados.append(['DESDE CLIENTE:', f"{movimiento.cliente_origen.codigo} - {movimiento.cliente_origen.nombre}"])
        if movimiento.cliente_destino:
            datos_destacados.append(['HACIA CLIENTE:', f"{movimiento.cliente_destino.codigo} - {movimiento.cliente_destino.nombre}"])
    
    # N° de Movimiento
    datos_destacados.append(['N° DE MOVIMIENTO:', movimiento.numero_movimiento])
    
    # Fecha
    datos_destacados.append(['FECHA:', movimiento.fecha.strftime('%d/%m/%Y')])
    
    tabla_destacada = Table(datos_destacados, colWidths=[1.8*inch, 4.7*inch])
    tabla_destacada.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#36454F')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2c5282')),  # Azul (era rojo #c53030)
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    elementos.append(tabla_destacada)
    elementos.append(Spacer(1, 0.15*inch))
    
    # Información básica del movimiento
    info_basica = [
        ['Tipo:', movimiento.get_tipo_display()],
    ]
    
    # Cliente y dirección
    if movimiento.cliente:
        info_basica.append(['Cliente:', f"{movimiento.cliente.codigo} - {movimiento.cliente.nombre}"])
        if movimiento.cliente.direccion:
            info_basica.append(['Dirección/Comunidad:', movimiento.cliente.direccion])
    
    # Información según tipo
    if movimiento.tipo == 'ENTRADA':
        if movimiento.almacen_origen:
            info_basica.append(['Almacén Origen:', str(movimiento.almacen_origen)])
    elif movimiento.tipo == 'SALIDA':
        if movimiento.almacen_destino:
            info_basica.append(['Almacén Destino:', str(movimiento.almacen_destino)])
    elif movimiento.tipo == 'TRASLADO':
        if movimiento.cliente_origen:
            info_basica.append(['Cliente Origen:', f"{movimiento.cliente_origen.codigo} - {movimiento.cliente_origen.nombre}"])
        if movimiento.cliente_destino:
            info_basica.append(['Cliente Destino:', f"{movimiento.cliente_destino.codigo} - {movimiento.cliente_destino.nombre}"])
    
    # Proveedor y recepcionista
    if movimiento.proveedor:
        info_basica.append(['Proveedor/Transporte:', str(movimiento.proveedor)])
    
    if movimiento.recepcionista:
        info_basica.append(['Recepcionista:', str(movimiento.recepcionista)])
    
    tabla_info = Table(info_basica, colWidths=[1.8*inch, 4.7*inch])
    tabla_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2d3748')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elementos.append(tabla_info)
    elementos.append(Spacer(1, 0.2*inch))
    
    # ==================== OBSERVACIONES ====================
    
    if movimiento.observaciones_movimiento:
        elementos.append(Paragraph('OBSERVACIONES DEL MOVIMIENTO', estilo_subtitulo))
        
        tabla_obs = Table([[movimiento.observaciones_movimiento]], colWidths=[6.5*inch])
        tabla_obs.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elementos.append(tabla_obs)
        elementos.append(Spacer(1, 0.15*inch))
    
    # ==================== DETALLE DE PRODUCTOS ====================
    
    elementos.append(Paragraph('DETALLE DE PRODUCTOS', estilo_subtitulo))
    
    datos_productos = [
        ['#', 'Código', 'Producto', 'Unidad', 'Cant. Buena', 'Cant. Dañada', 'Total', '% Dañado']
    ]
    
    detalles = movimiento.detalles.select_related('producto', 'producto__unidad_medida').all()
    
    total_cant_buena = 0
    total_cant_danada = 0
    
    for idx, detalle in enumerate(detalles, 1):
        codigo_producto = detalle.producto.codigo if detalle.producto and hasattr(detalle.producto, 'codigo') else '-'
        producto_nombre = detalle.producto.nombre if detalle.producto else '-'
        unidad = str(detalle.producto.unidad_medida) if detalle.producto else '-'
        cant_buena = float(detalle.cantidad)
        cant_danada = float(detalle.cantidad_danada)
        cant_total = cant_buena + cant_danada
        porcentaje_danado = (cant_danada / cant_total * 100) if cant_total > 0 else 0
        
        total_cant_buena += cant_buena
        total_cant_danada += cant_danada
        
        datos_productos.append([
            str(idx),
            codigo_producto,
            producto_nombre,
            unidad,
            f'{cant_buena:,.2f}',
            f'{cant_danada:,.2f}' if cant_danada > 0 else '-',
            f'{cant_total:,.2f}',
            f'{porcentaje_danado:.1f}%' if porcentaje_danado > 0 else '-'
        ])
    
    # Fila de totales
    total_general = total_cant_buena + total_cant_danada
    porcentaje_danado_total = (total_cant_danada / total_general * 100) if total_general > 0 else 0
    
    datos_productos.append([
        '',
        '',
        'TOTALES',
        '',
        f'{total_cant_buena:,.2f}',
        f'{total_cant_danada:,.2f}' if total_cant_danada > 0 else '-',
        f'{total_general:,.2f}',
        f'{porcentaje_danado_total:.1f}%' if porcentaje_danado_total > 0 else '-'
    ])
    
    tabla_productos = Table(
        datos_productos,
        colWidths=[0.3*inch, 0.8*inch, 1.9*inch, 0.7*inch, 0.9*inch, 0.9*inch, 0.8*inch, 0.7*inch]
    )
    
    estilos_tabla = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b2f52')),  # Guindo (era azul #2c5282)
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2d3748')),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#8b2f52')),  # Guindo (era azul #2c5282)
        
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#8b2f52')),  # Guindo (era azul #2c5282)
        
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    
    for i in range(1, len(datos_productos) - 1):
        if i % 2 == 0:
            estilos_tabla.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f7fafc')))
    
    tabla_productos.setStyle(TableStyle(estilos_tabla))
    elementos.append(tabla_productos)
    
    # ==================== OBSERVACIONES POR PRODUCTO ====================
    
    observaciones_productos = []
    for idx, detalle in enumerate(detalles, 1):
        if detalle.observaciones_producto:
            observaciones_productos.append(
                f'{idx}. {detalle.producto.nombre}: {detalle.observaciones_producto}'
            )
    
    if observaciones_productos:
        elementos.append(Spacer(1, 0.15*inch))
        elementos.append(Paragraph('OBSERVACIONES POR PRODUCTO', estilo_subtitulo))
        
        for obs in observaciones_productos:
            elementos.append(Paragraph(f'• {obs}', estilo_normal))
            elementos.append(Spacer(1, 0.08*inch))
    
    # ==================== COMENTARIO ADICIONAL ====================
    
    if movimiento.comentario:
        elementos.append(Spacer(1, 0.15*inch))
        elementos.append(Paragraph('COMENTARIO ADICIONAL', estilo_subtitulo))
        
        tabla_comentario = Table([[movimiento.comentario]], colWidths=[6.5*inch])
        tabla_comentario.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffaf0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elementos.append(tabla_comentario)
    
    # ==================== SECCIÓN DE FIRMAS ====================
    
    elementos.append(Spacer(1, 0.4*inch))
    
    datos_firmas = [
        ['', ''],
        ['_______________________________', '_______________________________'],
        ['FIRMA RECEPCIONISTA', 'FIRMA CLIENTE/RESPONSABLE'],
    ]
    
    tabla_firmas = Table(datos_firmas, colWidths=[3.25*inch, 3.25*inch])
    tabla_firmas.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    elementos.append(tabla_firmas)
    
    # ==================== CONSTRUIR PDF ====================
    
    doc.build(elementos, canvasmaker=NumberedCanvasCliente)
    
    buffer.seek(0)
    return buffer