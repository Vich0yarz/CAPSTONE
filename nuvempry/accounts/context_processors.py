from .tour import obtener_pasos_tour


def tour_guiado(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    rol = getattr(user, "role", None)
    if not getattr(rol, "crud_user", False) and not request.session.get("iniciar_tour"):
        return {}
    return {
        "tour_pasos": obtener_pasos_tour(),
        "tour_iniciar": bool(request.session.get("iniciar_tour", False)),
    }