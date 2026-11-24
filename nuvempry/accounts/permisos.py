from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def solo_anonimos(vista):
    """Si ya hay sesión iniciada, manda al inicio (para login y register)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return vista(request, *args, **kwargs)
    return envoltura


def requiere_permiso(permiso):
    """Exige sesión iniciada y que el rol tenga el permiso indicado (ej: 'crud_user', 'crud_item', 'update_stock')."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if not getattr(request.user.role, permiso, False):
                raise PermissionDenied  # responde 403
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador