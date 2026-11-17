from django.db import models


class Item(models.Model):
    id_item = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, db_column="rut_company"
    )
    name_item = models.CharField(max_length=255)
    stock = models.IntegerField()
    category = models.CharField(max_length=255, null=True, blank=True)
    detail = models.CharField(max_length=255, null=True, blank=True)
    code_sku = models.CharField(max_length=255, null=True, blank=True)

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