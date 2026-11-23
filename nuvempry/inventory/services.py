import re
import secrets
import unicodedata

from django.db.models import Sum
from django.db import transaction
from audit.models import Audit
from .models import Item

ETIQUETAS = {
    "name_item": "nombre",
    "category": "categoría",
    "detail": "detalle",
    "price": "precio",
}
CAMPOS_COMPARTIDOS = ("name_item", "category", "price")  # el subproducto los hereda


def _etiqueta(item, max_nombre=20):
    nombre = item.name_item
    if len(nombre) > max_nombre:
        nombre = nombre[:max_nombre - 3].rstrip() + "..."
    sku = f" [{item.code_sku}]" if item.code_sku else ""
    return f"{nombre}{sku}"


def _fmt(valor):
    return "(vacío)" if valor is None else str(valor)


def _normalizar(campo, valor):
    if campo in ("category", "detail"):
        return (valor or "").strip() or None  # texto vacío = sin dato
    return valor


def _registrar(usuario, empresa, evento, involucrado, cantidad=None, stock_previo=None):
    Audit.objects.create(
        company=empresa,
        event_type=evento,
        involved=involucrado[:255],
        move_quantity=cantidad,
        past_count=stock_previo,
        user_mail=usuario.mail_user,
    )


def generar_sku(padre):
    """Código sencillo: 3 letras del nombre + 4 caracteres al azar (ej: CAM-7K2Q)."""
    base = unicodedata.normalize("NFKD", padre.name_item).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]", "", base).upper()[:3] or "SKU"
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para no confundir
    while True:
        codigo = base + "-" + "".join(secrets.choice(alfabeto) for _ in range(4))
        if not Item.objects.filter(company=padre.company, code_sku=codigo).exists():
            return codigo


@transaction.atomic
def crear_producto(usuario, datos):
    item = Item.objects.create(
        company=usuario.company,
        name_item=datos["name_item"],
        stock=datos["stock"],
        category=_normalizar("category", datos.get("category")),
        detail=_normalizar("detail", datos.get("detail")),
        price=datos.get("price"),
    )
    _registrar(
        usuario,
        item.company,
        Audit.PRODUCT_CREATED,
        _etiqueta(item),
        cantidad=item.stock,
        stock_previo=0,
    )
    return item


@transaction.atomic
def crear_subproducto(usuario, padre, sku, stock, detalle):
    sub = Item.objects.create(
        company=padre.company,
        parent=padre,
        name_item=padre.name_item,   # heredados del producto original
        category=padre.category,
        price=padre.price,
        stock=stock,                 # propios
        detail=_normalizar("detail", detalle),
        code_sku=sku,
    )
    _registrar(
        usuario,
        padre.company,
        Audit.SUBPRODUCT_CREATED,
        _etiqueta(sub),
        cantidad=sub.stock,
        stock_previo=0,
    )
    return sub


@transaction.atomic
def editar_producto(usuario, item, datos):
    """Aplica solo los campos permitidos. Devuelve (item, hubo_cambios)."""
    cambios = {}
    for campo in ETIQUETAS:          # ignora cualquier otro dato (stock, empresa, etc.)
        if campo not in datos:
            continue
        nuevo = _normalizar(campo, datos[campo])
        anterior = getattr(item, campo)
        if anterior != nuevo:
            cambios[campo] = (anterior, nuevo)
            setattr(item, campo, nuevo)

    if not cambios:
        return item, False           # sin cambios = sin auditoría

    item.save(update_fields=list(cambios))
    detalle = "; ".join(
        f"{_fmt(a)} → {_fmt(n)}" for c, (a, n) in cambios.items()
    )
    if detalle:
        detalle = detalle[0].upper() + detalle[1:]
    evento = Audit.SUBPRODUCT_UPDATED if item.parent_id else Audit.PRODUCT_UPDATED
    _registrar(usuario, item.company, evento, f"{_etiqueta(item)}\n{detalle}")

    # Los subproductos heredan nombre, categoría y precio del producto original
    compartidos = {c: n for c, (a, n) in cambios.items() if c in CAMPOS_COMPARTIDOS}
    if compartidos and item.parent_id is None:
        for sub in item.subproducts.select_for_update():
            for campo, nuevo in compartidos.items():
                setattr(sub, campo, nuevo)
            sub.save(update_fields=list(compartidos))
            _registrar(usuario, item.company, Audit.SUBPRODUCT_UPDATED,
                       f"{_etiqueta(sub)}\nHeredó cambios del producto original")
    return item, True


@transaction.atomic
def eliminar_producto(usuario, item):
    afectados = [item] + list(item.subproducts.all())  # el padre arrastra a sus subproductos
    for it in afectados:
        evento = Audit.SUBPRODUCT_DELETED if it.parent_id else Audit.PRODUCT_DELETED
        _registrar(
            usuario,
            it.company,
            evento,
            _etiqueta(it),
            cantidad=-it.stock,
            stock_previo=it.stock,
        )
    item.delete()


def _recalcular_stock_padre(padre):
    """Sincroniza el stock del producto padre con la suma de sus subproductos."""
    total = padre.subproducts.aggregate(total=Sum("stock"))["total"] or 0
    padre.stock = total
    padre.save(update_fields=["stock"])
    return total


@transaction.atomic
def actualizar_stock(usuario, pk, nuevo_stock):
    """Actualiza el stock de un ítem (o subproducto) y registra el evento en auditoría."""
    if nuevo_stock < 0:
        raise ValueError("El stock no puede ser negativo.")

    item = Item.objects.select_for_update().get(
        pk=pk, company=usuario.company
    )

    # Si es un producto padre que tiene subproductos, su stock no se edita directamente
    if item.parent_id is None and item.subproducts.exists():
        raise ValueError("El stock de este producto se calcula automáticamente desde sus subproductos.")

    stock_previo = item.stock
    diferencia = nuevo_stock - stock_previo

    if diferencia == 0:
        return item, False, None

    item.stock = nuevo_stock
    item.save(update_fields=["stock"])

    evento = Audit.SUBPRODUCT_STOCK_UPDATED if item.parent_id else Audit.STOCK_UPDATED
    involucrado = _etiqueta(item)
    stock_padre = None

    if item.parent_id:
        padre = Item.objects.select_for_update().get(pk=item.parent_id)
        stock_padre = _recalcular_stock_padre(padre)

    _registrar(
        usuario,
        item.company,
        evento,
        involucrado,
        cantidad=diferencia,
        stock_previo=stock_previo,
    )
    return item, True, stock_padre