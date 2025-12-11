from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from .forms import UsuarioLoginForm

class CustomLoginView(LoginView):
    template_name = 'usuarios/login.html'
    form_class = UsuarioLoginForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirige según tipo de usuario después del login"""
        user = self.request.user
        
        # Si es staff (administrador), redirigir al admin
        if user.is_staff:
            messages.info(
                self.request, 
                f'Bienvenido al panel administrativo, {user.get_full_name() or user.username}'
            )
            return reverse_lazy('admin:index')
        
        # Si es usuario normal, redirigir al dashboard
        messages.success(
            self.request, 
            f'¡Bienvenido {user.get_full_name() or user.username}!'
        )
        return reverse_lazy('dashboard')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Iniciar Sesión'
        context['site_title'] = 'CASOVAL'
        context['site_header'] = 'CASOVAL'
        return context
    
    def form_invalid(self, form):
        """Mensaje cuando falla el login"""
        messages.error(
            self.request, 
            'Usuario o contraseña incorrectos. Por favor, inténtalo de nuevo.'
        )
        return super().form_invalid(form)


@login_required(login_url='login')
def dashboard(request):
    """Dashboard para usuarios NO-staff"""
    
    # Si es staff, redirigir al admin
    if request.user.is_staff:
        return redirect('admin:index')
    
    # Verificar TODOS los permisos del usuario
    permisos = {
        # Productos
        'puede_ver_productos': request.user.has_perm('productos.view_producto'),
        'puede_agregar_productos': request.user.has_perm('productos.add_producto'),
        'puede_editar_productos': request.user.has_perm('productos.change_producto'),
        'puede_eliminar_productos': request.user.has_perm('productos.delete_producto'),
        
        # Almacenes
        'puede_ver_movimientos': request.user.has_perm('almacenes.view_movimientoalmacen'),
        'puede_agregar_movimientos': request.user.has_perm('almacenes.add_movimientoalmacen'),
        
        # Beneficiarios
        'puede_ver_beneficiarios': request.user.has_perm('beneficiarios.view_beneficiario'),
        'puede_agregar_beneficiarios': request.user.has_perm('beneficiarios.add_beneficiario'),
        'puede_editar_beneficiarios': request.user.has_perm('beneficiarios.change_beneficiario'),
        
        # Reportes
        'puede_ver_reportes': request.user.has_perm('reportes.view_reporte'),
        'puede_crear_reportes': request.user.has_perm('reportes.add_reporte'),
        
        # Proveedores
        'puede_ver_proveedores': request.user.has_perm('proveedores.view_proveedor'),
        'puede_agregar_proveedores': request.user.has_perm('proveedores.add_proveedor'),
        'puede_editar_proveedores': request.user.has_perm('proveedores.change_proveedor'),
    }
    
    context = {
        'user': request.user,
        'permisos': permisos,
        'title': 'Dashboard Principal',
    }
    
    return render(request, 'usuarios/dashboard.html', context)