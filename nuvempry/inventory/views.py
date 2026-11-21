from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permisos import requiere_permiso

from . import services
from .forms import (ProductoCrearForm, ProductoEditarForm, SkuForm,
                    SubproductoCrearForm, SubproductoEditarForm)
from .models import Item


@login_required
def inventario(request):
    usuario = request.user
    puede_editar = usuario.role.crud_item
    form = ProductoCrearForm(request.POST or None)

    if request.method == "POST":
        if not puede_editar:
            raise PermissionDenied  # 403: se valida en el servidor, no en el HTML
        if form.is_valid():
            services.crear_producto(usuario, form.cleaned_data)
            messages.success(request, "Producto agregado.")
            return redirect("inventario")

    productos = (
        Item.objects.filter(company=usuario.company, parent__isnull=True)  # solo SU empresa
        .prefetch_related(Prefetch("subproducts", queryset=Item.objects.order_by("code_sku")))
        .order_by("name_item")
    )
    return render(request, "inventory/inventario.html", {
        "productos": productos,
        "form": form,
        "puede_editar": puede_editar,
        "abrir_form": request.method == "POST",  # reabre el formulario si hubo errores
    })


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
        messages.success(request, "Cambios guardados." if hubo_cambios else "No había cambios que guardar.")
        return redirect("inventario")
    return render(request, "inventory/editar_producto.html",
                  {"item": item, "form": form, "es_sub": es_sub})


@require_POST
@requiere_permiso("crud_item")
def eliminar_producto(request, pk):
    item = get_object_or_404(Item, pk=pk, company=request.user.company)
    nombre = item.name_item
    services.eliminar_producto(request.user, item)
    messages.success(request, f"«{nombre}» eliminado.")
    return redirect("inventario")


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
                messages.success(request, "Subproducto creado.")
                return redirect("inventario")

    return render(request, "inventory/subproducto_nuevo.html",
                  {"padre": padre, "paso": paso, "form1": form1, "form2": form2})