from django.urls import path
from . import views

urlpatterns = [
    path('next_code/', views.next_code, name='productos_next_code'),
]