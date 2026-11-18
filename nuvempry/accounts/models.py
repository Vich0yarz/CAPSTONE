from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Role(models.Model):
    id_role = models.AutoField(primary_key=True)
    name_role = models.CharField(max_length=50)
    crud_user = models.BooleanField(default=False)
    crud_item = models.BooleanField(default=False)
    update_stock = models.BooleanField(default=False)

    class Meta:
        db_table = "role"

    def __str__(self):
        return self.name_role


class Company(models.Model):
    rut_company = models.IntegerField(primary_key=True)
    dv = models.CharField(max_length=1)
    name_company = models.CharField(max_length=50)

    class Meta:
        db_table = "company"

    def __str__(self):
        return self.name_company


class UserManager(BaseUserManager):
    def create_user(self, mail_user, password, **extra):
        mail_user = mail_user.strip().lower()
        user = self.model(mail_user=self.normalize_email(mail_user), **extra)
        user.set_password(password)  # aquí se aplica Argon2
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    mail_user = models.EmailField(max_length=255, primary_key=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, db_column="rut_company"
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="id_role")
    name_user = models.CharField(max_length=100)
    surname_user = models.CharField(max_length=100)
    is_owner = models.BooleanField(default=False)

    USERNAME_FIELD = "mail_user"
    REQUIRED_FIELDS = ["name_user", "surname_user"]
    objects = UserManager()

    class Meta:
        db_table = "User"