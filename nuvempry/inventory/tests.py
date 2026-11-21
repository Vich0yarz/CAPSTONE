from unittest import mock

from django.urls import reverse

from accounts.tests_views import Base
from audit.models import Audit

from .models import Item


class InventarioBase(Base):
    def setUp(self):
        self.dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.empresa = self.dueno.company
        self.client.force_login(self.dueno)

    def producto(self, nombre="Camisa", stock=10, empresa=None, **extra):
        return Item.objects.create(
            company=empresa or self.empresa, name_item=nombre, stock=stock, **extra
        )

    def sub(self, padre, sku="CAM-0001", stock=3, **extra):
        return Item.objects.create(
            company=padre.company, parent=padre, name_item=padre.name_item,
            category=padre.category, price=padre.price, stock=stock, code_sku=sku, **extra
        )


class CrearProductoTests(InventarioBase):
    def test_crea_con_datos_obligatorios_y_audita(self):
        r = self.client.post(reverse("inventario"), {"name_item": "Camisa", "stock": 10})
        self.assertRedirects(r, reverse("inventario"))
        p = Item.objects.get(name_item="Camisa")
        self.assertEqual((p.company, p.stock, p.category, p.detail, p.price),
                         (self.empresa, 10, None, None, None))
        a = Audit.objects.get()
        self.assertEqual(a.event_type, Audit.PRODUCT_CREATED)
        self.assertEqual((a.move_quantity, a.past_count, a.user_mail, a.company),
                         (10, 0, "dueno@a.cl", self.empresa))

    def test_crea_con_opcionales_y_precio(self):
        self.client.post(reverse("inventario"), {
            "name_item": "Polera", "stock": 5, "category": "Ropa",
            "detail": "Algodón", "price": 7990,
        })
        p = Item.objects.get(name_item="Polera")
        self.assertEqual((p.category, p.detail, p.price), ("Ropa", "Algodón", 7990))

    def test_rechaza_datos_invalidos(self):
        invalidos = [
            {"name_item": "X", "stock": -1},
            {"name_item": "X", "stock": 1, "price": -5},
            {"name_item": "X", "stock": 1, "price": "abc"},
            {"name_item": "X", "stock": 1, "price": "10.5"},
            {"name_item": "X", "stock": 1, "price": 3_000_000_000},
            {"name_item": "", "stock": 1},
            {"name_item": "X"},
        ]
        for datos in invalidos:
            r = self.client.post(reverse("inventario"), datos)
            self.assertEqual(r.status_code, 200, datos)
        self.assertFalse(Item.objects.exists())
        self.assertFalse(Audit.objects.exists())

    def test_si_falla_la_auditoria_no_se_crea_el_producto(self):
        with mock.patch("inventory.services._registrar", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("inventario"), {"name_item": "X", "stock": 1})
        self.assertFalse(Item.objects.exists())


class PermisosTests(InventarioBase):
    def test_sin_sesion_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse("inventario"))
        self.assertRedirects(r, reverse("login") + "?next=" + reverse("inventario"))

    def test_operativo_y_lector_consultan_pero_no_modifican(self):
        p = self.producto()
        for rol in ("Operativo", "Lector"):
            self.client.force_login(self.crear(f"{rol.lower()}@a.cl", rol))
            self.assertEqual(self.client.get(reverse("inventario")).status_code, 200)
            r = self.client.post(reverse("inventario"), {"name_item": "Z", "stock": 1})
            self.assertEqual(r.status_code, 403)
            self.assertEqual(self.client.get(reverse("editar_producto", args=[p.pk])).status_code, 403)
            self.assertEqual(self.client.post(reverse("eliminar_producto", args=[p.pk])).status_code, 403)
            self.assertEqual(self.client.get(reverse("subproducto_nuevo", args=[p.pk])).status_code, 403)
        self.assertEqual(Item.objects.count(), 1)
        self.assertFalse(Audit.objects.exists())


class AislamientoTests(InventarioBase):
    def test_listado_y_acceso_cruzado(self):
        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        ajeno_item = self.producto("Secreto", empresa=ajeno.company)
        self.assertNotContains(self.client.get(reverse("inventario")), "Secreto")
        self.assertEqual(self.client.get(reverse("editar_producto", args=[ajeno_item.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("eliminar_producto", args=[ajeno_item.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("subproducto_nuevo", args=[ajeno_item.pk])).status_code, 404)
        self.assertTrue(Item.objects.filter(pk=ajeno_item.pk).exists())


class EditarTests(InventarioBase):
    def test_edicion_registra_auditoria_con_los_cambios(self):
        p = self.producto("Camisa", price=1000)
        r = self.client.post(reverse("editar_producto", args=[p.pk]), {
            "name_item": "Camisa roja", "category": "Ropa", "detail": "", "price": 1500,
        })
        self.assertRedirects(r, reverse("inventario"))
        p.refresh_from_db()
        self.assertEqual((p.name_item, p.category, p.price), ("Camisa roja", "Ropa", 1500))
        a = Audit.objects.get()
        self.assertEqual(a.event_type, Audit.PRODUCT_UPDATED)
        self.assertIn("nombre", a.involved)
        self.assertIn("precio", a.involved)
        self.assertEqual(a.user_mail, "dueno@a.cl")

    def test_sin_cambios_no_genera_auditoria(self):
        p = self.producto("Camisa", category="Ropa", price=1000)
        self.client.post(reverse("editar_producto", args=[p.pk]), {
            "name_item": "Camisa", "category": "Ropa", "detail": "", "price": 1000,
        })
        self.assertFalse(Audit.objects.exists())

    def test_el_stock_no_se_edita_desde_aqui(self):
        p = self.producto(stock=10)
        self.client.post(reverse("editar_producto", args=[p.pk]), {"name_item": "Camisa", "stock": 999})
        p.refresh_from_db()
        self.assertEqual(p.stock, 10)


class SubproductoTests(InventarioBase):
    def test_flujo_en_dos_pasos(self):
        padre = self.producto("Camisa", price=1000, category="Ropa")
        url = reverse("subproducto_nuevo", args=[padre.pk])
        r = self.client.post(url, {"accion": "continuar", "code_sku": "cam-0001"})
        self.assertEqual(r.context["paso"], 2)
        self.assertContains(r, "CAM-0001")  # normalizado a mayúsculas
        r = self.client.post(url, {"accion": "crear", "code_sku": "CAM-0001",
                                   "stock": 3, "detail": "Talla M"})
        self.assertRedirects(r, reverse("inventario"))
        s = Item.objects.get(code_sku="CAM-0001")
        self.assertEqual((s.parent, s.name_item, s.category, s.price, s.stock, s.detail),
                         (padre, "Camisa", "Ropa", 1000, 3, "Talla M"))
        a = Audit.objects.get(event_type=Audit.SUBPRODUCT_CREATED)
        self.assertEqual((a.move_quantity, a.past_count), (3, 0))

    def test_generar_sku(self):
        padre = self.producto("Camisa")
        r = self.client.post(reverse("subproducto_nuevo", args=[padre.pk]), {"accion": "generar"})
        self.assertRegex(r.context["form1"].initial["code_sku"], r"^CAM-[A-Z0-9]{4}$")

    def test_sku_duplicado_en_la_empresa_se_rechaza(self):
        padre = self.producto("Camisa")
        self.sub(padre, sku="CAM-0001")
        url = reverse("subproducto_nuevo", args=[padre.pk])
        r = self.client.post(url, {"accion": "continuar", "code_sku": "CAM-0001"})
        self.assertEqual(r.context["paso"], 1)
        r = self.client.post(url, {"accion": "crear", "code_sku": "CAM-0001", "stock": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Item.objects.filter(code_sku="CAM-0001").count(), 1)

    def test_mismo_sku_en_otra_empresa_si_se_permite(self):
        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        self.sub(self.producto("Camisa", empresa=ajeno.company))
        padre = self.producto("Camisa")
        r = self.client.post(reverse("subproducto_nuevo", args=[padre.pk]),
                             {"accion": "crear", "code_sku": "CAM-0001", "stock": 1})
        self.assertRedirects(r, reverse("inventario"))

    def test_no_existen_subproductos_de_subproductos(self):
        s = self.sub(self.producto("Camisa"))
        self.assertEqual(self.client.get(reverse("subproducto_nuevo", args=[s.pk])).status_code, 404)

    def test_cambios_del_padre_se_propagan_y_se_auditan(self):
        padre = self.producto("Camisa", price=1000)
        s = self.sub(padre)
        self.client.post(reverse("editar_producto", args=[padre.pk]), {
            "name_item": "Camisa azul", "category": "", "detail": "", "price": 1200,
        })
        s.refresh_from_db()
        self.assertEqual((s.name_item, s.price), ("Camisa azul", 1200))
        self.assertEqual(Audit.objects.filter(event_type=Audit.PRODUCT_UPDATED).count(), 1)
        self.assertEqual(Audit.objects.filter(event_type=Audit.SUBPRODUCT_UPDATED).count(), 1)

    def test_el_subproducto_solo_edita_su_detalle(self):
        padre = self.producto("Camisa", price=1000)
        s = self.sub(padre)
        self.client.post(reverse("editar_producto", args=[s.pk]),
                         {"detail": "Talla L", "name_item": "Hackeado", "price": 1})
        s.refresh_from_db()
        self.assertEqual((s.detail, s.name_item, s.price), ("Talla L", "Camisa", 1000))
        self.assertEqual(Audit.objects.get().event_type, Audit.SUBPRODUCT_UPDATED)


class EliminarTests(InventarioBase):
    def test_elimina_y_audita(self):
        p = self.producto(stock=7)
        r = self.client.post(reverse("eliminar_producto", args=[p.pk]))
        self.assertRedirects(r, reverse("inventario"))
        self.assertFalse(Item.objects.exists())
        a = Audit.objects.get()
        self.assertEqual((a.event_type, a.move_quantity, a.past_count),
                         (Audit.PRODUCT_DELETED, -7, 7))

    def test_eliminar_el_padre_elimina_subproductos_y_audita_cada_uno(self):
        padre = self.producto(stock=7)
        self.sub(padre, stock=2)
        self.client.post(reverse("eliminar_producto", args=[padre.pk]))
        self.assertFalse(Item.objects.exists())
        self.assertEqual(Audit.objects.filter(event_type=Audit.PRODUCT_DELETED).count(), 1)
        e = Audit.objects.get(event_type=Audit.SUBPRODUCT_DELETED)
        self.assertEqual((e.move_quantity, e.past_count), (-2, 2))

    def test_eliminar_un_subproducto_no_toca_al_padre(self):
        padre = self.producto()
        s = self.sub(padre)
        self.client.post(reverse("eliminar_producto", args=[s.pk]))
        self.assertTrue(Item.objects.filter(pk=padre.pk).exists())
        self.assertFalse(Item.objects.filter(pk=s.pk).exists())


class AuditoriaTests(InventarioBase):
    def test_solo_el_propietario_ve_la_auditoria_de_su_empresa(self):
        self.client.post(reverse("inventario"), {"name_item": "Camisa", "stock": 4})
        ajeno = self.crear("otro@b.cl", "Propietario", rut=22222222, dv="2", owner=True)
        Audit.objects.create(company=ajeno.company, event_type=Audit.PRODUCT_CREATED,
                             involved="Secreto", user_mail="otro@b.cl")
        r = self.client.get(reverse("auditoria"))
        self.assertContains(r, "Camisa")
        self.assertNotContains(r, "Secreto")

        self.client.force_login(self.crear("op@a.cl", "Operativo"))
        self.assertEqual(self.client.get(reverse("auditoria")).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("auditoria")), reverse("login"))