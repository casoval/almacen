from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.db import models
from django.utils.html import format_html
from django.db.models import Sum
from django import forms
from decimal import Decimal
from .models import Cliente, MovimientoCliente, DetalleMovimientoCliente
from .utils_cliente import generar_reporte_cliente_pdf

class DetalleMovimientoClienteForm(forms.ModelForm):
    """Form personalizado para forzar cantidades enteras"""
    cantidad = forms.DecimalField(
        label=_('Cant. Buena'),
        required=True,
        widget=forms.NumberInput(attrs={'step': '1'})
    )
    cantidad_danada = forms.DecimalField(
        label=_('Cant. Dañada'),
        required=False,
        widget=forms.NumberInput(attrs={'step': '1'})
    )
    
    # --- CORRECCIÓN DEL ERROR ---
    # Estos métodos aseguran que si el campo está vacío, se envíe un 0 
    # en lugar de None, evitando el error de comparación en models.py
    def clean_cantidad(self):
        data = self.cleaned_data.get('cantidad')
        return data if data is not None else Decimal('0')

    def clean_cantidad_danada(self):
        data = self.cleaned_data.get('cantidad_danada')
        return data if data is not None else Decimal('0')
    # ----------------------------

    class Meta:
        model = DetalleMovimientoCliente
        fields = '__all__'


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'direccion', 'telefono', 'activo', 'get_uso_estado')
    search_fields = ('codigo', 'nombre', 'direccion')
    list_filter = (
        'activo',
        'direccion',
    )
    ordering = ('codigo',)
    list_editable = ('activo',)
    
    fieldsets = (
        (_('Información del Cliente'), {
            'fields': ('codigo', 'nombre', 'direccion', 'telefono', 'activo'),
            'description': '<p style="color: #666; font-size: 13px; margin-bottom: 10px;">Los campos marcados con <strong style="color: red;">*</strong> son obligatorios.</p>'
        }),
        (_('Observaciones'), {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )
    
    def get_uso_estado(self, obj):
        """Muestra si el cliente está siendo usado en movimientos"""
        if obj.pk:
            en_uso = MovimientoCliente.objects.filter(
                models.Q(cliente=obj) | 
                models.Q(cliente_origen=obj) | 
                models.Q(cliente_destino=obj)
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
        """Bloquea campos si el cliente está siendo usado en movimientos"""
        if obj:  # Si es edición
            # Verificar si el cliente está siendo usado
            en_uso = MovimientoCliente.objects.filter(
                models.Q(cliente=obj) | 
                models.Q(cliente_origen=obj) | 
                models.Q(cliente_destino=obj)
            ).exists()
            
            if en_uso:
                # ✅ CAMBIO: Si está en uso, permitir editar nombre, dirección Y teléfono
                return ('codigo', 'activo')
            else:
                # Si no está en uso, solo bloquear código
                return ('codigo',)
        return ()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Agregar asterisco a campos obligatorios
        if 'codigo' in form.base_fields:
            form.base_fields['codigo'].label = '* Código'
        
        if 'nombre' in form.base_fields:
            form.base_fields['nombre'].label = '* Nombre'
        
        if 'direccion' in form.base_fields:
            form.base_fields['direccion'].label = '* Dirección/Comunidad'
        
        return form
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        
        # Agregar mensaje informativo si está en uso
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                en_uso = MovimientoCliente.objects.filter(
                    models.Q(cliente=obj) | 
                    models.Q(cliente_origen=obj) | 
                    models.Q(cliente_destino=obj)
                ).exists()
                
                if en_uso:
                    from django.contrib import messages
                    messages.warning(
                        request,
                        # ✅ CAMBIO: Actualizar mensaje para incluir teléfono y observaciones
                        '⚠️ Este cliente está siendo usado en movimientos. Solo puede modificar Nombre, Dirección, Teléfono y Observaciones.'
                    )
        
        return super().changeform_view(request, object_id, form_url, extra_context)

    def has_delete_permission(self, request, obj=None):
        """Impide eliminar cliente si está siendo usado en movimientos"""
        if obj:
            # Verificar si el cliente está siendo usado
            en_uso = MovimientoCliente.objects.filter(
                models.Q(cliente=obj) | 
                models.Q(cliente_origen=obj) | 
                models.Q(cliente_destino=obj)
            ).exists()
            
            if en_uso:
                return False  # NO permitir eliminar
        
        return super().has_delete_permission(request, obj)
    
    def response_add(self, request, obj, post_url_continue=None):
        if "_cancel" in request.POST:
            return HttpResponseRedirect(reverse('admin:beneficiarios_cliente_changelist'))
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_cancel" in request.POST:
            return HttpResponseRedirect(reverse('admin:beneficiarios_cliente_changelist'))
        return super().response_change(request, obj)


class DetalleMovimientoInline(admin.TabularInline):
    model = DetalleMovimientoCliente
    form = DetalleMovimientoClienteForm
    extra = 1
    min_num = 0
    max_num = None
    can_delete = True

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
        """Muestra el stock REAL disponible en el almacén según el tipo de movimiento"""
        if not obj or not obj.producto:
            return "-"
        
        movimiento = obj.movimiento
        producto = obj.producto
        almacen = None
        
        if movimiento.tipo == 'ENTRADA' and movimiento.almacen_origen:
            almacen = movimiento.almacen_origen
        elif movimiento.tipo == 'SALIDA' and movimiento.almacen_destino:
            almacen = movimiento.almacen_destino
        else:
            return "-"
        
        if not almacen:
            return "-"
        
        try:
            from almacenes.models import DetalleMovimientoAlmacen
            
            entradas_almacen = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='ENTRADA',
                movimiento__almacen_destino=almacen,
                producto=producto
            ).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
            
            salidas_almacen = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='SALIDA',
                movimiento__almacen_origen=almacen,
                producto=producto
            ).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
            
            traslados_recibidos = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='TRASLADO',
                movimiento__almacen_destino=almacen,
                producto=producto
            ).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
            
            traslados_enviados = DetalleMovimientoAlmacen.objects.filter(
                movimiento__tipo='TRASLADO',
                movimiento__almacen_origen=almacen,
                producto=producto
            ).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
            
            filtro_entradas_cliente = {
                'movimiento__tipo': 'ENTRADA',
                'movimiento__almacen_origen': almacen,
                'producto': producto
            }
            filtro_salidas_cliente = {
                'movimiento__tipo': 'SALIDA',
                'movimiento__almacen_destino': almacen,
                'producto': producto
            }
            
            if obj.pk:
                entradas_cliente = DetalleMovimientoCliente.objects.filter(
                    **filtro_entradas_cliente
                ).exclude(pk=obj.pk).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
                
                salidas_cliente = DetalleMovimientoCliente.objects.filter(
                    **filtro_salidas_cliente
                ).exclude(pk=obj.pk).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
            else:
                entradas_cliente = DetalleMovimientoCliente.objects.filter(
                    **filtro_entradas_cliente
                ).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
                
                salidas_cliente = DetalleMovimientoCliente.objects.filter(
                    **filtro_salidas_cliente
                ).aggregate(buena=Sum('cantidad'), danada=Sum('cantidad_danada'))
            
            stock_bueno = (
                Decimal(str(entradas_almacen['buena'] or 0)) +
                Decimal(str(traslados_recibidos['buena'] or 0)) +
                Decimal(str(salidas_cliente['buena'] or 0)) -
                Decimal(str(salidas_almacen['buena'] or 0)) -
                Decimal(str(traslados_enviados['buena'] or 0)) -
                Decimal(str(entradas_cliente['buena'] or 0))
            )

            stock_danado = (
                Decimal(str(entradas_almacen['danada'] or 0)) +
                Decimal(str(traslados_recibidos['danada'] or 0)) +
                Decimal(str(salidas_cliente['danada'] or 0)) -
                Decimal(str(salidas_almacen['danada'] or 0)) -
                Decimal(str(traslados_enviados['danada'] or 0)) -
                Decimal(str(entradas_cliente['danada'] or 0))
            )
            
            color = 'green' if stock_bueno > 0 else 'red'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">B: {:.2f} | D: {:.2f}</span>',
                color,
                stock_bueno,
                stock_danado
            )
        except Exception as e:
            return format_html('<span style="color: red;">Error: {}</span>', str(e))

    get_stock_disponible.short_description = _('Stock Real Disponible')
    
    def get_cantidad_total(self, obj):
        if obj and obj.pk:
            return f"{obj.get_cantidad_total():,.2f}"
        return "0.00"
    get_cantidad_total.short_description = _('Cantidad Total')

@admin.register(MovimientoCliente)
class MovimientoClienteAdmin(admin.ModelAdmin):
    list_display = (
        'fecha',
        'numero_movimiento',
        'tipo',
        'cliente',
        'get_cliente_info',
        'get_cliente_origen_display',
        'get_cliente_destino_display',
        'almacen_origen',
        'almacen_destino',
        'proveedor',
        'recepcionista',
        'get_total_productos',
        'get_total_cantidad_buena',
        'get_total_cantidad_danada',
        'boton_descargar_pdf',
    )
    list_filter = (
        'tipo',
        'fecha',
        'cliente',
        'proveedor',
        'recepcionista'
    )
    search_fields = (
        'numero_movimiento',
        'cliente__codigo',
        'cliente__nombre',
        'cliente__direccion',
        'comentario',
        'observaciones_movimiento',
        'detalles__producto__nombre',
        'proveedor__nombre',
        'recepcionista__nombre'
    )
    ordering = ('-fecha', 'cliente__codigo', '-numero_movimiento')
    readonly_fields = ('preview_numero_movimiento', 'get_cliente_codigo', 'get_cliente_nombre', 'get_cliente_direccion')
    autocomplete_fields = ['cliente', 'cliente_origen', 'cliente_destino', 'proveedor', 'recepcionista']
    inlines = [DetalleMovimientoInline]
    
    fieldsets = (
        (None, {
            'fields': ('fecha', 'cliente', 'get_cliente_codigo', 'get_cliente_nombre', 'get_cliente_direccion'),
            'description': '<p style="color: #666; font-size: 13px; margin-bottom: 10px;">Los campos marcados con <strong style="color: red;">*</strong> son obligatorios.</p>'
        }),
        (_('N° de Movimiento'), {
            'fields': ('preview_numero_movimiento',)
        }),
        (_('Tipo de Movimiento'), {
            'fields': ('tipo',)
        }),
        (_('Almacenes'), {
            'fields': ('almacen_origen', 'almacen_destino'),
            'description': _('Seleccione los almacenes según el tipo de movimiento')
        }),
        (_('Clientes (solo para traslados)'), {
            'fields': ('cliente_origen', 'cliente_destino'),
            'description': _('Solo aplica para traslados entre clientes'),
            'classes': ('collapse',)
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        if 'fecha' in form.base_fields: form.base_fields['fecha'].label = '* Fecha'
        if 'cliente' in form.base_fields: form.base_fields['cliente'].label = '* Cliente'
        if 'tipo' in form.base_fields: form.base_fields['tipo'].label = '* Tipo de Movimiento'
        if 'almacen_origen' in form.base_fields: form.base_fields['almacen_origen'].label = '* Almacén Origen'
        if 'almacen_destino' in form.base_fields: form.base_fields['almacen_destino'].label = '* Almacén Destino'
        
        if 'proveedor' in form.base_fields:
            form.base_fields['proveedor'].required = True
            form.base_fields['proveedor'].label = '* Proveedor/Transp.'
        
        if 'recepcionista' in form.base_fields:
            form.base_fields['recepcionista'].required = True
            form.base_fields['recepcionista'].label = '* Recepcionista'
        
        return form

    def get_readonly_fields(self, request, obj=None):
        """Bloquea campos críticos en modo edición para evitar inconsistencias"""
        if obj:  # Si es edición (objeto ya existe)
            return (
                'preview_numero_movimiento', 
                'get_cliente_codigo', 
                'get_cliente_nombre', 
                'get_cliente_direccion',
                'tipo',
                'almacen_origen',
                'almacen_destino',
                'cliente_origen',
                'cliente_destino'
            )
        return (
            'preview_numero_movimiento', 
            'get_cliente_codigo', 
            'get_cliente_nombre', 
            'get_cliente_direccion'
        )   

    def get_fieldsets(self, request, obj=None):  # ← AGREGAR ESTE MÉTODO AQUÍ
        """Personaliza fieldsets según el tipo de movimiento en edición"""
        fieldsets = super().get_fieldsets(request, obj)
        
        # Si es edición Y es un traslado, mostrar el fieldset de clientes expandido
        if obj and obj.tipo == 'TRASLADO':
            # Convertir a lista mutable
            fieldsets = list(fieldsets)
            
            # Buscar el fieldset de clientes y modificarlo
            for i, fieldset in enumerate(fieldsets):
                if fieldset[0] == _('Clientes (solo para traslados)'):
                    # Remover la clase 'collapse' para que se muestre expandido
                    fieldsets[i] = (
                        fieldset[0],
                        {
                            'fields': fieldset[1]['fields'],
                            'description': fieldset[1].get('description', ''),
                            # NO incluir 'classes': ('collapse',)
                        }
                    )
                    break
        
        return fieldsets 

    def boton_descargar_pdf(self, obj):
        if obj.pk:
            url = reverse('admin:beneficiarios_movimientocliente_descargar_pdf', args=[obj.pk])
            return format_html('<a class="button" href="{}" target="_blank" style="padding: 5px 10px; background-color: #417690; color: white;">📄 PDF</a>', url)
        return "-"
    boton_descargar_pdf.short_description = "Reporte"
    boton_descargar_pdf.allow_tags = True
    
    def get_cliente_info(self, obj):
        return f"{obj.cliente.nombre} - {obj.cliente.direccion or ''}" if obj.cliente else "-"
    get_cliente_info.short_description = _('Info Cliente')
    
    # ✅ NUEVOS MÉTODOS PARA MOSTRAR CLIENTE ORIGEN Y DESTINO
    def get_cliente_origen_display(self, obj):
        """Muestra el cliente origen solo si es un traslado"""
        if obj.tipo == 'TRASLADO' and obj.cliente_origen:
            return format_html(
                '<span style="color: #0066cc; font-weight: bold;">{}</span><br>'
                '<span style="color: #666; font-size: 11px;">{}</span>',
                obj.cliente_origen.codigo,
                obj.cliente_origen.nombre
            )
        return format_html('<span style="color: #999;">-</span>')
    get_cliente_origen_display.short_description = _('Cliente Origen')
    get_cliente_origen_display.admin_order_field = 'cliente_origen'
    
    def get_cliente_destino_display(self, obj):
        """Muestra el cliente destino solo si es un traslado"""
        if obj.tipo == 'TRASLADO' and obj.cliente_destino:
            return format_html(
                '<span style="color: #009933; font-weight: bold;">{}</span><br>'
                '<span style="color: #666; font-size: 11px;">{}</span>',
                obj.cliente_destino.codigo,
                obj.cliente_destino.nombre
            )
        return format_html('<span style="color: #999;">-</span>')
    get_cliente_destino_display.short_description = _('Cliente Destino')
    get_cliente_destino_display.admin_order_field = 'cliente_destino'
    
    def get_cliente_codigo(self, obj): return obj.cliente.codigo if obj.cliente else '-'
    get_cliente_codigo.short_description = _('Código del Cliente')
    
    def get_cliente_nombre(self, obj): return obj.cliente.nombre if obj.cliente else '-'
    get_cliente_nombre.short_description = _('Nombre del Cliente')
    
    def get_cliente_direccion(self, obj): return obj.cliente.direccion if obj.cliente and obj.cliente.direccion else '-'
    get_cliente_direccion.short_description = _('Dirección/Comunidad')
    
    def preview_numero_movimiento(self, obj): return obj.numero_movimiento if obj and obj.numero_movimiento else '-'
    preview_numero_movimiento.short_description = _('N° de movimiento')
    
    def get_total_productos(self, obj): return obj.get_total_productos()
    get_total_productos.short_description = _('Total Productos')
    
    def get_total_cantidad_buena(self, obj): return f"{obj.get_total_cantidad_buena():,.2f}"
    get_total_cantidad_buena.short_description = _('Cant. Buena')
    
    def get_total_cantidad_danada(self, obj): return f"{obj.get_total_cantidad_danada():,.2f}" if obj.get_total_cantidad_danada() > 0 else "-"
    get_total_cantidad_danada.short_description = _('Cant. Dañada')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:movimiento_id>/descargar-pdf/', self.admin_site.admin_view(self.descargar_pdf_view), name='beneficiarios_movimientocliente_descargar_pdf'),
            path('ajax/get-next-number/', self.admin_site.admin_view(self.get_next_number_view), name='beneficiarios_movimientocliente_next_number'),
            path('ajax/get-producto-unidad/<int:producto_id>/', self.admin_site.admin_view(self.get_producto_unidad_view), name='beneficiarios_producto_unidad'),
            path('ajax/get-cliente-info/<int:cliente_id>/', self.admin_site.admin_view(self.get_cliente_info_view), name='beneficiarios_cliente_info'),
            path('ajax/get-stock/<int:almacen_id>/<int:producto_id>/', self.admin_site.admin_view(self.get_stock_view), name='beneficiarios_get_stock'),
        ]
        return custom_urls + urls

    def descargar_pdf_view(self, request, movimiento_id):
        try:
            movimiento = MovimientoCliente.objects.get(pk=movimiento_id)
            buffer = generar_reporte_cliente_pdf(movimiento)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            filename = f'movimiento_{movimiento.numero_movimiento}.pdf'
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        except Exception: return HttpResponse("Error", status=500)

    def get_next_number_view(self, request):
        tipo = request.GET.get('tipo', '')
        cliente_id = request.GET.get('cliente_id', '')
        if not tipo or not cliente_id: return JsonResponse({'error': 'Faltan datos'}, status=400)
        try: cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist: return JsonResponse({'error': 'No cliente'}, status=404)
        
        ultimo = MovimientoCliente.objects.filter(cliente=cliente, tipo=tipo).order_by('-id').first()
        nuevo_num = 1
        
        if ultimo and ultimo.numero_movimiento:
            try: 
                # Lógica robusta: Reemplazamos / por - antes de dividir
                # Esto permite que funcione correctamente leyendo formatos viejos (-) y nuevos (/)
                numero_limpio = ultimo.numero_movimiento.replace('/', '-')
                nuevo_num = int(numero_limpio.split('-')[-1]) + 1
            except: pass
        
        pref = {'ENTRADA': 'ENT', 'SALIDA': 'SAL', 'TRASLADO': 'TRA'}.get(tipo, 'MOV')
        
        # --- CAMBIO REALIZADO AQUÍ ---
        # Se cambió el primer guion por una barra '/'
        # Formato resultante ejemplo: C001/ENT-0001
        return JsonResponse({'numero_movimiento': f"{cliente.codigo}/{pref}-{nuevo_num:04d}"})

    def get_producto_unidad_view(self, request, producto_id):
        from productos.models import Producto
        try:
            prod = Producto.objects.get(id=producto_id)
            return JsonResponse({'unidad': str(prod.unidad_medida)})
        except: return JsonResponse({}, status=404)

    def get_cliente_info_view(self, request, cliente_id):
        try:
            c = Cliente.objects.get(id=cliente_id)
            return JsonResponse({'codigo': c.codigo, 'nombre': c.nombre, 'direccion': c.direccion or ''})
        except: return JsonResponse({}, status=404)

    def get_stock_view(self, request, almacen_id, producto_id):
        try:
            from almacenes.models import Almacen, DetalleMovimientoAlmacen
            from productos.models import Producto
            
            try: almacen = Almacen.objects.get(id=almacen_id)
            except: return JsonResponse({'stock_bueno': 0, 'stock_danado': 0, 'error': 'Almacen inválido'})
            
            producto = Producto.objects.get(id=producto_id)
            
            ent_alm = DetalleMovimientoAlmacen.objects.filter(movimiento__tipo='ENTRADA', movimiento__almacen_destino=almacen, producto=producto).aggregate(b=Sum('cantidad'), d=Sum('cantidad_danada'))
            sal_alm = DetalleMovimientoAlmacen.objects.filter(movimiento__tipo='SALIDA', movimiento__almacen_origen=almacen, producto=producto).aggregate(b=Sum('cantidad'), d=Sum('cantidad_danada'))
            tra_rec = DetalleMovimientoAlmacen.objects.filter(movimiento__tipo='TRASLADO', movimiento__almacen_destino=almacen, producto=producto).aggregate(b=Sum('cantidad'), d=Sum('cantidad_danada'))
            tra_env = DetalleMovimientoAlmacen.objects.filter(movimiento__tipo='TRASLADO', movimiento__almacen_origen=almacen, producto=producto).aggregate(b=Sum('cantidad'), d=Sum('cantidad_danada'))
            
            ent_cli = DetalleMovimientoCliente.objects.filter(movimiento__tipo='ENTRADA', movimiento__almacen_origen=almacen, producto=producto).aggregate(b=Sum('cantidad'), d=Sum('cantidad_danada'))
            sal_cli = DetalleMovimientoCliente.objects.filter(movimiento__tipo='SALIDA', movimiento__almacen_destino=almacen, producto=producto).aggregate(b=Sum('cantidad'), d=Sum('cantidad_danada'))

            def val(x): return Decimal(str(x or 0))

            sb = val(ent_alm['b']) + val(tra_rec['b']) + val(sal_cli['b']) - val(sal_alm['b']) - val(tra_env['b']) - val(ent_cli['b'])
            sd = val(ent_alm['d']) + val(tra_rec['d']) + val(sal_cli['d']) - val(sal_alm['d']) - val(tra_env['d']) - val(ent_cli['d'])
            
            return JsonResponse({
                'stock_bueno': float(sb),
                'stock_danado': float(sd),
                'stock_total': float(sb + sd),
                'unidad': str(producto.unidad_medida) if producto.unidad_medida else 'UND'
            })
        except Exception as e:
            return JsonResponse({'error': str(e), 'stock_bueno': 0, 'stock_danado': 0})

    def response_add(self, request, obj, post_url_continue=None):
        if "_cancel" in request.POST: return HttpResponseRedirect(reverse('admin:beneficiarios_movimientocliente_changelist'))
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_cancel" in request.POST: return HttpResponseRedirect(reverse('admin:beneficiarios_movimientocliente_changelist'))
        return super().response_change(request, obj)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        
        if not instances and not change:
            from django.contrib import messages
            messages.error(request, 'Debe agregar al menos un producto al movimiento.')
            return
        
        for instance in instances:
            instance.save()
        formset.save_m2m()

    def render_change_form(self, request, context, **kwargs):
        response = super().render_change_form(request, context, **kwargs)
        
        script = """
        <script>
        (function($) {
            'use strict';
            $(document).ready(function() {
                
                var $campoCliente = $('#id_cliente');
                var $campoTipo = $('#id_tipo');
                var $campoAlmacenOrigen = $('#id_almacen_origen');
                var $campoAlmacenDestino = $('#id_almacen_destino');
                var $campoClienteOrigen = $('#id_cliente_origen');
                var $campoClienteDestino = $('#id_cliente_destino');
                
                var $rowAlmacenOrigen = $('.field-almacen_origen');
                var $rowAlmacenDestino = $('.field-almacen_destino');
                var $rowClienteOrigen = $('.field-cliente_origen');
                var $rowClienteDestino = $('.field-cliente_destino');
                
                var $infoCodigo = $('.field-get_cliente_codigo .readonly');
                var $infoNombre = $('.field-get_cliente_nombre .readonly');
                var $infoDireccion = $('.field-get_cliente_direccion .readonly');
                var $previewNumero = $('.field-preview_numero_movimiento .readonly');

                var stockCache = {};
                var activeRequests = {};

                function getTipoMovimiento() {
                    // Intentar obtener del select (modo creación)
                    if ($campoTipo.length && $campoTipo.is(':visible') && !$campoTipo.prop('disabled')) {
                        var valorSelect = $campoTipo.val();
                        if (valorSelect) return valorSelect;
                    }
                    
                    // Si está en solo lectura (modo edición), obtener del texto
                    var $readonlyField = $('.field-tipo .readonly');
                    if ($readonlyField.length > 0) {
                        var textoTipo = $readonlyField.text().trim();
                        
                        // Mapear el texto al valor del tipo
                        if (textoTipo.indexOf('Entrada') !== -1) return 'ENTRADA';
                        if (textoTipo.indexOf('Salida') !== -1) return 'SALIDA';
                        if (textoTipo.indexOf('Traslado') !== -1) return 'TRASLADO';
                    }
                    
                    // Como último recurso, intentar del select aunque esté deshabilitado
                    if ($campoTipo.length) {
                        return $campoTipo.val() || '';
                    }
                    
                    return '';
                }

                // --- FUNCIÓN DE VALIDACIÓN (SOLO PARA ENTRADA) ---
                function renderStockConValidacion($row, data) {
                    var $inputCantidad = $row.find('[id$="-cantidad"]');
                    var $inputDanada = $row.find('[id$="-cantidad_danada"]');
                    var $stockCell = $row.find('td.field-get_stock_disponible');
                    
                    var cantBuena = parseFloat($inputCantidad.val()) || 0;
                    var cantDanada = parseFloat($inputDanada.val()) || 0;
                    
                    var advertencia = '';
                    var colorBueno = 'green';
                    var colorDanado = 'green';

                    // Validar Cantidad Buena
                    if (cantBuena > data.stock_bueno) {
                        colorBueno = 'red';
                        advertencia += 'ADVERTENCIA: Stock bueno insuficiente! ';
                        $inputCantidad.css({'border': '2px solid red', 'background-color': '#ffebee'});
                    } else {
                        $inputCantidad.css({'border': '', 'background-color': ''});
                    }

                    // Validar Cantidad Dañada
                    if (cantDanada > data.stock_danado) {
                        colorDanado = 'red';
                        advertencia += '<br>ADVERTENCIA: Stock dañado insuficiente! ';
                        $inputDanada.css({'border': '2px solid red', 'background-color': '#ffebee'});
                    } else {
                        $inputDanada.css({'border': '', 'background-color': ''});
                    }

                    var htmlStock = '<span style="font-weight: bold;">';
                    htmlStock += '<span style="color: ' + colorBueno + ';">B: ' + data.stock_bueno.toFixed(2) + '</span>';
                    htmlStock += ' | ';
                    htmlStock += '<span style="color: ' + colorDanado + ';">D: ' + data.stock_danado.toFixed(2) + '</span>';
                    htmlStock += '</span>';

                    if (advertencia) {
                        htmlStock += '<br><span style="color: red; font-size: 11px; font-weight:bold;">' + advertencia + '</span>';
                    }
                    $stockCell.html(htmlStock);
                }

                function renderStockSimple($cell, data) {
                    if (data.error) { $cell.html('<span style="color:red">Error</span>'); return; }
                    var color = data.stock_bueno > 0 ? 'green' : 'red';
                    $cell.html('<span style="color:' + color + '; font-weight:bold">B: ' + parseFloat(data.stock_bueno).toFixed(2) + ' | D: ' + parseFloat(data.stock_danado).toFixed(2) + '</span>');
                }
                // -------------------------------------------------------------

                function actualizarInfoCliente() {
                    var clienteId = $campoCliente.val();
                    if (!clienteId) {
                        $infoCodigo.text('-'); $infoNombre.text('-'); $infoDireccion.text('-');
                        return;
                    }
                    $.ajax({
                        url: '/admin/beneficiarios/movimientocliente/ajax/get-cliente-info/' + clienteId + '/',
                        success: function(data) {
                            $infoCodigo.text(data.codigo || '-');
                            $infoNombre.text(data.nombre || '-');
                            $infoDireccion.text(data.direccion || '-');
                        }
                    });
                }

                function actualizarNumero() {
                    var tipo = getTipoMovimiento();
                    var clienteId = $campoCliente.val();
                    
                    if (!tipo || !clienteId) {
                        $previewNumero.text('-');
                        return;
                    }
                    
                    $.ajax({
                        url: '/admin/beneficiarios/movimientocliente/ajax/get-next-number/',
                        data: { 'tipo': tipo, 'cliente_id': clienteId },
                        success: function(data) {
                            if(data.numero_movimiento) $previewNumero.text(data.numero_movimiento);
                        }
                    });
                }

                function actualizarCampos() {
                    var tipo = getTipoMovimiento();
                    
                    $rowAlmacenOrigen.show();
                    $rowAlmacenDestino.show();
                    $rowClienteOrigen.hide();
                    $rowClienteDestino.hide();
                    
                    $campoAlmacenOrigen.prop('required', false);
                    $campoAlmacenDestino.prop('required', false);
                    $campoClienteOrigen.prop('required', false);
                    $campoClienteDestino.prop('required', false);

                    if (tipo === 'ENTRADA') {
                        $rowAlmacenDestino.hide();
                        $campoAlmacenOrigen.prop('required', true);
                        
                    } else if (tipo === 'SALIDA') {
                        $rowAlmacenOrigen.hide();
                        $campoAlmacenDestino.prop('required', true);
                        
                    } else if (tipo === 'TRASLADO') {
                        $rowAlmacenOrigen.hide();
                        $rowAlmacenDestino.hide();
                        $rowClienteOrigen.show();
                        $rowClienteDestino.show();
                        
                        // ✅ FORZAR EXPANSIÓN DEL FIELDSET EN MODO EDICIÓN
                        var $fieldsetClientes = $('.field-cliente_origen').closest('fieldset');
                        if ($fieldsetClientes.length > 0) {
                            $fieldsetClientes.removeClass('collapsed');
                            $fieldsetClientes.find('h2').removeClass('collapse-toggle');
                        }
                        
                        $campoClienteOrigen.prop('required', true);
                        $campoClienteDestino.prop('required', true);
                        
                        if ($campoCliente.val() && !$campoClienteOrigen.val()) {
                            $campoClienteOrigen.val($campoCliente.val()).trigger('change');
                        }
                        
                        // ✅ Validar en tiempo real
                        validarYMostrarAdvertencia();
                    }
                }

                function validarYMostrarAdvertencia() {
                    var clientePrincipalId = $campoCliente.val();
                    var clienteOrigenId = $campoClienteOrigen.val();
                    
                    // Eliminar advertencias previas
                    $('.advertencia-cliente-origen').remove();
                    $campoClienteOrigen.css({'border': '', 'background-color': ''});
                    
                    if (clientePrincipalId && clienteOrigenId && clientePrincipalId !== clienteOrigenId) {
                        // Mostrar advertencia visual
                        $campoClienteOrigen.css({
                            'border': '2px solid red',
                            'background-color': '#ffebee'
                        });
                        
                        // Agregar mensaje de advertencia
                        var mensajeAdvertencia = '<div class="advertencia-cliente-origen" style="color: red; font-weight: bold; margin-top: 5px; font-size: 12px;">' +
                            '⚠️ ERROR: El cliente origen debe ser igual al cliente del reporte' +
                            '</div>';
                        
                        $campoClienteOrigen.closest('.form-row').append(mensajeAdvertencia);
                    }
                }


                function validarClienteOrigenEnTraslado() {
                    var tipo = getTipoMovimiento();
                    if (tipo !== 'TRASLADO') {
                        return true; // No validar si no es traslado
                    }
                    
                    var clientePrincipalId = $campoCliente.val();
                    var clienteOrigenId = $campoClienteOrigen.val();
                    
                    if (clientePrincipalId && clienteOrigenId && clientePrincipalId !== clienteOrigenId) {
                        return false; // Validación fallida
                    }
                    
                    return true; // Validación exitosa
                }
                
                function actualizarUnidadYTotal(row) {
                    var $select = row.find('[id$="-producto"]');
                    var productoId = $select.val();
                    var $unitCell = row.find('td.field-get_unidad_medida');
                    var $totalCell = row.find('td.field-get_cantidad_total');
                    var $cantidadBuena = row.find('[id$="-cantidad"]');
                    var $cantidadDanada = row.find('[id$="-cantidad_danada"]');
                    
                    if (!productoId) {
                        $unitCell.text('-');
                        $totalCell.text('0.00');
                        return;
                    }

                    var buena = parseFloat($cantidadBuena.val()) || 0;
                    var danada = parseFloat($cantidadDanada.val()) || 0;
                    var total = buena + danada;
                    $totalCell.text(total.toFixed(2));
                    
                    if ($unitCell.text().trim() === '-' || $unitCell.text().trim() === '') {
                        $.ajax({
                            url: '/admin/beneficiarios/movimientocliente/ajax/get-producto-unidad/' + productoId + '/',
                            success: function(data) {
                                $unitCell.text(data.unidad || '-');
                            },
                            error: function() { $unitCell.text('-'); }
                        });
                    }
                }

                function actualizarStock() {
                    var tipo = getTipoMovimiento();
                    var almacenId = null;

                    // CORREGIDO: 
                    // ENTRADA (Cliente recibe) -> Sale de Almacen Origen.
                    // SALIDA (Cliente devuelve) -> Entra a Almacen Destino.
                    if (tipo === 'ENTRADA') {
                         almacenId = $campoAlmacenOrigen.val();
                    } else if (tipo === 'SALIDA') {
                         almacenId = $campoAlmacenDestino.val();
                    }
                    
                    if (tipo === 'TRASLADO' || !almacenId) {
                        $('td.field-get_stock_disponible').text('-');
                        return;
                    }

                    $('[id^="id_detalles-"][id$="-producto"]').each(function() {
                        var $select = $(this);
                        var productoId = $select.val();
                        var $row = $select.closest('tr');
                        var $cell = $row.find('td.field-get_stock_disponible');

                        if (!productoId) {
                            $cell.text('-');
                            return;
                        }

                        // CORREGIDO: Validar (rojo) solo si es ENTRADA (sale de almacen)
                        if (tipo === 'ENTRADA') {
                            $.ajax({
                                url: '/admin/beneficiarios/movimientocliente/ajax/get-stock/' + almacenId + '/' + productoId + '/',
                                success: function(res) {
                                    renderStockConValidacion($row, res);
                                }
                            });
                        } else {
                            // Si es SALIDA (devuelve al almacen), solo mostrar informativo verde
                            $.ajax({
                                url: '/admin/beneficiarios/movimientocliente/ajax/get-stock/' + almacenId + '/' + productoId + '/',
                                success: function(res) {
                                    renderStockSimple($cell, res);
                                }
                            });
                        }
                    });
                }
                
                function bindInlineEvents(row) {
                    var $productSelect = row.find('[id$="-producto"]');
                    var $cantidadBuena = row.find('[id$="-cantidad"]');
                    var $cantidadDanada = row.find('[id$="-cantidad_danada"]');
                    
                    $productSelect.off('change.inline').on('change.inline', function() {
                        actualizarUnidadYTotal(row);
                        actualizarStock(); 
                    });

                    // Evento INPUT para validar mientras se escribe
                    $cantidadBuena.off('input.total change.total').on('input.total change.total', function() {
                        actualizarUnidadYTotal(row);
                        
                        // CORREGIDO: Validar solo si es ENTRADA
                        if (getTipoMovimiento() === 'ENTRADA') {
                            var almId = $campoAlmacenOrigen.val();
                            var prodId = $productSelect.val();
                            if(almId && prodId) {
                                $.ajax({
                                    url: '/admin/beneficiarios/movimientocliente/ajax/get-stock/' + almId + '/' + prodId + '/',
                                    success: function(res) { renderStockConValidacion(row, res); }
                                });
                            }
                        }
                    });
                    
                    $cantidadDanada.off('input.total change.total').on('input.total change.total', function() {
                        actualizarUnidadYTotal(row);
                        
                        // CORREGIDO: Validar solo si es ENTRADA
                        if (getTipoMovimiento() === 'ENTRADA') {
                            var almId = $campoAlmacenOrigen.val();
                            var prodId = $productSelect.val();
                            if(almId && prodId) {
                                $.ajax({
                                    url: '/admin/beneficiarios/movimientocliente/ajax/get-stock/' + almId + '/' + prodId + '/',
                                    success: function(res) { renderStockConValidacion(row, res); }
                                });
                            }
                        }
                    });
                }
                
                $('#detalles-group .form-row').each(function() {
                    bindInlineEvents($(this));
                });
                
                $(document).on('formset:added', '#detalles-group', function(event, $row) {
                    bindInlineEvents($row);
                    actualizarStock();
                });

                $campoCliente.on('change', function() {
                    actualizarInfoCliente();
                    actualizarNumero();
                    if (getTipoMovimiento() === 'TRASLADO') actualizarCampos();
                });

                $campoTipo.on('change', function() {
                    actualizarCampos();
                    actualizarNumero();
                    actualizarStock();
                });

                $campoAlmacenOrigen.on('change', function() { actualizarStock(); });
                $campoAlmacenDestino.on('change', function() { actualizarStock(); });

                $campoClienteOrigen.on('change', function() {
                    if (getTipoMovimiento() === 'TRASLADO') {
                        validarYMostrarAdvertencia();
                    }
                });

                // Interceptar el envío del formulario para validar
                $('form').on('submit', function(e) {
                    if (!validarClienteOrigenEnTraslado()) {
                        e.preventDefault();
                        alert('ERROR: En un traslado, el cliente origen debe ser igual al cliente del reporte.');
                        $campoClienteOrigen.focus();
                        return false;
                    }
                });
                
                setTimeout(function() {
                    actualizarInfoCliente();
                    actualizarCampos();
                    if ($previewNumero.text().trim() === '-' || $previewNumero.text().trim() === '') {
                        actualizarNumero();
                    }
                    $('#detalles-group .form-row').each(function() {
                        bindInlineEvents($(this)); 
                        actualizarUnidadYTotal($(this));
                    });
                    actualizarStock();
                }, 500);

            });
        })(django.jQuery);
        </script>
        """
        
        response.render()
        response.content = response.content.decode('utf-8').replace('</body>', script + '</body>').encode('utf-8')
        return response

@admin.register(DetalleMovimientoCliente)
class DetalleMovimientoClienteAdmin(admin.ModelAdmin):
    list_display = (
        'get_fecha',
        'get_numero_movimiento',
        'get_tipo_movimiento',
        'get_cliente',
        'producto',
        'get_unidad_medida',
        'cantidad',
        'cantidad_danada',
        'get_cantidad_total',
        'get_porcentaje_danado'
    )
    list_filter = ('movimiento__tipo', 'movimiento__fecha', 'movimiento__cliente', 'producto')
    search_fields = ('producto__nombre', 'movimiento__numero_movimiento', 'movimiento__cliente__nombre', 'observaciones_producto')
    ordering = ('-movimiento__fecha', 'movimiento__cliente__codigo', '-movimiento__numero_movimiento', 'producto__nombre')
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
    
    def get_cliente(self, obj):
        return obj.movimiento.cliente.codigo if obj.movimiento.cliente else "-"
    get_cliente.short_description = _('Cliente')
    
    def get_fecha(self, obj):
        return obj.movimiento.fecha.strftime('%d/%m/%Y')
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
            'movimiento__cliente',
            'movimiento__cliente_origen',
            'movimiento__cliente_destino',
            'movimiento__almacen_origen',
            'movimiento__almacen_destino',
            'movimiento__proveedor',
            'movimiento__recepcionista',
            'producto',
            'producto__unidad_medida'
        )

    def response_add(self, request, obj, post_url_continue=None):
        if "_cancel" in request.POST:
            return HttpResponseRedirect(reverse('admin:beneficiarios_detallemovimientocliente_changelist'))
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_cancel" in request.POST:
            return HttpResponseRedirect(reverse('admin:beneficiarios_detallemovimientocliente_changelist'))
        return super().response_change(request, obj)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().changeform_view(request, object_id, form_url, extra_context)

