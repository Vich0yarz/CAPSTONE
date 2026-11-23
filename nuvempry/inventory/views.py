from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import F
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.http import urlencode

from accounts.permisos import requiere_permiso

from . import services
from .forms import (ProductoCrearForm, ProductoEditarForm, SkuForm,
                    SubproductoCrearForm, SubproductoEditarForm)
from .models import Item

FRAG = "inventory/fragmentos/"

ORDENES = {
    "nombre": "Nombre",
    "categoria": "Categoría",
    "unidades": "Unidades",
    "precio": "Precio",
}
TEXTO_DIR = {  # (ascendente, descendente)
    "nombre": ("A → Z", "Z → A"),
    "categoria": ("A → Z", "Z → A"),
    "unidades": ("menor a mayor", "mayor a menor"),
    "precio": ("menor a mayor", "mayor a menor"),
}


def _expresion_orden(clave):
    return {
        "nombre": Lower("name_item"),
        "categoria": Lower("category"),
        "unidades": F("stock"),
        "precio": F("price"),
    }[clave]


def _ok(request, mensaje, ver=None):
    """Respuesta de éxito: el JavaScript recarga la página y reabre el producto `ver`."""
    messages.success(request, mensaje)
    return JsonResponse({"ok": True, "ver": ver})


@login_required
def inventario(request):
    usuario = request.user
    q = request.GET.get("q", "").strip()
    orden = request.GET.get("orden", "nombre")
    if orden not in ORDENES:
        orden = "nombre"
    direccion = request.GET.get("dir", "asc")
    if direccion not in ("asc", "desc"):
        direccion = "asc"

    productos = (
        Item.objects.filter(company=usuario.company, parent__isnull=True)
        .prefetch_related("subproducts")
    )
    if q:
        productos = productos.filter(name_item__icontains=q)
    expr = _expresion_orden(orden)
    criterio = expr.asc(nulls_last=True) if direccion == "asc" else expr.desc(nulls_last=True)
    productos = productos.order_by(criterio, Lower("name_item"), "pk")

    opciones = []
    for clave, etiqueta in ORDENES.items():
        activo = clave == orden
        params = {"orden": clave, "dir": "desc" if (activo and direccion == "asc") else "asc"}
        if q:
            params["q"] = q
        opciones.append({
            "etiqueta": etiqueta,
            "activo": activo,
            "texto": TEXTO_DIR[clave][0 if direccion == "asc" else 1] if activo else "",
            "url": "?" + urlencode(params),
        })

    return render(request, "inventory/inventario.html", {
        "productos": productos,
        "q": q,
        "orden": orden,
        "direccion": direccion,
        "opciones": opciones,
        "orden_etiqueta": f"{ORDENES[orden]} ({TEXTO_DIR[orden][0 if direccion == 'asc' else 1]})",
        "puede_editar": usuario.role.crud_item,
        "puede_actualizar_stock": request.user.role.update_stock,
    })


@login_required
def producto_detalle(request, pk):
    item = get_object_or_404(
        Item.objects.select_related("parent"), pk=pk, company=request.user.company
    )
    es_sub = item.parent_id is not None
    return render(request, FRAG + "detalle.html", {
        "item": item,
        "es_sub": es_sub,
        "subs": [] if es_sub else item.subproducts.order_by("code_sku"),
        "puede_editar": request.user.role.crud_item,
        "puede_actualizar_stock": request.user.role.update_stock,
    })


@requiere_permiso("crud_item")
def producto_nuevo(request):
    form = ProductoCrearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.crear_producto(request.user, form.cleaned_data)
        return _ok(request, "Producto agregado.")
    return render(request, FRAG + "crear.html", {"form": form})


@requiere_permiso("crud_item")
def editar_producto(request, pk):
    item = get_object_or_404(
        Item.objects.select_related("parent"), pk=pk, company=request.user.company
    )
    es_sub = item.parent_id is not None
    if es_sub:
        form = SubproductoEditarForm(request.POST or None, initial={"detail": item.detail})
    else:
        form = ProductoEditarForm(request.POST or None, initial={
            "name_item": item.name_item, "category": item.category,
            "detail": item.detail, "price": item.price,
        })

    if request.method == "POST" and form.is_valid():
        _, hubo_cambios = services.editar_producto(request.user, item, form.cleaned_data)
        return _ok(request, "Cambios guardados." if hubo_cambios else "No había cambios que guardar.",
                   ver=item.pk)
    return render(request, FRAG + "editar.html", {"item": item, "form": form, "es_sub": es_sub})


@requiere_permiso("crud_item")
def eliminar_producto(request, pk):
    item = get_object_or_404(
        Item.objects.select_related("parent"), pk=pk, company=request.user.company
    )
    if request.method == "POST":
        ver = item.parent_id  # si era subproducto, se reabre su producto original
        nombre = item.name_item
        services.eliminar_producto(request.user, item)
        return _ok(request, f"«{nombre}» eliminado.", ver=ver)
    return render(request, FRAG + "eliminar.html", {"item": item, "n_subs": item.subproducts.count()})


@requiere_permiso("crud_item")
def subproducto_nuevo(request, pk):
    empresa = request.user.company
    # parent__isnull=True: no existen subproductos de subproductos
    padre = get_object_or_404(Item, pk=pk, company=empresa, parent__isnull=True)
    accion = request.POST.get("accion") if request.method == "POST" else None
    paso, form1, form2 = 1, SkuForm(empresa), None

    if accion == "generar":
        form1 = SkuForm(empresa, initial={"code_sku": services.generar_sku(padre)})
    elif accion == "continuar":
        form1 = SkuForm(empresa, request.POST)
        if form1.is_valid():
            paso = 2
            form2 = SubproductoCrearForm(empresa, initial={"code_sku": form1.cleaned_data["code_sku"]})
    elif accion == "crear":
        paso = 2
        form2 = SubproductoCrearForm(empresa, request.POST)
        if form2.is_valid():
            d = form2.cleaned_data
            try:
                services.crear_subproducto(request.user, padre, d["code_sku"], d["stock"], d["detail"])
            except IntegrityError:  # otro usuario tomó el mismo SKU justo antes
                form2.add_error("code_sku", "Ese código SKU ya existe en tu empresa.")
            else:
                return _ok(request, "Subproducto creado.", ver=padre.pk)

    return render(request, FRAG + "subproducto.html",
                  {"padre": padre, "paso": paso, "form1": form1, "form2": form2})


@requiere_permiso("update_stock")
def actualizar_stock(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    try:
        nuevo_stock = int(request.POST.get("stock", ""))
        if nuevo_stock < 0 or nuevo_stock > 9999:
            raise ValueError("Stock fuera de rango")
    except ValueError:
        return JsonResponse({"ok": False, "error": "Cantidad de stock inválida (0 a 9999)."}, status=400)
    
    try:
        item, hubo_cambios, stock_padre = services.actualizar_stock(request.user, pk, nuevo_stock)
    except Item.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Producto no encontrado."}, status=404)
    except ValueError as err:
        return JsonResponse({"ok": False, "error": str(err)}, status=400)

    return JsonResponse({
        "ok": True,
        "hubo_cambios": hubo_cambios,
        "stock": item.stock,
        "parent_id": item.parent_id,
        "parent_stock": stock_padre,
    })