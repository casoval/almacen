from django.contrib import admin
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from .models import Recepcionista

@admin.register(Recepcionista)
class RecepcionistaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'email', 'activo', 'get_uso_estado')
    search_fields = ('nombre', 'telefono', 'email')
    list_filter = ('activo',)
    ordering = ('nombre',)
    
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
        ("Datos del Recepcionista", {
            "fields": ("nombre", "telefono", "email", "activo")
        }),
    )

    class Media:
        css = {
            'all': ('admin/productos_admin.css',)
        }

    def get_uso_estado(self, obj):
        """Muestra si el recepcionista está siendo usado en movimientos"""
        if obj.pk:
            from almacenes.models import MovimientoAlmacen
            from beneficiarios.models import MovimientoCliente
            
            en_uso = (
                MovimientoAlmacen.objects.filter(recepcionista=obj).exists() or
                MovimientoCliente.objects.filter(recepcionista=obj).exists()
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
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_cancel'] = True
        return super().add_view(request, form_url, extra_context=extra_context)
    
    def save_model(self, request, obj, form, change):
        """Mensaje al guardar recepcionista"""
        try:
            super().save_model(request, obj, form, change)
            accion = 'actualizado' if change else 'creado'
            messages.success(request, f'✅ Recepcionista "{obj.nombre}" {accion} correctamente.')
        except Exception as e:
            messages.error(request, f'❌ Error al guardar el recepcionista: {str(e)}')
            raise
    
    def delete_model(self, request, obj):
        """Mensaje al eliminar un recepcionista"""
        nombre = obj.nombre
        try:
            super().delete_model(request, obj)
            messages.success(request, f'🗑️ Recepcionista {nombre} eliminado correctamente.')
        except Exception as e:
            messages.error(request, f'❌ Error al eliminar el recepcionista: {str(e)}')
            raise