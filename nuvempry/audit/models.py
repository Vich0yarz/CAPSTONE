from django.db import models


class Audit(models.Model):
    id_audit = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, db_column="rut_company"
    )
    event_type = models.CharField(max_length=32)
    involved = models.CharField(max_length=255)
    move_quantity = models.IntegerField(null=True, blank=True)
    past_count = models.IntegerField(null=True, blank=True)
    date_time = models.DateTimeField(auto_now_add=True)
    user_mail = models.CharField(max_length=255)

    class Meta:
        db_table = "audit"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(past_count__isnull=True)
                | models.Q(past_count__gte=0),
                name="audit_past_count_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "-date_time"], name="idx_audit_company_date"),
        ]