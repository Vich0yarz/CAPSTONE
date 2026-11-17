from django.contrib.auth import authenticate
from django.test import TestCase

from accounts.models import Company, Role, User


class LoginTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            rut_company=11111111, dv="1", name_company="Empresa Test"
        )
        self.role, _ = Role.objects.get_or_create(name_role="Lector")
        User.objects.create_user(
            "test@correo.cl", "ClaveSegura123!",
            company=self.company, role=self.role,
            name_user="Test", surname_user="Uno",
        )

    def test_login_correcto(self):
        user = authenticate(username="test@correo.cl", password="ClaveSegura123!")
        self.assertIsNotNone(user)

    def test_clave_incorrecta(self):
        user = authenticate(username="test@correo.cl", password="otra_clave")
        self.assertIsNone(user)

    def test_hash_es_argon2(self):
        user = User.objects.get(pk="test@correo.cl")
        self.assertTrue(user.password.startswith("argon2$"))