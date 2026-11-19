from django.test import TestCase
from django.urls import reverse

from accounts.models import Company, Role, User
from inventory.models import Item

CLAVE = "ClaveSegura123!"


class Base(TestCase):
    def crear(self, mail, rol, rut=11111111, dv="1", owner=False):
        empresa, _ = Company.objects.get_or_create(
            rut_company=rut, defaults={"dv": dv, "name_company": f"Empresa {rut}"}
        )
        return User.objects.create_user(
            mail, CLAVE, company=empresa, role=Role.objects.get(name_role=rol),
            name_user="N", surname_user="S", is_owner=owner,
        )


class AccesoTests(Base):
    def test_anonimo_no_entra_a_administracion(self):
        r = self.client.get(reverse("administracion"))
        self.assertRedirects(r, reverse("login"))

    def test_operativo_recibe_403(self):
        self.client.force_login(self.crear("op@a.cl", "Operativo"))
        self.assertEqual(self.client.get(reverse("administracion")).status_code, 403)

    def test_logueado_no_entra_a_login_ni_register(self):
        self.client.force_login(self.crear("op@a.cl", "Operativo"))
        for nombre in ("login", "register"):
            self.assertRedirects(self.client.get(reverse(nombre)), reverse("home"))

    def test_lista_solo_su_empresa(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("emp@a.cl", "Operativo")
        self.crear("otro@b.cl", "Operativo", rut=22222222, dv="2")
        self.client.force_login(dueno)
        r = self.client.get(reverse("administracion"))
        self.assertContains(r, "emp@a.cl")
        self.assertNotContains(r, "otro@b.cl")

    def test_filtro_por_rol(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("emp@a.cl", "Operativo")
        self.crear("lec@a.cl", "Lector")
        self.client.force_login(dueno)
        operativo = Role.objects.get(name_role="Operativo")
        r = self.client.get(reverse("administracion"), {"rol": operativo.pk})
        self.assertContains(r, "emp@a.cl")
        self.assertNotContains(r, "lec@a.cl")

    def test_filtro_invalido_se_ignora(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("emp@a.cl", "Operativo")
        self.client.force_login(dueno)
        r = self.client.get(reverse("administracion"), {"rol": "abc"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "emp@a.cl")


class ManipulacionTests(Base):
    def test_operativo_no_puede_eliminar_ni_con_post_manual(self):
        op = self.crear("op@a.cl", "Operativo")
        self.crear("emp@a.cl", "Lector")
        self.client.force_login(op)
        r = self.client.post(reverse("eliminar_usuario"), {"mail_user": "emp@a.cl"})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.filter(pk="emp@a.cl").exists())

    def test_no_se_elimina_usuario_de_otra_empresa(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("otro@b.cl", "Operativo", rut=22222222, dv="2")
        self.client.force_login(dueno)
        r = self.client.post(reverse("eliminar_usuario"), {"mail_user": "otro@b.cl"})
        self.assertEqual(r.status_code, 404)
        self.assertTrue(User.objects.filter(pk="otro@b.cl").exists())

    def test_no_se_cambia_rol_de_otra_empresa(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        ajeno = self.crear("otro@b.cl", "Lector", rut=22222222, dv="2")
        self.client.force_login(dueno)
        propietario = Role.objects.get(name_role="Propietario")
        r = self.client.post(
            reverse("cambiar_rol"), {"mail_user": "otro@b.cl", "role": propietario.pk}
        )
        self.assertEqual(r.status_code, 404)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.role.name_role, "Lector")

    def test_no_se_elimina_al_dueno(self):
        self.crear("dueno@a.cl", "Propietario", owner=True)
        socio = self.crear("socio@a.cl", "Propietario")
        self.client.force_login(socio)
        self.client.post(reverse("eliminar_usuario"), {"mail_user": "dueno@a.cl"})
        self.assertTrue(User.objects.filter(pk="dueno@a.cl").exists())

    def test_dueno_cambia_rol_de_su_empleado(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        emp = self.crear("emp@a.cl", "Lector")
        self.client.force_login(dueno)
        operativo = Role.objects.get(name_role="Operativo")
        self.client.post(reverse("cambiar_rol"), {"mail_user": "emp@a.cl", "role": operativo.pk})
        emp.refresh_from_db()
        self.assertEqual(emp.role.name_role, "Operativo")


class LoginRegistroTests(Base):
    datos = {
        "mail_user": "nuevo@x.cl", "password": CLAVE, "password2": CLAVE,
        "name_user": "Ana", "surname_user": "Pérez", "rut_company": "12.345.678-5",
        "name_company": "Demo SpA",
    }

    def test_registro_valido_crea_empresa_y_propietario(self):
        r = self.client.post(reverse("register"), self.datos)
        self.assertRedirects(r, reverse("login"))
        u = User.objects.get(pk="nuevo@x.cl")
        self.assertTrue(u.is_owner)
        self.assertEqual(u.role.name_role, "Propietario")
        self.assertEqual((u.company.rut_company, u.company.dv), (12345678, "5"))

    def test_dv_incorrecto_no_crea_nada(self):
        r = self.client.post(reverse("register"), {**self.datos, "rut_company": "12345678-9"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Company.objects.exists())

    def test_login_correcto_e_incorrecto(self):
        self.crear("a@a.cl", "Lector")
        r = self.client.post(reverse("login"), {"mail_user": "a@a.cl", "password": CLAVE})
        self.assertRedirects(r, reverse("home"))
        self.client.post(reverse("logout"))
        r = self.client.post(reverse("login"), {"mail_user": "a@a.cl", "password": "mala"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "incorrectos")

    def test_registro_con_claves_distintas(self):
        r = self.client.post(reverse("register"), {**self.datos, "password2": "otra"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Company.objects.exists())

    def test_error_de_rut_vuelve_al_paso_2(self):
        r = self.client.post(reverse("register"), {**self.datos, "rut_company": "12345678-9"})
        self.assertEqual(r.context["paso_inicial"], 2)

    def test_error_de_correo_vuelve_al_paso_1(self):
        self.crear("nuevo@x.cl", "Lector")
        r = self.client.post(reverse("register"), self.datos)
        self.assertEqual(r.context["paso_inicial"], 1)


class TrabajadorTests(Base):
    def datos(self, **extra):
        operativo = Role.objects.get(name_role="Operativo")
        base = {
            "mail_user": "Nuevo@A.cl", "password": CLAVE, "password2": CLAVE,
            "name_user": "Luis", "surname_user": "Rojas", "role": operativo.pk,
        }
        base.update(extra)
        return base

    def test_dueno_crea_trabajador_en_su_empresa(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.client.force_login(dueno)
        r = self.client.post(reverse("administracion"), self.datos())
        self.assertRedirects(r, reverse("administracion"))
        t = User.objects.get(pk="nuevo@a.cl")  # el correo quedó en minúsculas
        self.assertEqual(t.company, dueno.company)
        self.assertFalse(t.is_owner)
        self.assertEqual(t.role.name_role, "Operativo")
        self.assertTrue(t.password.startswith("argon2$"))

    def test_claves_distintas_no_crea_trabajador(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.client.force_login(dueno)
        r = self.client.post(reverse("administracion"), self.datos(password2="otra"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "no coinciden")
        self.assertFalse(User.objects.filter(pk="nuevo@a.cl").exists())

    def test_operativo_no_puede_crear_trabajadores(self):
        op = self.crear("op@a.cl", "Operativo")
        self.client.force_login(op)
        r = self.client.post(reverse("administracion"), self.datos())
        self.assertEqual(r.status_code, 403)
        self.assertFalse(User.objects.filter(pk="nuevo@a.cl").exists())

    def test_no_se_puede_asignar_otra_empresa(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("otro@b.cl", "Lector", rut=22222222, dv="2")
        self.client.force_login(dueno)
        self.client.post(
            reverse("administracion"),
            self.datos(company=22222222, rut_company=22222222),
        )
        t = User.objects.get(pk="nuevo@a.cl")
        self.assertEqual(t.company, dueno.company)

    def test_correo_duplicado(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("nuevo@a.cl", "Lector")
        self.client.force_login(dueno)
        r = self.client.post(reverse("administracion"), self.datos())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ya está registrado")

class ConfiguracionTests(Base):
    def test_requiere_sesion(self):
        r = self.client.get(reverse("configuracion"))
        self.assertRedirects(r, reverse("login") + "?next=" + reverse("configuracion"))

    def test_cambiar_datos_ignora_el_correo(self):
        u = self.crear("a@a.cl", "Lector")
        self.client.force_login(u)
        r = self.client.post(reverse("configuracion"), {
            "accion": "datos", "name_user": "Ana María", "surname_user": "Soto Díaz",
            "mail_user": "otro@x.cl",   # intento de cambiar el correo: se ignora
        })
        self.assertRedirects(r, reverse("configuracion"))
        u.refresh_from_db()
        self.assertEqual((u.name_user, u.surname_user), ("Ana María", "Soto Díaz"))
        self.assertTrue(User.objects.filter(pk="a@a.cl").exists())

    def test_cambiar_clave_mantiene_la_sesion(self):
        u = self.crear("a@a.cl", "Lector")
        self.client.force_login(u)
        r = self.client.post(reverse("configuracion"), {
            "accion": "clave", "clave_actual": CLAVE,
            "clave_nueva": "OtraClave456!", "clave_nueva2": "OtraClave456!",
        })
        self.assertRedirects(r, reverse("configuracion"))
        u.refresh_from_db()
        self.assertTrue(u.check_password("OtraClave456!"))
        self.assertEqual(self.client.get(reverse("configuracion")).status_code, 200)

    def test_clave_actual_incorrecta_no_cambia_nada(self):
        u = self.crear("a@a.cl", "Lector")
        self.client.force_login(u)
        r = self.client.post(reverse("configuracion"), {
            "accion": "clave", "clave_actual": "mala",
            "clave_nueva": "OtraClave456!", "clave_nueva2": "OtraClave456!",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "no es correcta")
        u.refresh_from_db()
        self.assertTrue(u.check_password(CLAVE))


class EliminarCuentaTests(Base):
    def test_solo_el_dueno_puede(self):
        self.crear("dueno@a.cl", "Propietario", owner=True)
        op = self.crear("op@a.cl", "Operativo")
        self.client.force_login(op)
        r = self.client.post(reverse("eliminar_cuenta"), {"password": CLAVE})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Company.objects.filter(rut_company=11111111).exists())

    def test_clave_incorrecta_no_borra(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.client.force_login(dueno)
        r = self.client.post(reverse("eliminar_cuenta"), {"password": "mala"})
        self.assertRedirects(r, reverse("configuracion"))
        self.assertTrue(Company.objects.filter(rut_company=11111111).exists())

    def test_borra_empresa_usuarios_y_datos_solo_de_esa_empresa(self):
        dueno = self.crear("dueno@a.cl", "Propietario", owner=True)
        self.crear("emp@a.cl", "Operativo")
        self.crear("otro@b.cl", "Lector", rut=22222222, dv="2")
        Item.objects.create(company=dueno.company, name_item="Producto", stock=1)
        self.client.force_login(dueno)
        r = self.client.post(reverse("eliminar_cuenta"), {"password": CLAVE})
        self.assertRedirects(r, reverse("login"))
        self.assertFalse(Company.objects.filter(rut_company=11111111).exists())
        self.assertFalse(User.objects.filter(company_id=11111111).exists())
        self.assertFalse(Item.objects.filter(company_id=11111111).exists())
        self.assertTrue(User.objects.filter(pk="otro@b.cl").exists())  # otra empresa intacta