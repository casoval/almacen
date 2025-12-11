from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from .models import Producto, Categoria, UnidadMedida

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tipo', 'nombre', 'categoria', 'unidad_medida', 'stock_minimo', 'activo', 'get_uso_estado')
    list_filter = ('tipo', 'categoria', 'unidad_medida', 'activo')
    search_fields = ('codigo', 'nombre', 'descripcion')
    ordering = ('tipo', 'codigo')
    list_editable = ('activo',)
    readonly_fields = ('codigo', 'preview_codigo', 'fecha_creacion', 'fecha_actualizacion')

    fieldsets = (
        (None, {
            "fields": (),
            "description": mark_safe(
                '<div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #417690; margin-bottom: 20px;">'
                '<strong style="color: #417690; font-size: 14px;">ℹ️ Información importante:</strong><br>'
                '<span style="color: #666;">Los campos marcados con <strong style="color: #d9534f;">*</strong> son obligatorios.</span>'
                '</div>'
            )
        }),
        ("Tipo de Producto", {
            "fields": ("tipo",),
            "description": "⚠️ Seleccione el tipo para generar el código automáticamente. No podrá cambiarse después."
        }),
        ("Código Generado", {
            "fields": ("preview_codigo",),
            "description": "📋 Este código se asignará automáticamente al guardar el producto."
        }),
        ("Información Básica", {
            "fields": ("nombre", "descripcion")
        }),
        ("Clasificación", {
            "fields": ("categoria", "unidad_medida")
        }),
        ("Control de Stock", {
            "fields": ("stock_minimo",)
        }),
        ("Estado", {
            "fields": ("activo",)
        }),
        ("Información del Sistema", {
            "fields": ("fecha_creacion", "fecha_actualizacion"),
            "classes": ("collapse",),
            "description": "Información automática del sistema"
        }),
    )

    class Media:
        js = ('admin/productos_codigo.js',)
        css = {
            'all': ('admin/productos_admin.css',)
        }

    def get_urls(self):
        """Añadir URLs personalizadas para importar/exportar"""
        urls = super().get_urls()
        custom_urls = [
            path('importar/', self.admin_site.admin_view(self.importar_view), name='productos_producto_importar'),
            path('exportar/', self.admin_site.admin_view(self.exportar_view), name='productos_producto_exportar'),
        ]
        return custom_urls + urls

    def importar_view(self, request):
        """Vista para importar productos desde Excel"""
        from .views import importar_productos
        return importar_productos(request)

    def exportar_view(self, request):
        """Vista para exportar productos a Excel"""
        from .views import exportar_productos
        return exportar_productos(request)

    def changelist_view(self, request, extra_context=None):
        """Añadir botones personalizados a la lista"""
        extra_context = extra_context or {}
        extra_context['show_import_export'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def get_uso_estado(self, obj):
        """Muestra si el producto está siendo usado en movimientos"""
        if obj.pk:
            from almacenes.models import DetalleMovimientoAlmacen
            from beneficiarios.models import DetalleMovimientoCliente
            
            en_uso = (
                DetalleMovimientoAlmacen.objects.filter(producto=obj).exists() or
                DetalleMovimientoCliente.objects.filter(producto=obj).exists()
            )
            
            if en_uso:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">⚠️ En uso</span>'
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Libre</span>'
                )
        return "-"
    get_uso_estado.short_description = 'Estado'
    
    def get_readonly_fields(self, request, obj=None):
        """Hace campos de solo lectura según el contexto"""
        ro = list(self.readonly_fields)
        if obj:  # Si ya existe el producto (edición)
            ro.append('tipo')  # No permitir cambiar el tipo
        return ro

    def preview_codigo(self, obj):
        """Muestra una vista previa del código que se generará"""
        if obj and obj.codigo:
            codigo = obj.codigo
            icono = "✅"
            color = "#417690"
        else:
            codigo = "-"
            icono = "⏳"
            color = "#999"
        
        return format_html(
            '<span id="codigo-preview" style="font-weight: bold; color: {}; font-size: 14px;">{} {}</span>',
            color, icono, codigo
        )
    preview_codigo.short_description = "Código del producto"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Personaliza la vista de cambio para agregar el botón cancelar"""
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        """Personaliza la vista de agregar para agregar el botón cancelar"""
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().add_view(request, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        """
        Validaciones y lógica antes de guardar el modelo
        change=True significa que es una edición, change=False que es nuevo
        """
        # Si es un nuevo producto
        if not change:
            # Validar que se haya seleccionado un tipo
            if not obj.tipo:
                messages.error(request, '❌ Debe seleccionar un tipo de producto antes de guardar.')
                return
            
            # Validar que el nombre no esté vacío
            if not obj.nombre or not obj.nombre.strip():
                messages.error(request, '❌ El nombre del producto no puede estar vacío.')
                return
            
            # Validar categoría
            if not obj.categoria:
                messages.error(request, '❌ Debe seleccionar una categoría.')
                return
            
            # Validar unidad de medida
            if not obj.unidad_medida:
                messages.error(request, '❌ Debe seleccionar una unidad de medida.')
                return
            
            # El código se genera automáticamente en el método save() del modelo
            try:
                super().save_model(request, obj, form, change)
                messages.success(
                    request, 
                    f'✅ Producto creado exitosamente con código: {obj.codigo}'
                )
            except Exception as e:
                messages.error(request, f'❌ Error al crear el producto: {str(e)}')
                raise
        else:
            # Es una edición
            try:
                # Verificar si se intenta cambiar el código manualmente
                original = Producto.objects.get(pk=obj.pk)
                if original.codigo != obj.codigo:
                    messages.warning(
                        request, 
                        f'⚠️ El código no se puede modificar. Se mantendrá: {original.codigo}'
                    )
                    obj.codigo = original.codigo
                
                super().save_model(request, obj, form, change)
                messages.success(request, f'✅ Producto {obj.codigo} actualizado correctamente.')
            except Exception as e:
                messages.error(request, f'❌ Error al actualizar el producto: {str(e)}')
                raise

    def delete_model(self, request, obj):
        """Mensaje al eliminar un producto"""
        codigo = obj.codigo
        nombre = obj.nombre
        try:
            super().delete_model(request, obj)
            messages.success(request, f'🗑️ Producto {codigo} - {nombre} eliminado correctamente.')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar el producto: {str(e)}')
            raise

    def delete_queryset(self, request, queryset):
        """Mensaje al eliminar múltiples productos"""
        count = queryset.count()
        try:
            super().delete_queryset(request, queryset)
            messages.success(request, f'🗑️ {count} producto(s) eliminado(s) correctamente.')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar productos: {str(e)}')
            raise


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'get_uso_estado')
    search_fields = ('nombre', 'descripcion')
    
    fieldsets = (
        (None, {
            "fields": (),
            "description": mark_safe(
                '<div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #417690; margin-bottom: 20px;">'
                '<strong style="color: #417690; font-size: 14px;">ℹ️ Información importante:</strong><br>'
                '<span style="color: #666;">Los campos marcados con <strong style="color: #d9534f;">*</strong> son obligatorios.</span>'
                '</div>'
            )
        }),
        ("Datos de la Categoría", {
            "fields": ("nombre", "descripcion")
        }),
    )

    class Media:
        css = {
            'all': ('admin/productos_admin.css',)
        }

    def get_uso_estado(self, obj):
        """Muestra si la categoría está siendo usada en productos"""
        if obj.pk:
            from .models import Producto
            
            en_uso = Producto.objects.filter(categoria=obj).exists()
            
            if en_uso:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">⚠️ En uso</span>'
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Libre</span>'
                )
        return "-"
    get_uso_estado.short_description = 'Estado'

    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().add_view(request, form_url, extra_context=extra_context)
    
    def save_model(self, request, obj, form, change):
        """Mensaje al guardar categoría"""
        try:
            super().save_model(request, obj, form, change)
            accion = 'actualizada' if change else 'creada'
            messages.success(request, f'✅ Categoría "{obj.nombre}" {accion} correctamente.')
        except Exception as e:
            messages.error(request, f'❌ Error al guardar la categoría: {str(e)}')
            raise


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'get_uso_estado')
    search_fields = ('nombre', 'abreviatura')
    
    fieldsets = (
        (None, {
            "fields": (),
            "description": mark_safe(
                '<div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #417690; margin-bottom: 20px;">'
                '<strong style="color: #417690; font-size: 14px;">ℹ️ Información importante:</strong><br>'
                '<span style="color: #666;">Los campos marcados con <strong style="color: #d9534f;">*</strong> son obligatorios.</span>'
                '</div>'
            )
        }),
        ("Datos de la Unidad de Medida", {
            "fields": ("nombre", "abreviatura")
        }),
    )

    class Media:
        css = {
            'all': ('admin/productos_admin.css',)
        }

    def get_uso_estado(self, obj):
        """Muestra si la unidad de medida está siendo usada en productos"""
        if obj.pk:
            from .models import Producto
            
            en_uso = Producto.objects.filter(unidad_medida=obj).exists()
            
            if en_uso:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">⚠️ En uso</span>'
                )
            else:
                return format_html(
                    '<span style="color: green;">✓ Libre</span>'
                )
        return "-"
    get_uso_estado.short_description = 'Estado'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().add_view(request, form_url, extra_context=extra_context)
    
    def save_model(self, request, obj, form, change):
        """Mensaje al guardar unidad de medida"""
        try:
            super().save_model(request, obj, form, change)
            accion = 'actualizada' if change else 'creada'
            messages.success(request, f'✅ Unidad de medida "{obj.nombre}" {accion} correctamente.')
        except Exception as e:
            messages.error(request, f'❌ Error al guardar la unidad de medida: {str(e)}')
            raise