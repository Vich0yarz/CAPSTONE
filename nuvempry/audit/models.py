import re
from django.db import models

class Audit(models.Model):
    PRODUCT_CREATED = "PRODUCT_CREATED"
    PRODUCT_UPDATED = "PRODUCT_UPDATED"
    PRODUCT_DELETED = "PRODUCT_DELETED"
    SUBPRODUCT_CREATED = "SUBPRODUCT_CREATED"
    SUBPRODUCT_UPDATED = "SUBPRODUCT_UPDATED"
    SUBPRODUCT_DELETED = "SUBPRODUCT_DELETED"
    STOCK_UPDATED = "STOCK_UPDATED"
    SUBPRODUCT_STOCK_UPDATED = "SUBPRODUCT_STOCK_UPDATED"

    EVENTOS = {
        PRODUCT_CREATED: "Producto creado",
        PRODUCT_UPDATED: "Producto editado",
        PRODUCT_DELETED: "Producto eliminado",
        SUBPRODUCT_CREATED: "Subproducto creado",
        SUBPRODUCT_UPDATED: "Subproducto editado",
        SUBPRODUCT_DELETED: "Subproducto eliminado",
        STOCK_UPDATED: "Stock actualizado",
        SUBPRODUCT_STOCK_UPDATED: "Stock actualizado",
    }

    @property
    def evento_legible(self):
        return self.EVENTOS.get(self.event_type, self.event_type)

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

    @property
    def evento_legible(self):
        return self.EVENTOS.get(self.event_type, self.event_type)

    @property
    def detalle_evento(self):
        """Extrae qué campo se editó (ej: 'Nombre', 'Precio') si existe en la segunda línea."""
        lineas = self.involved.split("\n")
        if len(lineas) > 1:
            campos = re.findall(r"(Nombre|Categoría|Detalle|Precio):", lineas[1], flags=re.IGNORECASE)
            if campos:
                return ", ".join(c.capitalize() for c in campos)
        return None

    @property
    def involucrado_limpio(self):
        """Quita el prefijo 'Nombre: ', 'Precio: ', etc. de la segunda línea."""
        lineas = self.involved.split("\n")
        if len(lineas) > 1:
            lineas[1] = re.sub(r"\b(Nombre|Categoría|Detalle|Precio):\s*", "", lineas[1], flags=re.IGNORECASE)
        return "\n".join(lineas)

    @property
    def titulo_involucrado(self):
        """Primera línea de involved (ej: 'Calzones leopardo [CAL-D6JY]')."""
        return self.involved.split("\n")[0].strip()

    @property
    def subtitulo_involucrado(self):
        """Segunda línea limpia (el detalle del cambio), si existe."""
        lineas = self.involucrado_limpio.split("\n")
        return lineas[1].strip() if len(lineas) > 1 else ""

    @property
    def sku_involucrado(self):
        """Extrae el código SKU entre corchetes si existe."""
        m = re.search(r"\[([^\]]+)\]", self.titulo_involucrado)
        return m.group(1) if m else ""

    @property
    def nombre_busqueda(self):
        """Nombre limpio sin el [SKU] ni puntos suspensivos para buscar el Item."""
        nombre = re.sub(r"\s*\[[^\]]+\]$", "", self.titulo_involucrado).strip()
        return nombre[:-3].strip() if nombre.endswith("...") else nombre

    @property
    def stock_legible(self):
        """Devuelve el stock formateado: '10 → 5' al actualizar, '10' al crear/eliminar, o None."""
        if self.event_type in (self.PRODUCT_CREATED, self.SUBPRODUCT_CREATED):
            if self.move_quantity is not None:
                return str(self.move_quantity)
            if self.past_count is not None:
                return str(self.past_count)
            return None

        if self.event_type in (self.PRODUCT_DELETED, self.SUBPRODUCT_DELETED):
            return str(self.past_count) if self.past_count is not None else None

        if self.event_type in (self.STOCK_UPDATED, self.SUBPRODUCT_STOCK_UPDATED):
            if self.past_count is not None and self.move_quantity is not None:
                nuevo = self.past_count + self.move_quantity
                return f"{self.past_count} → {nuevo}"

        return None