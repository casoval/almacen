from django.core.management.base import BaseCommand
from django.db import connection
from decimal import Decimal
from stock_cache.models import StockCache
from almacenes.models import Almacen
from productos.models import Producto


class Command(BaseCommand):
    help = 'Pobla la tabla StockCache con los datos de stock actuales'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Borra todos los registros existentes antes de poblar',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Borrando registros existentes...')
            StockCache.objects.all().delete()

        self.stdout.write('Obteniendo almacenes y productos...')

        almacenes = Almacen.objects.all()
        productos = Producto.objects.all()

        total_registros = 0

        for almacen in almacenes:
            self.stdout.write(f'Procesando almacén: {almacen.nombre}')

            # Calcular stock para este almacén usando la lógica de get_stock_bulk
            sql = """
            SELECT
                d.producto_id,
                SUM(
                    CASE
                        WHEN m.tipo = 'ENTRADA' AND m.almacen_destino_id = %s THEN d.cantidad ELSE 0 END
                ) - SUM(
                    CASE
                        WHEN m.tipo = 'SALIDA' AND m.almacen_origen_id = %s THEN d.cantidad ELSE 0 END
                ) + SUM(
                    CASE
                        WHEN m.tipo = 'TRASLADO' AND m.almacen_destino_id = %s THEN d.cantidad ELSE 0 END
                ) - SUM(
                    CASE
                        WHEN m.tipo = 'TRASLADO' AND m.almacen_origen_id = %s THEN d.cantidad ELSE 0 END
                ) AS stock_bueno,
                SUM(
                    CASE
                        WHEN m.tipo = 'ENTRADA' AND m.almacen_destino_id = %s THEN d.cantidad_danada ELSE 0 END
                ) - SUM(
                    CASE
                        WHEN m.tipo = 'SALIDA' AND m.almacen_origen_id = %s THEN d.cantidad_danada ELSE 0 END
                ) + SUM(
                    CASE
                        WHEN m.tipo = 'TRASLADO' AND m.almacen_destino_id = %s THEN d.cantidad_danada ELSE 0 END
                ) - SUM(
                    CASE
                        WHEN m.tipo = 'TRASLADO' AND m.almacen_origen_id = %s THEN d.cantidad_danada ELSE 0 END
                ) AS stock_danado
            FROM almacenes_detallemovimientoalmacen d
            JOIN almacenes_movimientoalmacen m ON d.movimiento_id = m.id
            WHERE (m.almacen_origen_id = %s OR m.almacen_destino_id = %s)
            GROUP BY d.producto_id
            """

            params = [almacen.id] * 10

            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

            for row in rows:
                pid, sb, sd = row
                sb = sb or Decimal(0)
                sd = sd or Decimal(0)

                # Solo crear registro si hay stock
                if sb != 0 or sd != 0:
                    StockCache.objects.update_or_create(
                        producto_id=pid,
                        almacen=almacen,
                        defaults={
                            'stock_bueno': sb,
                            'stock_danado': sd,
                            'stock_total': sb + sd,
                        }
                    )
                    total_registros += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'StockCache poblado exitosamente. Total registros: {total_registros}'
            )
        )