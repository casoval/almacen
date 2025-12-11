from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import MovimientoCliente


@receiver(pre_save, sender=MovimientoCliente)
def actualizar_numero_movimiento(sender, instance, **kwargs):
    """
    Actualiza el número de movimiento cuando cambia el código del cliente
    """
    # Solo procesar si ya existe el objeto (no es creación nueva)
    if instance.pk:
        try:
            # Obtener la instancia anterior de la base de datos
            old_instance = MovimientoCliente.objects.get(pk=instance.pk)
            
            # Verificar si cambió el cliente
            if old_instance.cliente != instance.cliente:
                # El cliente cambió, necesitamos actualizar el número de movimiento
                if instance.numero_movimiento and instance.cliente:
                    # Extraer el tipo y número del movimiento actual
                    partes = instance.numero_movimiento.split('-')
                    
                    if len(partes) >= 3:
                        # Formato esperado: CODIGO-TIPO-NUMERO
                        tipo_prefijo = partes[-2]  # ENT, SAL, TRA
                        numero = partes[-1]  # 0001, 0002, etc.
                        
                        # Crear el nuevo número de movimiento con el nuevo código
                        nuevo_numero = f"{instance.cliente.codigo}-{tipo_prefijo}-{numero}"
                        instance.numero_movimiento = nuevo_numero
        except MovimientoCliente.DoesNotExist:
            # Si no existe la instancia anterior, es una creación nueva
            pass