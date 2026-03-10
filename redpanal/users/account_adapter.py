import re
from django import forms
from django.utils.translation import gettext_lazy as _
from allauth.account.adapter import DefaultAccountAdapter

# Tu regex original
USERNAME_REGEX = re.compile(r'^[\w.+-]+$')  # same as UserCreationForm regex but without '@'

class MyAccountAdapter(DefaultAccountAdapter):
    """
    Adaptador de cuenta personalizado para allauth.
    Define comportamientos específicos para la gestión de usuarios.
    """

    def clean_username(self, username, shallow=False):
        """
        Limpia y valida el nombre de usuario.
        Se le añade 'shallow=False' para compatibilidad con las últimas versiones de allauth.
        """
        
        # Opción 1: Llama al método padre. 
        # Esto es lo más simple y a menudo lo que se necesita.
        return super().clean_username(username, shallow=shallow)
        
        # --- Opcional: Si necesitas tu propia lógica de validación ---
        # if not username:
        #     raise forms.ValidationError(_("El nombre de usuario no puede estar vacío."))
            
        # if not shallow and not USERNAME_REGEX.match(username):
        #     raise forms.ValidationError(_("El nombre de usuario contiene caracteres no permitidos."))

        # return username
        # ------------------------------------------------------------
