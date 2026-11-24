from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (CambiarClaveForm, CambiarRolForm, LoginForm, PerfilForm,
                    RegisterForm, TrabajadorForm)
from .models import Company, Role, User
from .permisos import requiere_permiso, solo_anonimos


@login_required
def home(request):
    return render(request, "accounts/home.html")


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