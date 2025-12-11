from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomLoginView, dashboard

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    
    # CORREGIDO: Logout ahora redirige correctamente al login
    path('logout/', 
         auth_views.LogoutView.as_view(
             next_page='login',
             http_method_names=['get', 'post']  # Acepta GET y POST
         ), 
         name='logout'),
    
    path('dashboard/', dashboard, name='dashboard'),
    
    # --- RECUPERACIÓN DE CONTRASEÑA ---
    
    # 1. Solicitar correo
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='usuarios/password_reset_form.html',
             email_template_name='usuarios/password_reset_email.html',
             subject_template_name='usuarios/password_reset_subject.txt',
             success_url='/usuarios/password-reset/done/'
         ), 
         name='password_reset'),

    # 2. Aviso de correo enviado
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='usuarios/password_reset_done.html'
         ), 
         name='password_reset_done'),

    # 3. Ingresar nueva contraseña (link del correo)
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='usuarios/password_reset_confirm.html',
             success_url='/usuarios/reset/done/'
         ), 
         name='password_reset_confirm'),

    # 4. Éxito al cambiar contraseña
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='usuarios/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]