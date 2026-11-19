import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Company, Role, User


def calcular_dv(numero):
    """Dígito verificador del RUT chileno (módulo 11)."""
    suma, mult = 0, 2
    for digito in reversed(str(numero)):
        suma += int(digito) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def parsear_rut(texto):
    """'12.345.678-5' -> (12345678, '5'). Lanza ValidationError si es inválido."""
    limpio = texto.replace(".", "").replace(" ", "").upper()
    if not re.fullmatch(r"\d{7,8}-[0-9K]", limpio):
        raise ValidationError("Formato inválido. Usa el formato 12345678-5.")
    numero_txt, dv = limpio.split("-")
    numero = int(numero_txt)
    if numero < 1_000_000:
        raise ValidationError("El RUT ingresado no es válido.")
    if calcular_dv(numero) != dv:
        raise ValidationError("El dígito verificador no corresponde al RUT.")
    return numero, dv


def _attrs(placeholder, icono=False, **extra):
    """Atributos HTML comunes: clases de Bootstrap/Nuvempry y placeholder."""
    clase = "form-control nv-input" + (" con-icono" if icono else "")
    return {"class": clase, "placeholder": placeholder, **extra}


class LoginForm(forms.Form):
    mail_user = forms.EmailField(
        label="Correo electrónico", max_length=255,
        widget=forms.EmailInput(attrs=_attrs("nombre@correo.com", icono=True, autocomplete="email")),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs=_attrs("Tu contraseña", icono=True, autocomplete="current-password")),
    )


class FormConClave(forms.Form):
    """Campos y validaciones comunes a Register y a Agregar usuario."""

    name_user = forms.CharField(
        label="Nombres", max_length=100,
        widget=forms.TextInput(attrs=_attrs("Ej: María José")),
    )
    surname_user = forms.CharField(
        label="Apellidos", max_length=100,
        widget=forms.TextInput(attrs=_attrs("Ej: González Pérez")),
    )
    mail_user = forms.EmailField(
        label="Correo electrónico", max_length=255,
        widget=forms.EmailInput(attrs=_attrs("Ej: maria.gonzalez@correo.cl", autocomplete="off")),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs=_attrs("Mínimo 8 caracteres", autocomplete="new-password")),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs=_attrs("Repite tu contraseña", autocomplete="new-password")),
    )

    def clean_mail_user(self):
        mail = self.cleaned_data["mail_user"].strip().lower()
        if User.objects.filter(mail_user=mail).exists():
            raise ValidationError("Este correo ya está registrado.")
        return mail

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)  # largo mínimo, clave común, solo números
        return password

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return datos


class RegisterForm(FormConClave):
    rut_company = forms.CharField(
        label="RUT", max_length=12,
        widget=forms.TextInput(attrs=_attrs("Ej: 12.345.678-5")),
    )
    name_company = forms.CharField(
        label="Nombre de tu empresa", max_length=50,
        widget=forms.TextInput(attrs=_attrs("Ej: Mi Tienda")),
    )

    def clean_rut_company(self):
        numero, dv = parsear_rut(self.cleaned_data["rut_company"])
        if Company.objects.filter(rut_company=numero).exists():
            raise ValidationError("Esta empresa ya está registrada.")
        self.rut_numero, self.rut_dv = numero, dv  # las dos variables separadas
        return self.cleaned_data["rut_company"]


class TrabajadorForm(FormConClave):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(), label="Rol", empty_label="Selecciona un rol",
        widget=forms.Select(attrs={"class": "form-select nv-input"}),
    )


class CambiarRolForm(forms.Form):
    mail_user = forms.EmailField()
    role = forms.ModelChoiceField(queryset=Role.objects.all())

class PerfilForm(forms.Form):
    name_user = forms.CharField(
        label="Nombres", max_length=100,
        widget=forms.TextInput(attrs=_attrs("Ej: María José")),
    )
    surname_user = forms.CharField(
        label="Apellidos", max_length=100,
        widget=forms.TextInput(attrs=_attrs("Ej: González Pérez")),
    )


class CambiarClaveForm(forms.Form):
    clave_actual = forms.CharField(
        label="Contraseña actual",
        widget=forms.PasswordInput(attrs=_attrs("Tu contraseña actual", autocomplete="current-password")),
    )
    clave_nueva = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs=_attrs("Mínimo 8 caracteres", autocomplete="new-password")),
    )
    clave_nueva2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs=_attrs("Repite la nueva contraseña", autocomplete="new-password")),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_clave_actual(self):
        clave = self.cleaned_data["clave_actual"]
        if not self.user.check_password(clave):
            raise ValidationError("La contraseña actual no es correcta.")
        return clave

    def clean_clave_nueva(self):
        clave = self.cleaned_data["clave_nueva"]
        validate_password(clave, self.user)
        return clave

    def clean(self):
        datos = super().clean()
        n1, n2 = datos.get("clave_nueva"), datos.get("clave_nueva2")
        if n1 and n2 and n1 != n2:
            self.add_error("clave_nueva2", "Las contraseñas no coinciden.")
        return datos