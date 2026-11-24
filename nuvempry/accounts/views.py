import json
import math
from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import Audit
from inventory.models import Item

from .forms import (CambiarClaveForm, CambiarRolForm, LoginForm, PerfilForm,
                    RegisterForm, TrabajadorForm)
from .models import Company, Role, User
from .permisos import requiere_permiso, solo_anonimos


MESES_ES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
DIAS_COBERTURA_MINIMA = 7   # días
MINIMO_SIN_HISTORIAL = 3    # stock


@login_required
def home(request):
    empresa = request.user.company
    ahora = timezone.now()
    hace_30_dias = ahora - timedelta(days=30)

    # 1. Catálogo vendible (productos sin hijos + subproductos)
    items_vendibles = list(
        Item.objects.filter(company=empresa)
        .select_related("parent")
        .filter(Q(parent__isnull=False) | Q(subproducts__isnull=True))
        .distinct()
    )

    info_por_sku = {}
    info_por_nombre = {}
    for it in items_vendibles:
        cat = (it.category or (it.parent.category if it.parent else None) or "Sin categoría").strip()
        titulo_visible = (it.detail or it.name_item) if it.parent_id else it.name_item
        nombre_producto = f"{titulo_visible} [{it.code_sku}]" if it.code_sku else titulo_visible
        datos_item = {
            "precio": it.price or 0,
            "categoria": cat,
            "producto": nombre_producto,
            "titulo": titulo_visible,
        }
        if it.code_sku:
            info_por_sku[it.code_sku] = datos_item
        if not it.parent_id:
            info_por_nombre[it.name_item.lower()] = datos_item

    # 2. Bajadas de stock en los últimos 12 meses
    y_inicio = ahora.year - 1 if ahora.month < 12 else ahora.year
    m_inicio = (ahora.month % 12) + 1
    inicio_12m = ahora.replace(year=y_inicio, month=m_inicio, day=1, hour=0, minute=0, second=0, microsecond=0)

    salidas = Audit.objects.filter(
        company=empresa,
        event_type__in=(Audit.STOCK_UPDATED, Audit.SUBPRODUCT_STOCK_UPDATED),
        move_quantity__lt=0,
        date_time__gte=inicio_12m,
    )

    claves_meses = []
    etiquetas_meses = []
    y, m = ahora.year, ahora.month
    for _ in range(12):
        claves_meses.append((y, m))
        etiquetas_meses.append(f"{MESES_ES[m - 1]} {str(y)[2:]}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    claves_meses.reverse()
    etiquetas_meses.reverse()

    unidades_cat_mes = defaultdict(lambda: defaultdict(int))
    ingresos_cat_mes = defaultdict(lambda: defaultdict(int))
    unidades_prod_cat_mes = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    ingresos_prod_cat_mes = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    top_productos = defaultdict(int)
    salidas_30d_por_item = defaultdict(int)
    ultima_salida = {}

    for ev in salidas:
        cant = abs(ev.move_quantity)
        clave = (ev.date_time.year, ev.date_time.month)
        sku = ev.sku_involucrado
        nombre_base = ev.nombre_busqueda
        clave_item = sku or nombre_base.lower()

        meta = info_por_sku.get(sku) if sku else info_por_nombre.get(nombre_base.lower())
        precio = meta["precio"] if meta else 0
        categoria = meta["categoria"] if meta else "Sin categoría"
        nombre_prod = meta["producto"] if meta else ev.titulo_involucrado

        unidades_cat_mes[categoria][clave] += cant
        ingresos_cat_mes[categoria][clave] += cant * precio
        unidades_prod_cat_mes[categoria][nombre_prod][clave] += cant
        ingresos_prod_cat_mes[categoria][nombre_prod][clave] += cant * precio

        if ev.date_time >= hace_30_dias:
            top_productos[nombre_prod] += cant
            salidas_30d_por_item[clave_item] += cant

        if clave_item not in ultima_salida or ev.date_time > ultima_salida[clave_item]:
            ultima_salida[clave_item] = ev.date_time

    categorias_ordenadas = sorted(
        unidades_cat_mes.keys(),
        key=lambda c: -sum(unidades_cat_mes[c].values()),
    )

    series_categorias = []
    detalle_por_categoria = {}
    for cat in categorias_ordenadas:
        series_categorias.append({
            "categoria": cat,
            "unidades": [unidades_cat_mes[cat][c] for c in claves_meses],
            "ingresos": [ingresos_cat_mes[cat][c] for c in claves_meses],
        })
        prods_cat = sorted(
            unidades_prod_cat_mes[cat].keys(),
            key=lambda p: -sum(unidades_prod_cat_mes[cat][p].values()),
        )
        detalle_por_categoria[cat] = [
            {
                "nombre": prod,
                "unidades": [unidades_prod_cat_mes[cat][prod][c] for c in claves_meses],
                "ingresos": [ingresos_prod_cat_mes[cat][prod][c] for c in claves_meses],
            }
            for prod in prods_cat
        ]

    # 3. Atención de reposición inteligente (incluye campos para el modal resumen)
    por_reponer = []
    for it in items_vendibles:
        clave_item = it.code_sku or it.name_item.lower()
        vendidos_30d = salidas_30d_por_item[clave_item]
        titulo_visible = (it.detail or it.name_item) if it.parent_id else it.name_item

        base_modal = {
            "nombre": titulo_visible,
            "sku": it.code_sku or "",
            "detalle_item": (f"{it.name_item} · {it.detail}" if it.detail else it.name_item) if it.parent_id else (it.detail or "Sin detalle"),
            "precio": it.price,
            "stock": it.stock,
        }

        if it.stock == 0:
            por_reponer.append({
                **base_modal,
                "dias_restantes": 0,
                "estado": "Agotado",
                "detalle": "Sin unidades en inventario",
                "urgente": True,
            })
        elif vendidos_30d > 0:
            venta_diaria = vendidos_30d / 30.0
            dias_restantes = math.floor(it.stock / venta_diaria)
            if dias_restantes <= DIAS_COBERTURA_MINIMA:
                if dias_restantes == 0:
                    estado = "Se acaba hoy"
                elif dias_restantes == 1:
                    estado = "Queda ~1 día"
                else:
                    estado = f"Quedan ~{dias_restantes} días"

                ritmo = round(venta_diaria, 1) if venta_diaria < 10 else round(venta_diaria)
                por_reponer.append({
                    **base_modal,
                    "dias_restantes": dias_restantes,
                    "estado": estado,
                    "detalle": f"{it.stock} unidades en stock (~{ritmo}/día)",
                    "urgente": dias_restantes <= 2,
                })
        elif it.stock <= MINIMO_SIN_HISTORIAL:
            por_reponer.append({
                **base_modal,
                "dias_restantes": 999,
                "estado": "Stock bajo",
                "detalle": f"Solo quedan {it.stock} u.",
                "urgente": False,
            })

    por_reponer.sort(key=lambda x: (x["dias_restantes"], x["stock"], x["nombre"].lower()))

    # 4. Productos estancados
    estancados = []
    for it in items_vendibles:
        if it.stock <= 0:
            continue
        clave_item = it.code_sku or it.name_item.lower()
        fecha_ref = ultima_salida.get(clave_item)
        if fecha_ref is None or fecha_ref < hace_30_dias:
            dias = (ahora - fecha_ref).days if fecha_ref else None
            titulo_visible = (it.detail or it.name_item) if it.parent_id else it.name_item
            estancados.append({
                "nombre": f"{titulo_visible} [{it.code_sku}]" if it.code_sku else titulo_visible,
                "stock": it.stock,
                "valor": it.stock * (it.price or 0),
                "dias": dias,
            })
    estancados.sort(key=lambda x: (x["dias"] is None, -(x["dias"] or 0), -x["stock"]))

    top_5 = sorted(top_productos.items(), key=lambda x: -x[1])[:5]

    return render(request, "accounts/home.html", {
        "dias_cobertura": DIAS_COBERTURA_MINIMA,
        "por_reponer": por_reponer,
        "estancados": estancados[:8],
        "reportes_data": {
            "meses": etiquetas_meses,
            "series": series_categorias,
            "detalleCategorias": detalle_por_categoria,
            "topLabels": [t[0] for t in top_5],
            "topValues": [t[1] for t in top_5],
        },
    })


@solo_anonimos
def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["mail_user"].strip().lower(),
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect("home")
        # Mensaje genérico: no revela si el correo existe o no
        form.add_error(None, "Correo o contraseña incorrectos.")
    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


CAMPOS_PASO_1 = ("name_user", "surname_user", "mail_user", "password", "password2")


@solo_anonimos
def register_view(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            # atomic: o se crean empresa y usuario, o no se crea nada
            with transaction.atomic():
                empresa = Company.objects.create(
                    rut_company=form.rut_numero,
                    dv=form.rut_dv,
                    name_company=d["name_company"],
                )
                User.objects.create_user(
                    d["mail_user"],
                    d["password"],
                    company=empresa,
                    role=Role.objects.get(name_role="Propietario"),
                    name_user=d["name_user"],
                    surname_user=d["surname_user"],
                    is_owner=True,
                )
        except IntegrityError:
            form.add_error(None, "No se pudo completar el registro. Intenta nuevamente.")
        else:
            messages.success(request, "Cuenta creada. Ya puedes iniciar sesión.")
            return redirect("login")

    # Si hubo errores, volver al paso donde está el problema
    paso_inicial = 1
    if form.is_bound and form.errors and not any(c in form.errors for c in CAMPOS_PASO_1):
        paso_inicial = 2
    return render(
        request, "accounts/register.html", {"form": form, "paso_inicial": paso_inicial}
    )


@requiere_permiso("crud_user")
def administracion(request):
    form = TrabajadorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                User.objects.create_user(
                    d["mail_user"],
                    d["password"],
                    company=request.user.company,  # siempre la del dueño logueado
                    role=d["role"],
                    name_user=d["name_user"],
                    surname_user=d["surname_user"],
                    is_owner=False,
                )
        except IntegrityError:
            form.add_error("mail_user", "Este correo ya está registrado.")
        else:
            messages.success(request, f"Usuario {d['mail_user']} agregado.")
            return redirect("administracion")

    roles = list(Role.objects.order_by("id_role"))
    usuarios = (
        User.objects.filter(company=request.user.company)  # solo SU empresa
        .select_related("role")
        .order_by("-is_owner", "name_user", "surname_user")
    )

    # Pestañas: ?rol=<id>. Un valor inválido simplemente se ignora (= "Todos")
    rol_activo = None
    rol_param = request.GET.get("rol", "")
    if rol_param.isdigit():
        rol_activo = next((r for r in roles if r.pk == int(rol_param)), None)
        if rol_activo:
            usuarios = usuarios.filter(role=rol_activo)

    return render(
        request,
        "accounts/administracion.html",
        {
            "usuarios": usuarios,
            "roles": roles,
            "rol_activo": rol_activo,
            "form": form,
            "abrir_form": request.method == "POST",  # reabre la ventana si hubo errores
        },
    )


@require_POST
@requiere_permiso("crud_user")
def eliminar_usuario(request):
    mail = request.POST.get("mail_user", "").strip().lower()
    objetivo = get_object_or_404(
        User,
        mail_user=mail,
        company=request.user.company,  # un usuario ajeno da 404
    )
    correo = objetivo.mail_user  # se guarda antes: delete() deja la clave en None
    if objetivo.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
    elif objetivo.is_owner:
        messages.error(request, "No se puede eliminar al propietario de la empresa.")
    else:
        objetivo.delete()
        messages.success(request, f"Usuario {correo} eliminado.")
    return redirect("administracion")


@require_POST
@requiere_permiso("crud_user")
def cambiar_rol(request):
    form = CambiarRolForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Datos inválidos.")
        return redirect("administracion")
    objetivo = get_object_or_404(
        User,
        mail_user=form.cleaned_data["mail_user"],
        company=request.user.company,
    )
    if objetivo.pk == request.user.pk:
        messages.error(request, "No puedes cambiar tu propio rol.")
    elif objetivo.is_owner:
        messages.error(request, "No se puede cambiar el rol del propietario.")
    else:
        objetivo.role = form.cleaned_data["role"]
        objetivo.save(update_fields=["role"])
        messages.success(request, f"Rol de {objetivo.mail_user} actualizado.")
    return redirect("administracion")


@login_required
def configuracion(request):
    usuario = request.user  # siempre el usuario logueado: nunca se recibe otro desde el navegador
    accion = request.POST.get("accion")

    form_datos = PerfilForm(
        request.POST if accion == "datos" else None,
        initial={"name_user": usuario.name_user, "surname_user": usuario.surname_user},
    )
    form_clave = CambiarClaveForm(usuario, request.POST if accion == "clave" else None)

    if request.method == "POST":
        if accion == "datos" and form_datos.is_valid():
            usuario.name_user = form_datos.cleaned_data["name_user"]
            usuario.surname_user = form_datos.cleaned_data["surname_user"]
            usuario.save(update_fields=["name_user", "surname_user"])
            messages.success(request, "Tus datos fueron actualizados.")
            return redirect("configuracion")
        if accion == "clave" and form_clave.is_valid():
            usuario.set_password(form_clave.cleaned_data["clave_nueva"])  # Argon2
            usuario.save(update_fields=["password"])
            update_session_auth_hash(request, usuario)  # mantiene la sesión abierta
            messages.success(request, "Tu contraseña fue actualizada.")
            return redirect("configuracion")

    return render(
        request,
        "accounts/configuracion.html",
        {"form_datos": form_datos, "form_clave": form_clave},
    )


@require_POST
@login_required
def eliminar_cuenta(request):
    usuario = request.user
    if not usuario.is_owner:
        raise PermissionDenied  # solo el propietario puede borrar la empresa
    if not usuario.check_password(request.POST.get("password", "")):
        messages.error(request, "Contraseña incorrecta. No se eliminó nada.")
        return redirect("configuracion")

    empresa = usuario.company
    with transaction.atomic():
        empresa.delete()  # cascada: usuarios, productos y auditoría de esa empresa
    logout(request)
    messages.success(request, "Tu cuenta y tu empresa fueron eliminadas.")
    return redirect("login")