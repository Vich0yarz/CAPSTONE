from django.db import migrations


def crear_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    roles = [
        ("Propietario", True, True, True),
        ("Operativo", False, False, True),
        ("Lector", False, False, False),
    ]
    for nombre, crud_user, crud_item, update_stock in roles:
        Role.objects.get_or_create(
            name_role=nombre,
            defaults={
                "crud_user": crud_user,
                "crud_item": crud_item,
                "update_stock": update_stock,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(crear_roles, migrations.RunPython.noop)]