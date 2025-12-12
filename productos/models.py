from django.db import models
from django.utils.html import format_html

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="* Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "3.1. Categorías"
        # 🚀 OPTIMIZACIÓN: Índice para búsquedas por nombre
        indexes = [
            models.Index(fields=['nombre']),
        ]

class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="* Nombre")
    abreviatura = models.CharField(max_length=10, unique=True, verbose_name="* Abreviatura")

    def __str__(self):
        return self.abreviatura

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "3.2. Unidades de Medida"
        # 🚀 OPTIMIZACIÓN: Índice para búsquedas por abreviatura
        indexes = [
            models.Index(fields=['abreviatura']),
        ]

class Producto(models.Model):
    TIPO_PRODUCTO = (
        ('INSUMOS', 'Insumos'),
        ('EQUIPOS', 'Equipos'),
        ('HERRAMIENTAS', 'Herramientas'),
        ('OTROS', 'Otros'),
    )

    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_PRODUCTO, 
        verbose_name="* Tipo de Producto"
    )
    codigo = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False, 
        verbose_name="Código"
    )
    nombre = models.CharField(max_length=150, verbose_name="* Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    categoria = models.ForeignKey(
        Categoria, 
        on_delete=models.PROTECT,  # Protege: no permite eliminar si hay productos asociados
        null=False,  # Ahora es obligatorio
        blank=False,  # Ahora es obligatorio
        verbose_name="* Categoría"
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida, 
        on_delete=models.PROTECT,  # Protege: no permite eliminar si hay productos asociados
        null=False,  # Ahora es obligatorio
        blank=False,  # Ahora es obligatorio
        verbose_name="* Unidad de Medida"
    )
    stock_minimo = models.PositiveIntegerField(default=0, verbose_name="Stock Mínimo")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    def __str__(self):
        """Muestra código - nombre - unidad"""
        unidad = self.unidad_medida.abreviatura if self.unidad_medida else 'Sin unidad'
        return f"{self.codigo} - {self.nombre} - {unidad}"

    def preview_codigo(self, obj=None):
        codigo = self.codigo if self.codigo else "-"
        return format_html('<span id="codigo-preview">{}</span>', codigo)
    preview_codigo.short_description = "Código generado"

    def save(self, *args, **kwargs):
        if not self.pk and not self.codigo:
            prefijos = {'INSUMOS':'I','EQUIPOS':'E','HERRAMIENTAS':'H','OTROS':'O'}
            prefijo = prefijos.get(self.tipo, 'P')
            ultimo = Producto.objects.filter(tipo=self.tipo).order_by('-codigo').first()
            if ultimo and ultimo.codigo:
                try:
                    num = int(ultimo.codigo[1:]) + 1
                except:
                    num = 1
            else:
                num = 1
            self.codigo = f"{prefijo}{num:04d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['tipo','codigo']
        verbose_name = "Producto"
        verbose_name_plural = "3.3. Productos"
        # =========================================================
        # 🚀 OPTIMIZACIÓN: ÍNDICES PARA JOINs Y FILTROS EN REPORTES
        # =========================================================
        indexes = [
            models.Index(fields=['tipo']),
            models.Index(fields=['codigo']),
            models.Index(fields=['categoria']),
            models.Index(fields=['unidad_medida']),
            models.Index(fields=['activo']),
        ]