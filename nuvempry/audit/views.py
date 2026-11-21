from django.shortcuts import render

from accounts.permisos import requiere_permiso

from .models import Audit


@requiere_permiso("crud_user")
def auditoria(request):
    eventos = (
        Audit.objects.filter(company=request.user.company)  # solo SU empresa
        .order_by("-date_time", "-id_audit")[:200]
    )
    return render(request, "audit/auditoria.html", {"eventos": eventos})