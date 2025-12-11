from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import path, reverse  # ← Agregar reverse
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect  # ← Agregar HttpResponseRedirect
from django.db import models
from django.utils.html import format_html
from django.db.models import Sum
from .models import Almacen, MovimientoAlmacen, DetalleMovimientoAlmacen
from productos.models import Producto
from .utils import generar_reporte_movimiento_pdf


@admin.register(Almacen)
class AlmacenAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'direccion', 'activo', 'get_uso_estado')
    search_fields = ('nombre', 'codigo', 'direccion')
    list_filter = ('activo',)
    ordering = ('nombre',)
    list_editable = ('activo',)

    actions = ['delete_selected_almacenes']
    
    fieldsets = (
        (None, {
            'fields': ('nombre', 'codigo', 'direccion', 'activo'),
            'description': '<p style="color: #666; font-size: 13px; margin-bottom: 10px;">Los campos marcados con <strong style="color: red;">*</strong> son obligatorios.</p>'
        }),
    )
    
    def get_uso_estado(self, obj):
        """Muestra si el almacén está siendo usado en movimientos"""
        if obj.pk:
            en_uso = MovimientoAlmacen.objects.filter(
                models.Q(almacen_origen=obj) | models.Q(almacen_destino=obj)
            ).exists()
            
            if en_uso:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">⚠️ En uso</span>'
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Libre</span>'
                )
        return "-"
    get_uso_estado.short_description = _('Estado')
    
    def get_readonly_fields(self, request, obj=None):
        """Bloquea campos si el almacén está siendo usado en movimientos"""
        if obj:  # Si es edición
            # Verificar si el almacén está siendo usado
            en_uso = MovimientoAlmacen.objects.filter(
                models.Q(almacen_origen=obj) | models.Q(almacen_destino=obj)
            ).exists()
            
            if en_uso:
                # Si está en uso, solo permitir editar dirección
                return ('nombre', 'codigo', 'activo')
            else:
                # Si no está en uso, permitir editar todo
                return ()
        return ()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Agregar asterisco a campos obligatorios
        if 'nombre' in form.base_fields:
            form.base_fields['nombre'].label = '* Nombre'
        
        if 'codigo' in form.base_fields:
            form.base_fields['codigo'].label = '* Código'
            form.base_fields['codigo'].required = True
        
        return form
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        
        # Agregar mensaje informativo si está en uso
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                en_uso = MovimientoAlmacen.objects.filter(
                    models.Q(almacen_origen=obj) | models.Q(almacen_destino=obj)
                ).exists()
                
                if en_uso:
                    from django.contrib import messages
                    messages.warning(
                        request,
                        '⚠️ Este almacén está siendo usado en movimientos. Solo puede modificar la Dirección.'
                    )
        
        return super().changeform_view(request, object_id, form_url, extra_context)

 
    def response_add(self, request, obj, post_url_continue=None):
        if "_cancel" in request.POST:
            return HttpResponseRedirect(reverse('admin:almacenes_almacen_changelist'))
        return super().response_add(request, obj, post_url_continue)
    
    def response_change(self, request, obj):
        if "_cancel" in request.POST:
            return HttpResponseRedirect(reverse('admin:almacenes_almacen_changelist'))
        return super().response_change(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Impide eliminar almacén si está siendo usado en movimientos"""
        if obj:
            # Verificar si el almacén está siendo usado
            en_uso = MovimientoAlmacen.objects.filter(
                models.Q(almacen_origen=obj) | models.Q(almacen_destino=obj)
            ).exists()
            
            if en_uso:
                return False  # NO permitir eliminar
        
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        """Personalizar acciones para proteger eliminación"""
        actions = super().get_actions(request)
        
        # Eliminar la acción de eliminar por defecto
        if 'delete_selected' in actions:
            del actions['delete_selected']
        
        return actions

    @admin.action(description=_("Eliminar elementos seleccionados"))
    def delete_selected_almacenes(self, request, queryset):
        """Acción personalizada de eliminación que verifica el uso"""
        from django.contrib import messages
        
        # Verificar si algún almacén está en uso
        almacenes_en_uso = []
        almacenes_eliminables = []
        
        for almacen in queryset:
            en_uso = MovimientoAlmacen.objects.filter(
                models.Q(almacen_origen=almacen) | models.Q(almacen_destino=almacen)
            ).exists()
            
            if en_uso:
                almacenes_en_uso.append(almacen.nombre)
            else:
                almacenes_eliminables.append(almacen)
        
        # Si hay almacenes en uso, mostrar error
        if almacenes_en_uso:
            messages.error(
                request,
                f"❌ No se puede eliminar: {', '.join(almacenes_en_uso)} (están siendo usados en movimientos)"
            )
        
        # Eliminar solo los que no están en uso
        if almacenes_eliminables:
            count = len(almacenes_eliminables)
            for almacen in almacenes_eliminables:
                almacen.delete()
            messages.success(request, f"✅ Se eliminaron {count} almacén(es) correctamente.")


class DetalleMovimientoInline(admin.TabularInline):
    model = DetalleMovimientoAlmacen
    extra = 1
    min_num = 0
    fields = [
        'producto',
        'get_unidad_medida',
        'get_stock_disponible',
        'cantidad', 
        'cantidad_danada',
        'get_cantidad_total',
        'observaciones_producto'
    ]
    readonly_fields = ['get_unidad_medida', 'get_stock_disponible', 'get_cantidad_total']
    autocomplete_fields = ['producto']
    can_delete = True
    
    verbose_name = _("Producto")
    verbose_name_plural = _("Productos del movimiento")
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'observaciones_producto':
            formfield.widget.attrs['rows'] = 2
            formfield.widget.attrs['style'] = 'width: 200px; height: 50px;'
        return formfield

    def get_unidad_medida(self, obj):
        if obj and obj.producto:
            return obj.producto.unidad_medida
        return "-"
    get_unidad_medida.short_description = _('Unidad')
    
    def get_stock_disponible(self, obj):
        """Muestra el stock REAL disponible en el almacén origen (incluye movimientos de clientes)"""
        if not obj or not obj.producto:
            return "-"
        
        movimiento = obj.movimiento
        if movimiento.tipo in ['SALIDA', 'TRASLADO'] and movimiento.almacen_origen:
            from beneficiarios.models import DetalleMovimientoCliente
            from decimal import Decimal
            
            almacen = movimiento.almacen_origen
            producto = obj.producto
            
            # MOVIMIENTOS DE ALMACÉN
            entradas_almacen = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='ENTRADA',
                movimiento__almacen_destino=almacen,
                producto=producto
            ).aggregate(
                buena=Sum('cantidad'),
                danada=Sum('cantidad_danada')
            )
            
            salidas_almacen = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='SALIDA',
                movimiento__almacen_origen=almacen,
                producto=producto
            ).aggregate(
                buena=Sum('cantidad'),
                danada=Sum('cantidad_danada')
            )
            
            traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='TRASLADO',
                movimiento__almacen_destino=almacen,
                producto=producto
            ).aggregate(
                buena=Sum('cantidad'),
                danada=Sum('cantidad_danada')
            )
            
            traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='TRASLADO',
                movimiento__almacen_origen=almacen,
                producto=producto
            ).aggregate(
                buena=Sum('cantidad'),
                danada=Sum('cantidad_danada')
            )
            
            # MOVIMIENTOS DE CLIENTE
            entradas_cliente = DetalleMovimientoCliente.objects.filter(
                movimiento__tipo='ENTRADA',
                movimiento__almacen_origen=almacen,
                producto=producto
            ).aggregate(
                buena=Sum('cantidad'),
                danada=Sum('cantidad_danada')
            )
            
            salidas_cliente = DetalleMovimientoCliente.objects.filter(
                movimiento__tipo='SALIDA',
                movimiento__almacen_destino=almacen,
                producto=producto
            ).aggregate(
                buena=Sum('cantidad'),
                danada=Sum('cantidad_danada')
            )
            
            # CALCULAR STOCK REAL
            stock_bueno = (
                Decimal(str(entradas_almacen['buena'] or 0)) +
                Decimal(str(traslados_recibidos['buena'] or 0)) +
                Decimal(str(salidas_cliente['buena'] or 0)) +      # SUMA: regresan al almacén
                - Decimal(str(salidas_almacen['buena'] or 0))      # RESTA: salen del almacén
                - Decimal(str(traslados_enviados['buena'] or 0))   # RESTA: traslados enviados
                - Decimal(str(entradas_cliente['buena'] or 0))     # RESTA: salen del almacén hacia clientes
            )

            stock_danado = (
                Decimal(str(entradas_almacen['danada'] or 0)) +
                Decimal(str(traslados_recibidos['danada'] or 0)) +
                Decimal(str(salidas_cliente['danada'] or 0)) +     # SUMA: regresan al almacén
                - Decimal(str(salidas_almacen['danada'] or 0))     # RESTA
                - Decimal(str(traslados_enviados['danada'] or 0))  # RESTA
                - Decimal(str(entradas_cliente['danada'] or 0))    # RESTA
            )
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">B: {} | D: {}</span>',
                'green' if stock_bueno > 0 else 'red',
                stock_bueno,
                stock_danado
            )
        return "-"
    get_stock_disponible.short_description = _('Stock Real Disponible')

    def get_cantidad_total(self, obj):
        if not obj or not obj.id:
            return "-"
        total = obj.get_cantidad_total()
        return format_html(
            '<strong style="color: #2c5282; font-size: 14px;">{:.2f}</strong>',
            total
        )
    get_cantidad_total.short_description = _('Total')

@admin.register(MovimientoAlmacen)
class MovimientoAlmacenAdmin(admin.ModelAdmin):
    list_display = (
        'fecha',
        'numero_movimiento',
        'tipo',
        'almacen_origen',
        'almacen_destino',
        'proveedor',
        'recepcionista',
        'get_total_productos',
        'get_total_cantidad_buena',
        'get_total_cantidad_danada',
        'ver_reporte_link'
    )
    list_filter = (
        'tipo',
        'fecha',
        'almacen_origen',
        'almacen_destino',
        'proveedor',
        'recepcionista'
    )
    search_fields = (
        'numero_movimiento',
        'comentario',
        'observaciones_movimiento',
        'detalles__producto__nombre',
        'proveedor__nombre',
        'recepcionista__nombre'
    )
    ordering = ('-fecha', '-numero_movimiento', 'tipo')
    
    readonly_fields = ('preview_numero_movimiento',)
    autocomplete_fields = ['proveedor', 'recepcionista']
    
    def preview_numero_movimiento(self, obj):
        if obj and obj.numero_movimiento:
            return obj.numero_movimiento
        return '-'
    preview_numero_movimiento.short_description = _('N° de movimiento')
    
    def ver_reporte_link(self, obj):
        """Muestra un botón para generar el reporte PDF"""
        if obj.pk:
            url = f'/admin/almacenes/movimientoalmacen/{obj.pk}/reporte-pdf/'
            return format_html(
                '<a class="button" href="{}" target="_blank" style="background-color: #417690; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px;">📄 PDF</a>',
                url
            )
        return "-"
    ver_reporte_link.short_description = _('Reporte')
    
    inlines = [DetalleMovimientoInline]
        
    fieldsets = (
        (None, {
            'fields': ('fecha', 'preview_numero_movimiento'),
            'description': '<p style="color: #666; font-size: 13px; margin-bottom: 10px;">Los campos marcados con <strong style="color: red;">*</strong> son obligatorios.</p>'
        }),
        (_('Tipo de Movimiento'), {
            'fields': ('tipo',)
        }),
        (_('Almacenes'), {
            'fields': ('almacen_origen', 'almacen_destino'),
            'description': _('Seleccione los almacenes según el tipo de movimiento')
        }),
        (_('Proveedor y Recepcionista'), {
            'fields': ('proveedor', 'recepcionista'),
            'description': _('Información adicional del movimiento')
        }),
        (_('Observaciones del Movimiento'), {
            'fields': ('observaciones_movimiento',)
        }),
        (_('Comentario Adicional'), {
            'fields': ('comentario',),
            'classes': ('collapse',)
        }),
    )
    
    # ← NUEVO MÉTODO: Personalizar formulario
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Agregar asteriscos a campos obligatorios
        if 'fecha' in form.base_fields:
            form.base_fields['fecha'].label = '* Fecha'
        
        if 'tipo' in form.base_fields:
            form.base_fields['tipo'].label = '* Tipo de Movimiento'
        
        if 'almacen_origen' in form.base_fields:
            form.base_fields['almacen_origen'].label = '* Almacén Origen'
        
        if 'almacen_destino' in form.base_fields:
            form.base_fields['almacen_destino'].label = '* Almacén Destino'
        
        # Hacer obligatorios Proveedor y Recepcionista
        if 'proveedor' in form.base_fields:
            form.base_fields['proveedor'].required = True
            form.base_fields['proveedor'].label = '* Proveedor/Transp.'
        
        if 'recepcionista' in form.base_fields:
            form.base_fields['recepcionista'].required = True
            form.base_fields['recepcionista'].label = '* Recepcionista'
        
        # Configurar campos de cantidad para que incrementen de 1 en 1
        return form

    def get_readonly_fields(self, request, obj=None):
        """Bloquea campos críticos en modo edición para evitar inconsistencias"""
        if obj:  # Si es edición (objeto ya existe)
            return ('preview_numero_movimiento', 'tipo', 'almacen_origen', 'almacen_destino')
        return ('preview_numero_movimiento',)
    
    # ← NUEVO MÉTODO: Agregar estilos CSS para los campos numéricos
    class Media:
        css = {
            'all': ('admin/css/movimiento_almacen_custom.css',)
        }
        js = ('admin/js/movimiento_almacen_custom.js',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ajax/get-next-number/', 
                 self.admin_site.admin_view(self.get_next_number_view),
                 name='almacenes_movimientoalmacen_next_number'),
            path('ajax/get-producto-info/<int:producto_id>/',
                 self.admin_site.admin_view(self.get_producto_info_view),
                 name='almacenes_producto_info'),
            path('ajax/get-stock/<int:almacen_id>/<int:producto_id>/',
                 self.admin_site.admin_view(self.get_stock_view),
                 name='almacenes_get_stock'),
            path('<int:movimiento_id>/reporte-pdf/',
                 self.admin_site.admin_view(self.reporte_pdf_view),
                 name='almacenes_movimiento_reporte_pdf'),
        ]
        return custom_urls + urls
    
    def reporte_pdf_view(self, request, movimiento_id):
        """Vista para generar el reporte PDF del movimiento"""
        from django.shortcuts import get_object_or_404
        
        movimiento = get_object_or_404(
            MovimientoAlmacen.objects.prefetch_related(
                'detalles__producto__unidad_medida'
            ).select_related(
                'almacen_origen',
                'almacen_destino',
                'proveedor',
                'recepcionista'
            ),
            pk=movimiento_id
        )
        
        # Generar el PDF
        pdf_buffer = generar_reporte_movimiento_pdf(movimiento)
        
        # Preparar la respuesta HTTP
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        filename = f'movimiento_{movimiento.numero_movimiento}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
    
    def get_next_number_view(self, request):
        tipo = request.GET.get('tipo', '')
        almacen_id = request.GET.get('almacen_id', '')
        
        if not tipo:
            return JsonResponse({'error': 'Tipo no especificado'}, status=400)
        
        if not almacen_id:
            return JsonResponse({'error': 'Almacén no especificado'}, status=400)
        
        try:
            almacen = Almacen.objects.get(id=almacen_id)
        except Almacen.DoesNotExist:
            return JsonResponse({'error': 'Almacén no encontrado'}, status=404)
        
        # Buscar el último movimiento del MISMO TIPO y MISMO ALMACÉN
        filtro_query = {'tipo': tipo}
        
        if tipo == 'ENTRADA':
            filtro_query['almacen_destino'] = almacen
        elif tipo == 'SALIDA':
            filtro_query['almacen_origen'] = almacen
        elif tipo == 'TRASLADO':
            filtro_query['almacen_origen'] = almacen
        
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
        }.get(tipo, 'MOV')
        
        # Formato: CODIGO_ALMACEN-PREFIJO-0001
        codigo_almacen = almacen.codigo or almacen.nombre[:3].upper()
        numero_movimiento = f"{codigo_almacen}/{prefijo}-{nuevo_numero:04d}"
    
        return JsonResponse({'numero_movimiento': numero_movimiento})
    
    def get_producto_info_view(self, request, producto_id):
        try:
            producto = Producto.objects.select_related('unidad_medida').get(id=producto_id)
            return JsonResponse({
                'unidad': str(producto.unidad_medida),
                'nombre': producto.nombre
            })
        except Producto.DoesNotExist:
            return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    
    def get_stock_view(self, request, almacen_id, producto_id):
        """Obtiene el stock REAL de un producto en un almacén específico (incluye movimientos de clientes)"""
        try:
            almacen = Almacen.objects.get(id=almacen_id)
            producto = Producto.objects.get(id=producto_id)
            
            # Importar modelo de clientes
            from beneficiarios.models import DetalleMovimientoCliente
            from decimal import Decimal
            
            # ====== MOVIMIENTOS DE ALMACÉN ======
            
            # 1. ENTRADAS de almacén
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
            
            # 2. SALIDAS de almacén
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
            
            # 3. TRASLADOS RECIBIDOS
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
            
            # 4. TRASLADOS ENVIADOS
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
            
            # ====== CÁLCULO FINAL DEL STOCK REAL ======

            stock_bueno = (
                entradas_alm_buena +           # SUMA: entradas de almacén
                traslados_rec_buena +          # SUMA: traslados recibidos
                salidas_cli_buena +            # SUMA: salidas de cliente (regresan al almacén)
                - salidas_alm_buena            # RESTA: salidas de almacén
                - traslados_env_buena          # RESTA: traslados enviados
                - entradas_cli_buena           # RESTA: entradas de cliente (salen del almacén)
            )

            stock_danado = (
                entradas_alm_danada +          # SUMA: entradas de almacén
                traslados_rec_danada +         # SUMA: traslados recibidos
                salidas_cli_danada +           # SUMA: salidas de cliente (regresan al almacén)
                - salidas_alm_danada           # RESTA: salidas de almacén
                - traslados_env_danada         # RESTA: traslados enviados
                - entradas_cli_danada          # RESTA: entradas de cliente (salen del almacén)
            )
            
            return JsonResponse({
                'stock_bueno': float(stock_bueno),
                'stock_danado': float(stock_danado),
                'stock_total': float(stock_bueno + stock_danado),
                'unidad': str(producto.unidad_medida) if producto.unidad_medida else 'UND'
            })
            
        except (Almacen.DoesNotExist, Producto.DoesNotExist):
            return JsonResponse({'error': 'Almacén o producto no encontrado'}, status=404)
        except Exception as e:
            import traceback
            return JsonResponse({
                'error': f'Error: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
    
    def get_total_productos(self, obj):
        return obj.get_total_productos()
    get_total_productos.short_description = _('Total Productos')
    
    def get_total_cantidad_buena(self, obj):
        total = obj.get_total_cantidad_buena()
        return f"{total:,.2f}"
    get_total_cantidad_buena.short_description = _('Cant. Buena')
    
    def get_total_cantidad_danada(self, obj):
        total = obj.get_total_cantidad_danada()
        if total > 0:
            return f"{total:,.2f}"
        return "-"
    get_total_cantidad_danada.short_description = _('Cant. Dañada')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            'detalles',
            'detalles__producto',
            'detalles__producto__unidad_medida'
        ).select_related(
            'almacen_origen',
            'almacen_destino',
            'proveedor',
            'recepcionista'
        )
    
    def response_add(self, request, obj, post_url_continue=None):
        if "_cancel" in request.POST:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(reverse('admin:almacenes_movimientoalmacen_changelist'))
        return super().response_add(request, obj, post_url_continue)
    
    def response_change(self, request, obj):
        if "_cancel" in request.POST:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(reverse('admin:almacenes_movimientoalmacen_changelist'))
        return super().response_change(request, obj)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().changeform_view(request, object_id, form_url, extra_context)

    def render_change_form(self, request, context, **kwargs):
        response = super().render_change_form(request, context, **kwargs)
        
        script = """
        <style>
        /* Hacer que los inputs numéricos incrementen de 1 en 1 */
        input[name*="cantidad"],
        input[name*="cantidad_danada"] {
            /* Estos estilos aseguran que el step sea 1 */
        }

        /* ← AGREGAR TODO ESTE BLOQUE AQUÍ ↓ */
        /* Cambiar checkbox de eliminar por X roja */
        .inline-related td.delete input[type="checkbox"] {
            position: absolute;
            opacity: 0;
            width: 0;
            height: 0;
        }

        /* Contenedor de la celda eliminar */
        .inline-related td.delete {
            position: relative;
            text-align: center !important;
            vertical-align: middle !important;
            width: 80px;
            padding: 10px !important;
        }

        /* Forzar step=1 en todos los campos numéricos - MANTENER FLECHITAS VISIBLES */
        input[type="number"][name*="cantidad"],
        input[type="number"][name*="cantidad_danada"] {
            /* No ocultar las flechitas, solo asegurar step=1 */
        }

        </style>
        <script>
        (function() {
            'use strict';
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', inicializar);
            } else {
                inicializar();
            }
            
            function inicializar() {
                var $ = django.jQuery;
                var campoTipo = $('#id_tipo');
                var previewNumero = $('.field-preview_numero_movimiento .readonly');
                var campoAlmacenOrigen = $('#id_almacen_origen');
                
                if (campoTipo.length === 0) return;
                
                // ... todas tus funciones existentes ...
                
                // ← AGREGAR ESTA FUNCIÓN AQUÍ (después de las otras)
                function crearBotonesEliminarDirecto() {
                    $('.inline-related').each(function() {
                        var $row = $(this);
                        var $deleteCell = $row.find('td.delete');
                        
                        if ($deleteCell.length === 0) return;
                        if ($deleteCell.find('.btn-delete-custom').length > 0) return;
                        
                        var $checkbox = $deleteCell.find('input[type="checkbox"], input[name*="DELETE"]');
                        if ($checkbox.length === 0) return;
                        
                        $checkbox.hide();
                        
                        var isChecked = $checkbox.is(':checked');
                        var $btn = $('<div class="btn-delete-custom"></div>').css({
                            'display': 'inline-block',
                            'width': '35px',
                            'height': '35px',
                            'background-color': isChecked ? '#28a745' : '#dc3545',
                            'color': 'white',
                            'border-radius': '50%',
                            'line-height': '35px',
                            'text-align': 'center',
                            'cursor': 'pointer',
                            'font-weight': 'bold',
                            'font-size': '20px',
                            'transition': 'all 0.3s ease'
                        }).text(isChecked ? '✓' : '×');
                        
                        $btn.on('click', function() {
                            var currentChecked = $checkbox.is(':checked');
                            $checkbox.prop('checked', !currentChecked);
                            
                            if (!currentChecked) {
                                $btn.css('background-color', '#28a745').text('✓');
                                $row.css({
                                    'opacity': '0.6',
                                    'background-color': '#ffebee'
                                });
                            } else {
                                $btn.css('background-color', '#dc3545').text('×');
                                $row.css({
                                    'opacity': '1',
                                    'background-color': ''
                                });
                            }
                        });
                        
                        $btn.on('mouseenter', function() {
                            if (!$checkbox.is(':checked')) {
                                $(this).css({
                                    'background-color': '#c82333',
                                    'transform': 'scale(1.1)'
                                });
                            }
                        }).on('mouseleave', function() {
                            if (!$checkbox.is(':checked')) {
                                $(this).css({
                                    'background-color': '#dc3545',
                                    'transform': 'scale(1)'
                                });
                            }
                        });
                        
                        $deleteCell.append($btn);
                    });
                }

                // ← VERSIÓN MÁS SIMPLE: Permitir decimales, redondear al final
                function configurarCamposNumericos() {
                    $('input[name*="cantidad"], input[name*="cantidad_danada"]').each(function() {
                        var $input = $(this);
                        
                        // FORZAR los atributos incluso si ya existen
                        $input.prop('step', '1');
                        $input.prop('min', '0');
                        $input.prop('type', 'number');
                        
                        // También establecer con attr por compatibilidad
                        $input.attr('step', '1');
                        $input.attr('min', '0');
                    });
                }

                // ← NUEVO: Forzar actualización de unidades y totales en filas existentes
                function actualizarFilasExistentes() {
                    $('.inline-related.has_original').each(function() {
                        var $row = $(this);
                        var $productoSelect = $row.find('[id$="-producto"]');
                        var productoId = $productoSelect.val();
                        
                        if (!productoId) return;
                        
                        var unidadCell = $row.find('td.field-get_unidad_medida');
                        var stockCell = $row.find('td.field-get_stock_disponible');
                        
                        // Actualizar unidad de medida
                        $.ajax({
                            url: '/admin/almacenes/movimientoalmacen/ajax/get-producto-info/' + productoId + '/',
                            method: 'GET',
                            success: function(data) {
                                if (data.unidad) {
                                    unidadCell.text(data.unidad);
                                }
                            }
                        });
                        
                        // Actualizar stock si aplica
                        var tipoMovimiento = $('#id_tipo').val();
                        var almacenOrigenId = $('#id_almacen_origen').val();
                        
                        if ((tipoMovimiento === 'SALIDA' || tipoMovimiento === 'TRASLADO') && almacenOrigenId) {
                            $.ajax({
                                url: '/admin/almacenes/movimientoalmacen/ajax/get-stock/' + 
                                    almacenOrigenId + '/' + productoId + '/',
                                method: 'GET',
                                success: function(data) {
                                    var color = data.stock_bueno > 0 ? 'green' : 'red';
                                    stockCell.html(
                                        '<span style="color: ' + color + '; font-weight: bold;">' +
                                        'B: ' + data.stock_bueno + ' | D: ' + data.stock_danado +
                                        '</span>'
                                    );
                                }
                            });
                        }
                    });
                    
                    // Actualizar totales
                    actualizarTotales();
                }
                
                // ← NUEVO: Actualizar totales dinámicamente
                function actualizarTotales() {
                    $('input[name*="cantidad"]').each(function() {
                        var inputCantidad = $(this);
                        if (inputCantidad.attr('name').indexOf('cantidad_danada') !== -1) return;
                        
                        var row = inputCantidad.closest('tr');
                        var nombreBase = inputCantidad.attr('name').replace('-cantidad', '');
                        var inputDanada = $('input[name="' + nombreBase + '-cantidad_danada"]');
                        var cantidadBuena = parseFloat(inputCantidad.val()) || 0;
                        var cantidadDanada = parseFloat(inputDanada.val()) || 0;
                        var total = cantidadBuena + cantidadDanada;
                        
                        var totalCell = row.find('td.field-get_cantidad_total');
                        if (totalCell.length > 0) {
                            totalCell.html('<strong style="color: #2c5282; font-size: 14px;">' + total.toFixed(2) + '</strong>');
                        }
                    });
                }
                
                function actualizarCamposAlmacen() {
                    var tipoMovimiento = campoTipo.val();
                    var fieldOrigen = $('.field-almacen_origen');
                    var fieldDestino = $('.field-almacen_destino');
                    var selectOrigen = $('#id_almacen_origen');
                    var selectDestino = $('#id_almacen_destino');
                    
                    $('.help-almacen').remove();
                    fieldOrigen.show();
                    fieldDestino.show();
                    selectOrigen.prop('disabled', false).prop('required', false);
                    selectDestino.prop('disabled', false).prop('required', false);
                    
                    if (tipoMovimiento === 'ENTRADA') {
                        fieldOrigen.hide();
                        selectOrigen.val('').prop('disabled', true);
                        selectDestino.prop('required', true);
                    } else if (tipoMovimiento === 'SALIDA') {
                        fieldDestino.hide();
                        selectDestino.val('').prop('disabled', true);
                        selectOrigen.prop('required', true);
                    } else if (tipoMovimiento === 'TRASLADO') {
                        selectOrigen.prop('required', true);
                        selectDestino.prop('required', true);
                    }
                    
                    actualizarStockDisponible();
                }
                
                function actualizarNumeroMovimiento() {
                    var tipoMovimiento = campoTipo.val();
                    var almacenId = null;
                    
                    // Determinar qué almacén usar según el tipo
                    if (tipoMovimiento === 'ENTRADA') {
                        almacenId = $('#id_almacen_destino').val();
                    } else if (tipoMovimiento === 'SALIDA') {
                        almacenId = $('#id_almacen_origen').val();
                    } else if (tipoMovimiento === 'TRASLADO') {
                        almacenId = campoAlmacenOrigen.val();
                    }
                    
                    if (!tipoMovimiento || !almacenId) {
                        previewNumero.text('-');
                        return;
                    }
                    
                    $.ajax({
                        url: '/admin/almacenes/movimientoalmacen/ajax/get-next-number/',
                        method: 'GET',
                        data: { 
                            tipo: tipoMovimiento,
                            almacen_id: almacenId  // ← NUEVO PARÁMETRO
                        },
                        success: function(data) {
                            if (data.numero_movimiento) {
                                previewNumero.text(data.numero_movimiento);
                            }
                        }
                    });
                }
                
                function actualizarStockDisponible() {
                    var tipoMovimiento = campoTipo.val();
                    var almacenOrigenId = campoAlmacenOrigen.val();
                    
                    if (!tipoMovimiento || !almacenOrigenId) return;
                    if (tipoMovimiento === 'ENTRADA') return;
                    
                    $('[id^="id_detalles-"][id$="-producto"]').each(function() {
                        var $select = $(this);
                        var productoId = $select.val();
                        var row = $select.closest('tr');
                        var stockCell = row.find('td.field-get_stock_disponible');
                        
                        if (!productoId) {
                            stockCell.html('-');
                            return;
                        }
                        
                        $.ajax({
                            url: '/admin/almacenes/movimientoalmacen/ajax/get-stock/' + 
                                 almacenOrigenId + '/' + productoId + '/',
                            method: 'GET',
                            success: function(data) {
                                var color = data.stock_bueno > 0 ? 'green' : 'red';
                                stockCell.html(
                                    '<span style="color: ' + color + '; font-weight: bold;">' +
                                    'B: ' + data.stock_bueno + ' | D: ' + data.stock_danado +
                                    '</span>'
                                );
                            },
                            error: function() {
                                stockCell.html('-');
                            }
                        });
                    });
                }

                function validarStockEnTiempoReal() {
                    $('input[name*="cantidad"]').each(function() {
                        var $inputCantidad = $(this);
                        if ($inputCantidad.attr('name').indexOf('cantidad_danada') !== -1) return;
                        
                        var row = $inputCantidad.closest('tr');
                        var nombreBase = $inputCantidad.attr('name').replace('-cantidad', '');
                        var $inputDanada = $('input[name="' + nombreBase + '-cantidad_danada"]');
                        var $productoSelect = row.find('[id$="-producto"]');
                        var stockCell = row.find('td.field-get_stock_disponible');
                        
                        var productoId = $productoSelect.val();
                        var tipoMovimiento = $('#id_tipo').val();
                        var almacenOrigenId = $('#id_almacen_origen').val();
                        
                        if (!productoId || !almacenOrigenId) return;
                        if (tipoMovimiento !== 'SALIDA' && tipoMovimiento !== 'TRASLADO') return;
                        
                        // Obtener el stock y comparar
                        $.ajax({
                            url: '/admin/almacenes/movimientoalmacen/ajax/get-stock/' + 
                                almacenOrigenId + '/' + productoId + '/',
                            method: 'GET',
                            success: function(data) {
                                var cantidadBuena = parseFloat($inputCantidad.val()) || 0;
                                var cantidadDanada = parseFloat($inputDanada.val()) || 0;
                                
                                var colorBueno = 'green';
                                var colorDanado = 'green';
                                var advertencia = '';
                                
                                // Validar cantidad buena
                                if (cantidadBuena > data.stock_bueno) {
                                    colorBueno = 'red';
                                    advertencia += 'ADVERTENCIA: Stock bueno insuficiente! ';
                                    $inputCantidad.css({
                                        'border': '2px solid red',
                                        'background-color': '#ffebee'
                                    });
                                } else {
                                    $inputCantidad.css({
                                        'border': '',
                                        'background-color': ''
                                    });
                                }
                                
                                // Validar cantidad dañada
                                if (cantidadDanada > data.stock_danado) {
                                    colorDanado = 'red';
                                    advertencia += 'ADVERTENCIA: Stock dañado insuficiente! ';
                                    $inputDanada.css({
                                        'border': '2px solid red',
                                        'background-color': '#ffebee'
                                    });
                                } else {
                                    $inputDanada.css({
                                        'border': '',
                                        'background-color': ''
                                    });
                                }
                                
                                // Actualizar celda de stock con colores
                                var htmlStock = '<span style="font-weight: bold;">';
                                htmlStock += '<span style="color: ' + colorBueno + ';">B: ' + data.stock_bueno + '</span>';
                                htmlStock += ' | ';
                                htmlStock += '<span style="color: ' + colorDanado + ';">D: ' + data.stock_danado + '</span>';
                                htmlStock += '</span>';
                                
                                if (advertencia) {
                                    htmlStock += '<br><span style="color: red; font-size: 11px;">' + advertencia + '</span>';
                                }
                                
                                stockCell.html(htmlStock);
                            }
                        });
                    });
                }

                // Llamar a esta función cuando cambien las cantidades
                $(document).on('input change', 'input[name*="cantidad"], input[name*="cantidad_danada"]', function() {
                    configurarCamposNumericos();
                    actualizarTotales();
                    validarStockEnTiempoReal(); // ← AGREGAR ESTA LÍNEA
                });
                
                function configurarProductoUnidad() {
                    var selectores = $('[id^="id_detalles-"][id$="-producto"]');
                    selectores.each(function() {
                        var $select = $(this);
                        // Remover eventos anteriores
                        $select.off('change.unidad');
                        
                        $select.on('change.unidad', function() {
                            var productoId = $(this).val();
                            var row = $(this).closest('tr');
                            var unidadCell = row.find('td.field-get_unidad_medida');
                            var stockCell = row.find('td.field-get_stock_disponible');
                            
                            if (!productoId) {
                                unidadCell.text('-');
                                stockCell.html('-');
                                return;
                            }
                            
                            // Actualizar unidad de medida
                            $.ajax({
                                url: '/admin/almacenes/movimientoalmacen/ajax/get-producto-info/' + productoId + '/',
                                method: 'GET',
                                success: function(data) {
                                    if (data.unidad) {
                                        // Actualizar el texto directamente
                                        unidadCell.text(data.unidad);
                                        
                                        // Forzar re-renderizado
                                        unidadCell.hide().show(0);
                                    }
                                },
                                error: function() {
                                    unidadCell.text('-');
                                }
                            });
                            
                            // Actualizar stock si corresponde
                            var tipoMovimiento = campoTipo.val();
                            var almacenOrigenId = campoAlmacenOrigen.val();
                            
                            if ((tipoMovimiento === 'SALIDA' || tipoMovimiento === 'TRASLADO') && almacenOrigenId) {
                                $.ajax({
                                    url: '/admin/almacenes/movimientoalmacen/ajax/get-stock/' + 
                                        almacenOrigenId + '/' + productoId + '/',
                                    method: 'GET',
                                    success: function(data) {
                                        var color = data.stock_bueno > 0 ? 'green' : 'red';
                                        stockCell.html(
                                            '<span style="color: ' + color + '; font-weight: bold;">' +
                                            'B: ' + data.stock_bueno + ' | D: ' + data.stock_danado +
                                            '</span>'
                                        );
                                    },
                                    error: function() {
                                        stockCell.html('-');
                                    }
                                });
                            } else {
                                stockCell.html('-');
                            }
                        });
                    });
                }
                
                // INICIALIZACIÓN
                actualizarCamposAlmacen();
                actualizarNumeroMovimiento();
                configurarProductoUnidad();
                configurarCamposNumericos();
                actualizarTotales();
                actualizarFilasExistentes();  // ← AGREGAR

                // Crear botones de eliminar varias veces para asegurar
                crearBotonesEliminarDirecto();
                setTimeout(crearBotonesEliminarDirecto, 100);
                setTimeout(crearBotonesEliminarDirecto, 300);
                setTimeout(crearBotonesEliminarDirecto, 500);
                setTimeout(crearBotonesEliminarDirecto, 1000);

                // ← AGREGAR: Forzar actualización múltiple en edición
                setTimeout(function() {
                    configurarCamposNumericos();
                    actualizarFilasExistentes();
                }, 200);

                setTimeout(function() {
                    configurarCamposNumericos();
                    actualizarFilasExistentes();
                }, 500);

                setTimeout(function() {
                    configurarCamposNumericos();
                    actualizarFilasExistentes();
                }, 1000);

                campoTipo.on('change', function() {
                    actualizarCamposAlmacen();
                    actualizarNumeroMovimiento();  // ← Ya existe
                });

                // ← AGREGAR ESTOS NUEVOS EVENTOS
                $('#id_almacen_destino').on('change', function() {
                    if (campoTipo.val() === 'ENTRADA') {
                        actualizarNumeroMovimiento();
                    }
                });

                campoAlmacenOrigen.on('change', function() {
                    actualizarStockDisponible();
                    actualizarFilasExistentes();
                    // ← AGREGAR: Actualizar número si es SALIDA o TRASLADO
                    if (campoTipo.val() === 'SALIDA' || campoTipo.val() === 'TRASLADO') {
                        actualizarNumeroMovimiento();
                    }
                });

                campoAlmacenOrigen.on('change', function() {
                    actualizarStockDisponible();
                });
                
                // ← NUEVO: Escuchar cambios en campos de cantidad
                $(document).on('input change', 'input[name*="cantidad"], input[name*="cantidad_danada"]', function() {
                    configurarCamposNumericos();
                    actualizarTotales();
                });
                
                // Observer para nuevas filas
                var observerTarget = document.querySelector('.inline-group');
                if (observerTarget && typeof MutationObserver !== 'undefined') {
                    var observer = new MutationObserver(function(mutations) {
                        setTimeout(function() {
                            configurarProductoUnidad();
                            configurarCamposNumericos();  // ← Ejecutar primero
                            actualizarTotales();
                            crearBotonesEliminarDirecto();
                            actualizarFilasExistentes();  // ← AGREGAR
                        }, 100);
                    });
                    observer.observe(observerTarget, { childList: true, subtree: true });
                }
            }

         })();
        </script>
        """
        
        response.render()
        response.content = response.content.decode('utf-8').replace('</body>', script + '</body>').encode('utf-8')
        return response


@admin.register(DetalleMovimientoAlmacen)
class DetalleMovimientoAdmin(admin.ModelAdmin):
    list_display = (
        'get_fecha',
        'get_numero_movimiento',
        'get_tipo_movimiento',
        'producto',
        'get_unidad_medida',
        'cantidad',
        'cantidad_danada',
        'get_cantidad_total',
        'get_porcentaje_danado'
    )
    list_filter = ('movimiento__tipo', 'movimiento__fecha', 'producto')
    search_fields = ('producto__nombre', 'movimiento__numero_movimiento', 'observaciones_producto')
    ordering = ('-movimiento__fecha', '-movimiento__numero_movimiento', 'producto__nombre')
    autocomplete_fields = ['producto']
    readonly_fields = ('get_cantidad_total', 'get_porcentaje_danado', 'get_unidad_medida')
    
    fieldsets = (
        (_('Información del Movimiento'), {'fields': ('movimiento',)}),
        (_('Producto'), {'fields': ('producto', 'get_unidad_medida')}),
        (_('Cantidades'), {'fields': (('cantidad', 'cantidad_danada'), ('get_cantidad_total', 'get_porcentaje_danado'))}),
        (_('Observaciones'), {'fields': ('observaciones_producto',), 'classes': ('collapse',)}),
    )
    
    def get_numero_movimiento(self, obj):
        return obj.movimiento.numero_movimiento
    get_numero_movimiento.short_description = _('N° Movimiento')
    
    def get_tipo_movimiento(self, obj):
        return obj.movimiento.get_tipo_display()
    get_tipo_movimiento.short_description = _('Tipo')
    
    def get_fecha(self, obj):
        return obj.movimiento.fecha.strftime('%d/%m/%Y %H:%M')
    get_fecha.short_description = _('Fecha')
    
    def get_unidad_medida(self, obj):
        return obj.producto.unidad_medida if obj.producto else "-"
    get_unidad_medida.short_description = _('Unidad')
    
    def get_cantidad_total(self, obj):
        return f"{obj.get_cantidad_total():,.2f}"
    get_cantidad_total.short_description = _('Total')
    
    def get_porcentaje_danado(self, obj):
        porcentaje = obj.get_porcentaje_danado()
        return f"{porcentaje:.2f}%" if porcentaje > 0 else "-"
    get_porcentaje_danado.short_description = _('% Dañado')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'movimiento', 
            'movimiento__almacen_origen', 
            'movimiento__almacen_destino',
            'movimiento__proveedor',
            'movimiento__recepcionista',
            'producto', 
            'producto__unidad_medida'
        )

    def response_add(self, request, obj, post_url_continue=None):
        if "_cancel" in request.POST:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(reverse('admin:almacenes_detallemovimientoalmacen_changelist'))
        return super().response_add(request, obj, post_url_continue)
    
    def response_change(self, request, obj):
        if "_cancel" in request.POST:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(reverse('admin:almacenes_detallemovimientoalmacen_changelist'))
        return super().response_change(request, obj)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().changeform_view(request, object_id, form_url, extra_context)