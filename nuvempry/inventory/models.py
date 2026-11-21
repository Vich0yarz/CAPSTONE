from django.db import models


class Item(models.Model):
    id_item = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, db_column="rut_company"
    )
    # Si no es nulo, este registro es un SUBPRODUCTO del producto indicado
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE,
        related_name="subproducts", db_column="id_parent",
    )
    name_item = models.CharField(max_length=255)
    stock = models.IntegerField()
    category = models.CharField(max_length=255, null=True, blank=True)
    detail = models.CharField(max_length=255, null=True, blank=True)
    code_sku = models.CharField(max_length=255, null=True, blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)  # pesos chilenos, entero

    class Meta:
        db_table = "item"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock__gte=0), name="item_stock_gte_0"
            ),
            models.UniqueConstraint(
                fields=["company", "code_sku"], name="uq_item_company_sku"
            ),
        ]

    def __str__(self):
        return f"{self.name_item} ({self.pk})"