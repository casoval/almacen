#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar stocks en el sistema
Guardar como: verificar_stocks.py
Ejecutar: python manage.py shell < verificar_stocks.py
"""

from almacenes.models import Almacen, MovimientoAlmacen, DetalleMovimientoAlmacen
from productos.models import Producto

print("\n" + "="*80)
print(" VERIFICACIÓN DE STOCKS EN EL SISTEMA")
print("="*80)

# 1. Listar todos los almacenes
print("\n📦 ALMACENES EN EL SISTEMA:")
almacenes = Almacen.objects.filter(activo=True)
print(f"   Total: {almacenes.count()} almacenes activos\n")

for almacen in almacenes:
    print(f"   {almacen.id}. {almacen.nombre}")

# 2. Para cada almacén, mostrar su stock
print("\n" + "="*80)
print(" STOCKS POR ALMACÉN")
print("="*80)

for almacen in almacenes:
    print(f"\n🏢 ALMACÉN: {almacen.nombre}")
    print("-" * 80)
    
    try:
        stocks = almacen.get_todos_los_stocks()
        
        if len(stocks) == 0:
            print("   ⚠️  No hay productos con movimientos en este almacén")
            continue
        
        print(f"   Total de productos: {len(stocks)}\n")
        
        # Mostrar cada producto con su stock
        for producto, stock_data in stocks.items():
            print(f"   📦 {producto.codigo} - {producto.nombre}")
            print(f"      ├─ Entradas:          {stock_data['entradas_total']:>10.2f}")
            print(f"      ├─ Salidas:           {stock_data['salidas_total']:>10.2f}")
            print(f"      ├─ Trasl. Recibidos:  {stock_data['traslados_recibidos_total']:>10.2f}")
            print(f"      ├─ Trasl. Enviados:   {stock_data['traslados_enviados_total']:>10.2f}")
            print(f"      └─ 📊 STOCK FINAL:    {stock_data['stock_total']:>10.2f} {producto.unidad_medida}")
            
            # Separar stock bueno y dañado si hay dañado
            if stock_data['stock_danado'] > 0:
                print(f"         ├─ Bueno:          {stock_data['stock_bueno']:>10.2f}")
                print(f"         └─ Dañado:         {stock_data['stock_danado']:>10.2f}")
            print()
            
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# 3. Resumen general
print("\n" + "="*80)
print(" RESUMEN GENERAL")
print("="*80)

total_movimientos = MovimientoAlmacen.objects.count()
total_entradas = MovimientoAlmacen.objects.filter(tipo='ENTRADA').count()
total_salidas = MovimientoAlmacen.objects.filter(tipo='SALIDA').count()
total_traslados = MovimientoAlmacen.objects.filter(tipo='TRASLADO').count()

print(f"\n   📊 Total de movimientos:    {total_movimientos}")
print(f"   📥 Entradas:                {total_entradas}")
print(f"   📤 Salidas:                 {total_salidas}")
print(f"   🔄 Traslados:               {total_traslados}")

# Calcular stock total del sistema
print(f"\n   📦 Stock total por almacén:")
stock_total_sistema = 0

for almacen in almacenes:
    stocks = almacen.get_todos_los_stocks()
    stock_almacen = sum(s['stock_total'] for s in stocks.values())
    stock_total_sistema += stock_almacen
    print(f"      {almacen.nombre}: {stock_almacen:.2f}")

print(f"\n   🎯 STOCK TOTAL DEL SISTEMA: {stock_total_sistema:.2f}")

# 4. Últimos 10 movimientos
print("\n" + "="*80)
print(" ÚLTIMOS 10 MOVIMIENTOS")
print("="*80 + "\n")

ultimos = MovimientoAlmacen.objects.order_by('-id')[:10]

for mov in ultimos:
    print(f"   {mov.numero_movimiento} - {mov.tipo} - {mov.fecha}")
    print(f"      Origen:  {mov.almacen_origen.nombre if mov.almacen_origen else 'N/A'}")
    print(f"      Destino: {mov.almacen_destino.nombre if mov.almacen_destino else 'N/A'}")
    
    # Mostrar productos del movimiento
    detalles = mov.detalles.all()
    for det in detalles:
        print(f"      • {det.producto.nombre}: {det.cantidad} (B) + {det.cantidad_danada} (D)")
    print()

print("="*80)
print(" ✅ VERIFICACIÓN COMPLETADA")
print("="*80 + "\n")