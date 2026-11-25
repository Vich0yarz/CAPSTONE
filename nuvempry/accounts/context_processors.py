from .tour import obtener_pasos_tour


def tour_guiado(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    return {
        "tour_pasos": obtener_pasos_tour(),
        "tour_iniciar": bool(request.session.get("iniciar_tour", False)),
    }