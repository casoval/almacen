from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('exportar-movimientos-excel/', views.exportar_movimientos_excel, name='exportar_movimientos_excel'),
    path('exportar-movimientos-csv/', views.exportar_movimientos_csv, name='exportar_movimientos_csv'),
    path('obtener-detalle-stock/', views.obtener_detalle_stock, name='obtener_detalle_stock'),
    path('obtener-detalle-almacen/', views.obtener_detalle_almacen, name='obtener_detalle_almacen'),
    path('obtener-detalle-producto-almacenes/', views.obtener_detalle_producto_almacenes, name='obtener_detalle_producto_almacenes'),
    path('api/numeros-movimiento/', views.obtener_numeros_movimiento_json, name='obtener_numeros_movimiento_json'),
    path('obtener-detalle-estadistica/', views.obtener_detalle_estadistica, name='obtener_detalle_estadistica'),
]