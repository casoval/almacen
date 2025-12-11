console.log('✅ ARCHIVO productos_codigo.js CARGADO');

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ DOM CARGADO');
    
    const tipoSelect = document.querySelector('#id_tipo');
    const previewField = document.querySelector('#codigo-preview');
    
    console.log('Tipo select:', tipoSelect);
    console.log('Preview field:', previewField);
    
    if (!tipoSelect || !previewField) {
        console.error('❌ Elementos no encontrados');
        return;
    }
    
    function actualizarCodigo() {
        const tipo = tipoSelect.value;
        console.log('🔄 Tipo seleccionado:', tipo);
        
        if (!tipo) {
            previewField.textContent = '-';
            previewField.style.color = '#666';
            previewField.style.fontWeight = 'normal';
            return;
        }
        
        // ⏳ Mostrar indicador de carga
        previewField.textContent = '⏳ Generando código...';
        previewField.style.color = '#999';
        previewField.style.fontWeight = 'normal';
        previewField.style.fontStyle = 'italic';
        
        const url = `/productos/next_code/?tipo=${encodeURIComponent(tipo)}`;
        console.log('📡 Haciendo fetch a:', url);
        
        fetch(url)
            .then(response => {
                console.log('📡 Response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('✅ Código recibido:', data.codigo);
                
                // ✅ Mostrar el código con estilo exitoso
                previewField.textContent = data.codigo || '-';
                previewField.style.color = '#417690';  // Azul Django admin
                previewField.style.fontWeight = 'bold';
                previewField.style.fontStyle = 'normal';
                previewField.style.fontSize = '14px';
            })
            .catch(error => {
                console.error('❌ Error completo:', error);
                
                // ❌ Mostrar error
                previewField.textContent = '❌ Error al generar código';
                previewField.style.color = '#ba2121';  // Rojo Django admin
                previewField.style.fontWeight = 'bold';
                previewField.style.fontStyle = 'normal';
            });
    }
    
    // Escuchar cambios en el select
    tipoSelect.addEventListener('change', actualizarCodigo);
    
    // Actualizar al cargar si ya hay un tipo seleccionado
    if (tipoSelect.value) {
        actualizarCodigo();
    }
    
    console.log('✅ Event listener agregado correctamente');
});