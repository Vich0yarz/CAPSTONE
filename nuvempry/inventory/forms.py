from django import forms
from django.core.validators import RegexValidator

from .models import Item


class ProductoEditarForm(forms.Form):
    name_item = forms.CharField(label="Nombre", max_length=255)
    category = forms.CharField(label="Categoría (opcional)", max_length=255, required=False)
    detail = forms.CharField(label="Detalle (opcional)", max_length=255, required=False)
    price = forms.IntegerField(
        label="Precio (opcional, pesos chilenos, número entero)",
        min_value=0, max_value=2_000_000_000, required=False,
    )


class ProductoCrearForm(ProductoEditarForm):
    field_order = ["name_item", "stock", "category", "detail", "price"]
    stock = forms.IntegerField(label="Stock inicial", min_value=0, max_value=1_000_000_000)


class SubproductoEditarForm(forms.Form):
    """De un subproducto solo se edita el detalle; lo demás se hereda del original."""
    detail = forms.CharField(label="Detalle (opcional)", max_length=255, required=False)


class SkuForm(forms.Form):
    code_sku = forms.CharField(
        label="Código SKU", max_length=64,
        validators=[RegexValidator(r"^[A-Za-z0-9_-]+$",
                                   "Usa solo letras, números, guion y guion bajo.")],
    )

    def __init__(self, empresa, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

    def clean_code_sku(self):
        sku = self.cleaned_data["code_sku"].strip().upper()
        if Item.objects.filter(company=self.empresa, code_sku=sku).exists():
            raise forms.ValidationError("Ese código SKU ya existe en tu empresa.")
        return sku


class SubproductoCrearForm(SkuForm):
    stock = forms.IntegerField(
        label="Stock del subproducto", min_value=0, max_value=1_000_000_000, initial=0
    )
    detail = forms.CharField(label="Detalle (opcional)", max_length=255, required=False)