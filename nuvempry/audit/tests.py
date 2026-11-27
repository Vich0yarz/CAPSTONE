from django.urls import reverse

from accounts.tests_views import Base
from inventory.models import Item

from .models import Audit
from .views import LOTE_AUDITORIA


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
    def test_lista_eventos_por_lotes_y_total_empresa(self):
        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        self.registrar(involved="Producto Ajeno", empresa=ajeno.company)

        total_creados = 60
        for i in range(total_creados):
            self.registrar(involved=f"Item {i}")

        r = self.client.get(reverse("auditoria"))
        self.assertEqual(r.status_code, 200)
        eventos = list(r.context["eventos"])
        self.assertEqual(len(eventos), LOTE_AUDITORIA)
        self.assertEqual(eventos[0].involved, f"Item {total_creados - 1}")
        self.assertEqual(r.context["total_empresa"], total_creados)
        self.assertTrue(r.context["hay_mas"])
        self.assertEqual(r.context["siguiente_offset"], LOTE_AUDITORIA)
        self.assertNotContains(r, "Producto Ajeno")

    def test_carga_parcial_scroll_infinito(self):
        total_creados = LOTE_AUDITORIA + 10
        for i in range(total_creados):
            self.registrar(involved=f"Item {i}")

        # Segundo lote (offset=25)
        r = self.client.get(reverse("auditoria"), {"parcial": "1", "offset": LOTE_AUDITORIA})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Has-More"], "0")
        self.assertEqual(r.headers["X-Next-Offset"], str(total_creados))
        self.assertContains(r, "Item 0")
        self.assertNotContains(r, f"Item {total_creados - 1}")

    def test_filtros_busqueda_evento_y_usuario(self):
        self.registrar(evento=Audit.PRODUCT_CREATED, involved="Polera Roja [POL-1]", mail="uno@a.cl")
        self.registrar(evento=Audit.PRODUCT_UPDATED, involved="Pantalón Azul [PAN-2]\nPrecio: 1000 → 1500", mail="dos@a.cl")
        self.registrar(evento=Audit.SUBPRODUCT_STOCK_UPDATED, involved="Polera Roja [POL-1]", cantidad=5, previo=2, mail="uno@a.cl")

        # Búsqueda por texto (SKU / nombre)
        r_q = self.client.get(reverse("auditoria"), {"q": "PAN-2"})
        self.assertEqual(len(r_q.context["eventos"]), 1)
        self.assertEqual(r_q.context["total_empresa"], 3)

        # Filtro por tipo de evento (STOCK_UPDATED incluye subproductos)
        r_ev = self.client.get(reverse("auditoria"), {"evento": "STOCK_UPDATED"})
        self.assertEqual(len(r_ev.context["eventos"]), 1)
        self.assertEqual(r_ev.context["eventos"][0].event_type, Audit.SUBPRODUCT_STOCK_UPDATED)

        # Filtro por usuario
        r_usr = self.client.get(reverse("auditoria"), {"usuario": "dos@a.cl"})
        self.assertEqual(len(r_usr.context["eventos"]), 1)
        self.assertEqual(r_usr.context["eventos"][0].user_mail, "dos@a.cl")

    def test_ordenamiento_por_fecha_y_stock_final(self):
        self.registrar(evento=Audit.PRODUCT_CREATED, involved="Primero", cantidad=10, previo=0)
        self.registrar(evento=Audit.STOCK_UPDATED, involved="Segundo", cantidad=-7, previo=10)  # stock_final = 3
        self.registrar(evento=Audit.PRODUCT_UPDATED, involved="SinStock", cantidad=None, previo=None)  # stock_final = None

        # Fecha ascendente
        r_fecha_asc = self.client.get(reverse("auditoria"), {"orden": "fecha", "dir": "asc"})
        nombres_fecha = [e.involved for e in r_fecha_asc.context["eventos"]]
        self.assertEqual(nombres_fecha, ["Primero", "Segundo", "SinStock"])

        # Stock final ascendente (nulls al final)
        r_stock_asc = self.client.get(reverse("auditoria"), {"orden": "stock", "dir": "asc"})
        nombres_stock = [e.involved for e in r_stock_asc.context["eventos"]]
        self.assertEqual(nombres_stock, ["Segundo", "Primero", "SinStock"])

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

        for rol in ("Operativo", "Lector"):
            self.client.force_login(self.crear(f"{rol.lower()}@a.cl", rol))
            self.assertEqual(
                self.client.get(reverse("auditoria_item_detalle", args=[reg.pk])).status_code,
                403,
            )

        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        self.client.force_login(ajeno)
        self.assertEqual(
            self.client.get(reverse("auditoria_item_detalle", args=[reg.pk])).status_code,
            404,
        )