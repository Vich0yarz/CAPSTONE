from django.db.models import Case, ExpressionWrapper, F, IntegerField, Q, When
from django.shortcuts import get_object_or_404, render
from django.utils.http import urlencode

from accounts.permisos import requiere_permiso
from inventory.models import Item
from .models import Audit

LOTE_AUDITORIA = 25
ORDENES = {
    "fecha": "Fecha",
    "stock": "Stock final",
}
TEXTO_DIR = {  # (ascendente, descendente)
    "fecha": ("Más antiguos primero", "Más recientes primero"),
    "stock": ("Menor a mayor", "Mayor a menor"),
}
TIPOS_EVENTO = [
    ("PRODUCT_CREATED", "Producto creado"),
    ("PRODUCT_UPDATED", "Producto editado"),
    ("PRODUCT_DELETED", "Producto eliminado"),
    ("SUBPRODUCT_CREATED", "Subproducto creado"),
    ("SUBPRODUCT_UPDATED", "Subproducto editado"),
    ("SUBPRODUCT_DELETED", "Subproducto eliminado"),
    ("STOCK_UPDATED", "Stock actualizado"),
]


def _url_auditoria(**params):
    limpios = {k: v for k, v in params.items() if v}
    return "?" + urlencode(limpios) if limpios else "?"


@requiere_permiso("crud_user")
def auditoria(request):
    base_qs = Audit.objects.filter(company=request.user.company)
    total_empresa = base_qs.count()

    q = request.GET.get("q", "").strip()
    evento = request.GET.get("evento", "").strip()
    usuario = request.GET.get("usuario", "").strip()
    orden = request.GET.get("orden", "fecha")
    if orden not in ORDENES:
        orden = "fecha"
    direccion = request.GET.get("dir", "desc")
    if direccion not in ("asc", "desc"):
        direccion = "desc"

    try:
        offset = max(0, int(request.GET.get("offset", 0)))
    except ValueError:
        offset = 0

    # Stock después del cambio
    qs = base_qs.annotate(
        stock_final=Case(
            When(
                event_type__in=[Audit.PRODUCT_CREATED, Audit.SUBPRODUCT_CREATED],
                move_quantity__isnull=False,
                then=F("move_quantity"),
            ),
            When(
                event_type__in=[Audit.STOCK_UPDATED, Audit.SUBPRODUCT_STOCK_UPDATED],
                past_count__isnull=False,
                move_quantity__isnull=False,
                then=ExpressionWrapper(
                    F("past_count") + F("move_quantity"),
                    output_field=IntegerField(),
                ),
            ),
            default=F("past_count"),
            output_field=IntegerField(),
        )
    )

    if q:
        qs = qs.filter(Q(involved__icontains=q) | Q(user_mail__icontains=q))

    if evento:
        if evento == "STOCK_UPDATED":
            qs = qs.filter(event_type__in=[Audit.STOCK_UPDATED, Audit.SUBPRODUCT_STOCK_UPDATED])
        else:
            qs = qs.filter(event_type=evento)

    if usuario:
        qs = qs.filter(user_mail=usuario)

    if orden == "stock":
        criterio = (
            F("stock_final").asc(nulls_last=True)
            if direccion == "asc"
            else F("stock_final").desc(nulls_last=True)
        )
        qs = qs.order_by(criterio, "-date_time", "-id_audit")
    else:
        qs = (
            qs.order_by("date_time", "id_audit")
            if direccion == "asc"
            else qs.order_by("-date_time", "-id_audit")
        )

    total_filtrado = qs.count()
    eventos = list(qs[offset : offset + LOTE_AUDITORIA])
    siguiente_offset = offset + len(eventos)
    hay_mas = siguiente_offset < total_filtrado

    if request.GET.get("parcial") == "1":
        response = render(request, "audit/fragmentos/filas_auditoria.html", {
            "eventos": eventos,
            "es_parcial": True,
        })
        response["X-Has-More"] = "1" if hay_mas else "0"
        response["X-Next-Offset"] = str(siguiente_offset)
        return response

    # Opciones de dropdown: Tipo de evento
    opciones_evento = [{
        "etiqueta": "Todos los eventos",
        "activo": evento == "",
        "url": _url_auditoria(q=q, usuario=usuario, orden=orden, dir=direccion),
    }]
    evento_etiqueta = "Tipo de evento"
    for clave, etiqueta in TIPOS_EVENTO:
        activo = clave == evento
        if activo:
            evento_etiqueta = etiqueta
        opciones_evento.append({
            "etiqueta": etiqueta,
            "activo": activo,
            "url": _url_auditoria(q=q, evento=clave, usuario=usuario, orden=orden, dir=direccion),
        })

    # Opciones de dropdown: Usuario
    correos = list(
        base_qs.values_list("user_mail", flat=True).distinct().order_by("user_mail")
    )
    opciones_usuario = [{
        "etiqueta": "Todos los usuarios",
        "activo": usuario == "",
        "url": _url_auditoria(q=q, evento=evento, orden=orden, dir=direccion),
    }]
    usuario_etiqueta = "Usuario"
    for mail in correos:
        activo = mail == usuario
        if activo:
            usuario_etiqueta = mail
        opciones_usuario.append({
            "etiqueta": mail,
            "activo": activo,
            "url": _url_auditoria(q=q, evento=evento, usuario=mail, orden=orden, dir=direccion),
        })

    # Opciones de dropdown: Organizar por (Fecha / Stock final)
    opciones_orden = []
    for clave, etiqueta in ORDENES.items():
        activo = clave == orden
        nueva_dir = ("desc" if direccion == "asc" else "asc") if activo else "desc"
        opciones_orden.append({
            "etiqueta": etiqueta,
            "activo": activo,
            "url": _url_auditoria(q=q, evento=evento, usuario=usuario, orden=clave, dir=nueva_dir),
        })

    url_limpiar_q = _url_auditoria(evento=evento, usuario=usuario, orden=orden, dir=direccion)
    url_toggle_dir = _url_auditoria(
        q=q,
        evento=evento,
        usuario=usuario,
        orden=orden,
        dir="desc" if direccion == "asc" else "asc",
    )

    return render(request, "audit/auditoria.html", {
        "eventos": eventos,
        "q": q,
        "evento": evento,
        "usuario": usuario,
        "orden": orden,
        "direccion": direccion,
        "evento_etiqueta": evento_etiqueta,
        "usuario_etiqueta": usuario_etiqueta,
        "opciones_evento": opciones_evento,
        "opciones_usuario": opciones_usuario,
        "opciones_orden": opciones_orden,
        "dir_texto": TEXTO_DIR[orden][0 if direccion == "asc" else 1],
        "url_limpiar_q": url_limpiar_q,
        "url_toggle_dir": url_toggle_dir,
        "hay_filtros": bool(q or evento or usuario or orden != "fecha" or direccion != "desc"),
        "total_empresa": total_empresa,
        "hay_mas": hay_mas,
        "siguiente_offset": siguiente_offset,
    })


@requiere_permiso("crud_user")
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