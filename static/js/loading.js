// static/js/loading.js - Indicadores de carga para AJAX
function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i> Cargando...</div>';
    }
}

function hideLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = '';
    }
}

// Auto-hide después de 30s por seguridad
setTimeout(() => {
    document.querySelectorAll('.loading-spinner').forEach(el => el.remove());
}, 30000);