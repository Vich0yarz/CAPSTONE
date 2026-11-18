from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CambiarRolForm, LoginForm, RegisterForm, TrabajadorForm
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
    return render(request, "accounts/register.html", {"form": form})


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
            messages.success(request, f"Trabajador {d['mail_user']} agregado.")
            return redirect("administracion")

    usuarios = (
        User.objects.filter(company=request.user.company)
        .select_related("role")
        .order_by("mail_user")
    )
    roles = Role.objects.order_by("id_role")
    return render(
        request,
        "accounts/administracion.html",
        {
            "usuarios": usuarios,
            "roles": roles,
            "form": form,
            "abrir_form": request.method == "POST",
        },
    )


@require_POST
@requiere_permiso("crud_user")
def eliminar_usuario(request):
    objetivo = get_object_or_404(
        User,
        mail_user=request.POST.get("mail_user", ""),
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