(function($) {
    'use strict';
    
    console.log('✓ Script movimiento_almacen.js cargado');
    
    $(document).ready(function() {
        console.log('✓ DOM ready - Iniciando configuración');
        
        // Función para actualizar el estado de los campos de almacén
        function actualizarCamposAlmacen() {
            var tipoMovimiento = $('#id_tipo').val();
            
            // Referencias a los campos
            var fieldAlmacenOrigen = $('.field-almacen_origen');
            var fieldAlmacenDestino = $('.field-almacen_destino');
            var selectOrigen = $('#id_almacen_origen');
            var selectDestino = $('#id_almacen_destino');
            
            console.log('Tipo de movimiento seleccionado:', tipoMovimiento);
            console.log('Campo origen encontrado:', fieldAlmacenOrigen.length > 0);
            console.log('Campo destino encontrado:', fieldAlmacenDestino.length > 0);
            
            // Resetear estados - mostrar todo primero
            fieldAlmacenOrigen.show();
            fieldAlmacenDestino.show();
            selectOrigen.prop('disabled', false).prop('required', false);
            selectDestino.prop('disabled', false).prop('required', false);
            
            // Remover clases de error previas
            fieldAlmacenOrigen.find('.errorlist').remove();
            fieldAlmacenDestino.find('.errorlist').remove();
            fieldAlmacenOrigen.removeClass('errors');
            fieldAlmacenDestino.removeClass('errors');
            
            // Aplicar lógica según el tipo de movimiento
            if (tipoMovimiento === 'ENTRADA') {
                console.log('→ Configurando para ENTRADA');
                // Entrada: solo almacén destino
                fieldAlmacenOrigen.hide();
                selectOrigen.val('').prop('disabled', true).prop('required', false);
                selectDestino.prop('required', true);
                
                // Agregar ayuda visual
                if (!fieldAlmacenDestino.find('.help').length) {
                    fieldAlmacenDestino.find('label').after(
                        '<div class="help" style="color: #666; font-size: 12px; margin-top: 3px;">' +
                        '→ Seleccione el almacén donde ingresarán los productos</div>'
                    );
                }
                
            } else if (tipoMovimiento === 'SALIDA') {
                console.log('→ Configurando para SALIDA');
                // Salida: solo almacén origen
                fieldAlmacenDestino.hide();
                selectDestino.val('').prop('disabled', true).prop('required', false);
                selectOrigen.prop('required', true);
                
                // Agregar ayuda visual
                if (!fieldAlmacenOrigen.find('.help').length) {
                    fieldAlmacenOrigen.find('label').after(
                        '<div class="help" style="color: #666; font-size: 12px; margin-top: 3px;">' +
                        '→ Seleccione el almacén desde donde saldrán los productos</div>'
                    );
                }
                
            } else if (tipoMovimiento === 'TRASLADO') {
                console.log('→ Configurando para TRASLADO');
                // Traslado: ambos almacenes requeridos
                selectOrigen.prop('required', true);
                selectDestino.prop('required', true);
                
                // Agregar ayuda visual
                if (!fieldAlmacenOrigen.find('.help').length) {
                    fieldAlmacenOrigen.find('label').after(
                        '<div class="help" style="color: #666; font-size: 12px; margin-top: 3px;">' +
                        '→ Almacén desde donde se trasladarán los productos</div>'
                    );
                }
                if (!fieldAlmacenDestino.find('.help').length) {
                    fieldAlmacenDestino.find('label').after(
                        '<div class="help" style="color: #666; font-size: 12px; margin-top: 3px;">' +
                        '→ Almacén hacia donde se trasladarán los productos</div>'
                    );
                }
            } else {
                console.log('→ Tipo no seleccionado, mostrando ambos campos');
                // Limpiar ayudas
                fieldAlmacenOrigen.find('.help').remove();
                fieldAlmacenDestino.find('.help').remove();
            }
        }
        
        // Verificar que el campo tipo existe
        var campoTipo = $('#id_tipo');
        if (campoTipo.length === 0) {
            console.error('✗ No se encontró el campo #id_tipo');
            return;
        }
        
        console.log('✓ Campo tipo encontrado');
        
        // Ejecutar al cargar la página
        actualizarCamposAlmacen();
        
        // Ejecutar cuando cambia el tipo de movimiento
        campoTipo.on('change', function() {
            console.log('Cambio detectado en tipo de movimiento');
            // Limpiar ayudas previas antes de actualizar
            $('.field-almacen_origen .help, .field-almacen_destino .help').remove();
            actualizarCamposAlmacen();
        });
        
        console.log('✓ Event listener agregado al campo tipo');
    });
    
})(django.jQuery);