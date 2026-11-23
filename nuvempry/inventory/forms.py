from django import forms
from django.core.validators import RegexValidator

from .models import Item


class EstiloMixin:
    """Agrega las clases de Bootstrap/Nuvempry a todos los campos visibles."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if not campo.widget.is_hidden:
                campo.widget.attrs.setdefault("class", "form-control nv-input")


class ProductoEditarForm(EstiloMixin, forms.Form):
    name_item = forms.CharField(
        label="Nombre", max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Ej: Camisa de algodón"}),
    )
    category = forms.CharField(
        label="Categoría (opcional)", max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej: Ropa"}),
    )
    detail = forms.CharField(
        label="Detalle (opcional)", max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej: 100% algodón"}),
    )
    price = forms.IntegerField(
        label="Precio (opcional, pesos chilenos)", min_value=0, max_value=2_000_000_000,
        required=False, widget=forms.NumberInput(attrs={"placeholder": "Ej: 7990"}),
    )


class ProductoCrearForm(ProductoEditarForm):
    field_order = ["name_item", "stock", "category", "detail", "price"]
    stock = forms.IntegerField(
        label="Stock inicial", min_value=0, max_value=9999,
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 15", "max": 9999}),
    )


class SubproductoEditarForm(EstiloMixin, forms.Form):
    """De un subproducto solo se edita el detalle; lo demás se hereda del original."""
    detail = forms.CharField(label="Detalle (opcional)", max_length=255, required=False)


class SkuForm(EstiloMixin, forms.Form):
    code_sku = forms.CharField(
        label="Código SKU", max_length=64,
        validators=[RegexValidator(r"^[A-Za-z0-9_-]+$",
                                   "Usa solo letras, números, guion y guion bajo.")],
        widget=forms.TextInput(attrs={"placeholder": "Ej: CAM-7K2Q"}),
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
        label="Stock del subproducto", min_value=0, max_value=9999, initial=0,
        widget=forms.NumberInput(attrs={"max": 9999}),
    )
    detail = forms.CharField(label="Detalle (opcional)", max_length=255, required=False)