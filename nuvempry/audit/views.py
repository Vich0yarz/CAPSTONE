from accounts.permisos import requiere_permiso
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from inventory.models import Item
from .models import Audit


@requiere_permiso("crud_user")
def auditoria(request):
    eventos = (
        Audit.objects.filter(company=request.user.company)  # solo SU empresa
        .order_by("-date_time", "-id_audit")[:200]
    )
    return render(request, "audit/auditoria.html", {"eventos": eventos})

@login_required
def detalle_item_auditoria(request, pk):
    registro = get_object_or_404(Audit, pk=pk, company=request.user.company)
    item = None

    if registro.sku_involucrado:
        item = Item.objects.filter(
            company=request.user.company,
            code_sku=registro.sku_involucrado
        ).first()
    elif registro.nombre_busqueda:
        qs = Item.objects.filter(company=request.user.company, parent__isnull=True)
        if registro.titulo_involucrado.split(" [")[0].endswith("..."):
            item = qs.filter(name_item__istartswith=registro.nombre_busqueda).first()
        else:
            item = qs.filter(name_item__iexact=registro.nombre_busqueda).first()

    return render(request, "audit/fragmentos/resumen_item.html", {
        "registro": registro,
        "item": item,
    })