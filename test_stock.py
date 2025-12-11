from almacenes.models import Almacen, MovimientoAlmacen
from productos.models import Producto

# Tomar un almacén y producto de prueba
almacen = Almacen.objects.first()
producto = Producto.objects.first()

# Ver el stock
stock = almacen.get_stock_producto(producto)
print(stock)

# Ver todos los movimientos del producto en ese almacén
from almacenes.models import DetalleMovimientoAlmacen

print("\nENTRADAS:")
entradas = DetalleMovimientoAlmacen.objects.filter(
    movimiento__tipo='ENTRADA',
    movimiento__almacen_destino=almacen,
    producto=producto
)
for e in entradas:
    print(f"  {e.movimiento.numero_movimiento}: Buena={e.cantidad}, Dañada={e.cantidad_danada}")

print("\nSALIDAS:")
salidas = DetalleMovimientoAlmacen.objects.filter(
    movimiento__tipo='SALIDA',
    movimiento__almacen_origen=almacen,
    producto=producto
)
for s in salidas:
    print(f"  {s.movimiento.numero_movimiento}: Buena={s.cantidad}, Dañada={s.cantidad_danada}")

print("\nTRASLADOS RECIBIDOS:")
tras_rec = DetalleMovimientoAlmacen.objects.filter(
    movimiento__tipo='TRASLADO',
    movimiento__almacen_destino=almacen,
    producto=producto
)
for t in tras_rec:
    print(f"  {t.movimiento.numero_movimiento}: Buena={t.cantidad}, Dañada={t.cantidad_danada}")

print("\nTRASLADOS ENVIADOS:")
tras_env = DetalleMovimientoAlmacen.objects.filter(
    movimiento__tipo='TRASLADO',
    movimiento__almacen_origen=almacen,
    producto=producto
)
for t in tras_env:
    print(f"  {t.movimiento.numero_movimiento}: Buena={t.cantidad}, Dañada={t.cantidad_danada}")