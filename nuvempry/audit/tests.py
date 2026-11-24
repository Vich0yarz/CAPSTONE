from django.urls import reverse

from accounts.tests_views import Base
from inventory.models import Item

from .models import Audit


class AuditBase(Base):
    def setUp(self):
        self.dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.empresa = self.dueno.company
        self.client.force_login(self.dueno)

    def registrar(self, evento=Audit.PRODUCT_CREATED, involved="Camisa",
                  cantidad=10, previo=0, empresa=None, mail="dueno@a.cl"):
        return Audit.objects.create(
            company=empresa or self.empresa,
            event_type=evento,
            involved=involved,
            move_quantity=cantidad,
            past_count=previo,
            user_mail=mail,
        )


class AuditModelPropertiesTests(AuditBase):
    def test_evento_legible(self):
        a = self.registrar(evento=Audit.SUBPRODUCT_STOCK_UPDATED)
        self.assertEqual(a.evento_legible, "Stock actualizado")

        desconocido = self.registrar(evento="CUSTOM_EVENT")
        self.assertEqual(desconocido.evento_legible, "CUSTOM_EVENT")

    def test_titulo_subtitulo_sku_y_nombre_busqueda(self):
        a = self.registrar(
            evento=Audit.SUBPRODUCT_UPDATED,
            involved="Calzones leopardo [CAL-D6JY]\nDetalle: Talla M → Talla L",
        )
        self.assertEqual(a.titulo_involucrado, "Calzones leopardo [CAL-D6JY]")
        self.assertEqual(a.sku_involucrado, "CAL-D6JY")
        self.assertEqual(a.nombre_busqueda, "Calzones leopardo")
        self.assertEqual(a.detalle_evento, "Detalle")
        self.assertEqual(a.subtitulo_involucrado, "Talla M → Talla L")

    def test_nombre_truncado_con_puntos_suspensivos(self):
        a = self.registrar(involved="Nombre muy largo... [SKU-01]")
        self.assertEqual(a.sku_involucrado, "SKU-01")
        self.assertEqual(a.nombre_busqueda, "Nombre muy largo")

    def test_stock_legible_segun_tipo_evento(self):
        creado = self.registrar(evento=Audit.PRODUCT_CREATED, cantidad=15, previo=0)
        self.assertEqual(creado.stock_legible, "15")

        sub_creado = self.registrar(evento=Audit.SUBPRODUCT_CREATED, cantidad=4, previo=0)
        self.assertEqual(sub_creado.stock_legible, "4")

        eliminado = self.registrar(evento=Audit.PRODUCT_DELETED, cantidad=-7, previo=7)
        self.assertEqual(eliminado.stock_legible, "7")

        actualizado = self.registrar(evento=Audit.STOCK_UPDATED, cantidad=-5, previo=10)
        self.assertEqual(actualizado.stock_legible, "10 → 5")

        sub_actualizado = self.registrar(evento=Audit.SUBPRODUCT_STOCK_UPDATED, cantidad=8, previo=2)
        self.assertEqual(sub_actualizado.stock_legible, "2 → 10")

        editado = self.registrar(evento=Audit.PRODUCT_UPDATED, cantidad=None, previo=None)
        self.assertIsNone(editado.stock_legible)


class AuditoriaVistaTests(AuditBase):
    def test_lista_eventos_de_su_empresa_ordenados_y_con_limite_200(self):
        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        self.registrar(involved="Producto Ajeno", empresa=ajeno.company)

        for i in range(205):
            self.registrar(involved=f"Item {i}")

        r = self.client.get(reverse("auditoria"))
        self.assertEqual(r.status_code, 200)
        eventos = list(r.context["eventos"])
        self.assertEqual(len(eventos), 200)
        self.assertEqual(eventos[0].involved, "Item 204")
        self.assertNotContains(r, "Producto Ajeno")

    def test_permisos_y_sesion(self):
        for rol in ("Operativo", "Lector"):
            self.client.force_login(self.crear(f"{rol.lower()}@a.cl", rol))
            self.assertEqual(self.client.get(reverse("auditoria")).status_code, 403)

        self.client.logout()
        r = self.client.get(reverse("auditoria"))
        self.assertRedirects(r, reverse("login"))


class DetalleItemAuditoriaTests(AuditBase):
    def test_encuentra_subproducto_por_sku(self):
        padre = Item.objects.create(company=self.empresa, name_item="Camisa", stock=3)
        sub = Item.objects.create(
            company=self.empresa, parent=padre, name_item="Camisa",
            stock=3, code_sku="CAM-0001",
        )
        reg = self.registrar(involved="Camisa [CAM-0001]")

        r = self.client.get(reverse("auditoria_item_detalle", args=[reg.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["item"], sub)

    def test_encuentra_producto_por_nombre_exacto_y_truncado(self):
        p_corto = Item.objects.create(company=self.empresa, name_item="Polera", stock=5)
        p_largo = Item.objects.create(
            company=self.empresa, name_item="Pantalón de gabardina azul marino", stock=2
        )

        reg_corto = self.registrar(involved="Polera")
        r1 = self.client.get(reverse("auditoria_item_detalle", args=[reg_corto.pk]))
        self.assertEqual(r1.context["item"], p_corto)

        reg_largo = self.registrar(involved="Pantalón de gabar...")
        r2 = self.client.get(reverse("auditoria_item_detalle", args=[reg_largo.pk]))
        self.assertEqual(r2.context["item"], p_largo)

    def test_item_eliminado_devuelve_item_none_sin_fallar(self):
        reg = self.registrar(evento=Audit.PRODUCT_DELETED, involved="Fantasma", cantidad=-1, previo=1)
        r = self.client.get(reverse("auditoria_item_detalle", args=[reg.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["item"])

    def test_permisos_y_aislamiento_en_detalle(self):
        reg = self.registrar(involved="Camisa")

        # Operativo y Lector reciben 403 (con el @requiere_permiso("crud_user") corregido)
        for rol in ("Operativo", "Lector"):
            self.client.force_login(self.crear(f"{rol.lower()}@a.cl", rol))
            self.assertEqual(
                self.client.get(reverse("auditoria_item_detalle", args=[reg.pk])).status_code,
                403,
            )

        # Dueño de otra empresa recibe 404
        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        self.client.force_login(ajeno)
        self.assertEqual(
            self.client.get(reverse("auditoria_item_detalle", args=[reg.pk])).status_code,
            404,
        )