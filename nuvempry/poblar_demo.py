import random
from datetime import timedelta
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import User
from inventory.models import Item
from audit.models import Audit

random.seed(42)

# 1. Buscar usuario y empresa
usuario = User.objects.select_related("company").get(mail_user="admin@nuvempry.cl")
empresa = usuario.company
usuarios_empresa = list(User.objects.filter(company=empresa).values_list("mail_user", flat=True))

ahora = timezone.now()
hace_12_meses = ahora - timedelta(days=365)


def formato_involved_simple(item):
    return f"{item.name_item} [{item.code_sku}]" if item.code_sku else item.name_item


def formato_involved_sub(padre, sub):
    etiqueta = sub.detail or sub.name_item
    return f"{padre.name_item} — {etiqueta} [{sub.code_sku}]" if sub.code_sku else f"{padre.name_item} — {etiqueta}"


with transaction.atomic():
    # Limpiar solo inventario y auditoría de esta empresa
    Audit.objects.filter(company=empresa).delete()
    Item.objects.filter(company=empresa, parent__isnull=False).delete()
    Item.objects.filter(company=empresa).delete()

    # 2. Crear catálogo de productos y subproductos
    vaso_padre = Item.objects.create(
        company=empresa,
        name_item="Vaso Vidrio Tapa Bambú 500ml",
        category="Vasos con tapa de bambú",
        price=7990,
        stock=0,
    )

    sub_halloween = Item.objects.create(
        company=empresa,
        parent=vaso_padre,
        name_item="Vaso Vidrio Tapa Bambú 500ml",
        detail="Edición Halloween (Fantasmas y Calabazas)",
        category="Vasos con tapa de bambú",
        code_sku="VAS-HAL-01",
        price=8490,
        stock=18,
    )
    sub_navidad = Item.objects.create(
        company=empresa,
        parent=vaso_padre,
        name_item="Vaso Vidrio Tapa Bambú 500ml",
        detail="Edición Navidad (Renos y Copos)",
        category="Vasos con tapa de bambú",
        code_sku="VAS-NAV-02",
        price=8490,
        stock=22,  # quedará estancado sin salidas recientes
    )
    sub_floral = Item.objects.create(
        company=empresa,
        parent=vaso_padre,
        name_item="Vaso Vidrio Tapa Bambú 500ml",
        detail="Edición Primavera Floral",
        category="Vasos con tapa de bambú",
        code_sku="VAS-FLO-03",
        price=7990,
        stock=34,
    )
    sub_minimal = Item.objects.create(
        company=empresa,
        parent=vaso_padre,
        name_item="Vaso Vidrio Tapa Bambú 500ml",
        detail="Edición Minimalista Frases",
        category="Vasos con tapa de bambú",
        code_sku="VAS-MIN-04",
        price=7990,
        stock=4,   # alerta urgente de reposición (alta rotación, quedan 4)
    )

    vaso_padre.stock = sum(
        s.stock for s in (sub_halloween, sub_navidad, sub_floral, sub_minimal)
    )
    vaso_padre.save(update_fields=["stock"])

    # Productos simples de otras categorías
    p_dtf_flores = Item.objects.create(
        company=empresa,
        name_item="Lámina Estampado DTF UV Botánico",
        category="Estampados y vinilos",
        detail="Transfer resistente al agua 10x12 cm",
        code_sku="EST-BOT-10",
        price=2500,
        stock=0,   # alerta agotado
    )
    p_dtf_retro = Item.objects.create(
        company=empresa,
        name_item="Lámina Estampado DTF UV Retro 90s",
        category="Estampados y vinilos",
        detail="Transfer resistente al agua 10x12 cm",
        code_sku="EST-RET-11",
        price=2500,
        stock=45,
    )
    p_dtf_patriota = Item.objects.create(
        company=empresa,
        name_item="Pack Stickers Vinilo Fiestas Patrias",
        category="Estampados y vinilos",
        detail="Set de 6 stickers impermeables",
        code_sku="EST-CHI-12",
        price=3200,
        stock=28,
    )

    p_bombillas = Item.objects.create(
        company=empresa,
        name_item="Set 2 Bombillas Vidrio Reutilizables",
        category="Accesorios y tapas",
        detail="Incluye 1 recta y 1 curva",
        code_sku="ACC-BOM-20",
        price=2990,
        stock=11,  # alerta preventiva de reposición (~4-5 días de cobertura)
    )
    p_tapa_repuesto = Item.objects.create(
        company=empresa,
        name_item="Tapa Bambú Repuesto Boca Ancha 90mm",
        category="Accesorios y tapas",
        detail="Con sello de silicona hermético",
        code_sku="ACC-TAP-21",
        price=3490,
        stock=30,  # quedará estancado (> 45 días sin salidas)
    )
    p_cepillo = Item.objects.create(
        company=empresa,
        name_item="Cepillo Limpiador de Bombillas",
        category="Accesorios y tapas",
        detail="Acero inoxidable y cerdas suaves",
        code_sku="ACC-CEP-22",
        price=1500,
        stock=40,
    )

    p_pack_regalo = Item.objects.create(
        company=empresa,
        name_item="Box Regalo Vaso + Bombilla + Cepillo",
        category="Packs y regalos",
        detail="Caja kraft con cinta y tarjeta",
        code_sku="PCK-REG-30",
        price=11990,
        stock=16,
    )
    p_pack_pareja = Item.objects.create(
        company=empresa,
        name_item="Dúo Vasos Personalizados Pareja",
        category="Packs y regalos",
        detail="2 vasos 500ml con nombres",
        code_sku="PCK-DUO-31",
        price=14990,
        stock=12,
    )

    # 3. Registrar creación inicial en Auditoría hace 12 meses
    todos_simples = [
        p_dtf_flores, p_dtf_retro, p_dtf_patriota,
        p_bombillas, p_tapa_repuesto, p_cepillo,
        p_pack_regalo, p_pack_pareja,
    ]
    todos_subs = [sub_halloween, sub_navidad, sub_floral, sub_minimal]

    registros_audit = []
    fechas_historicas = []

    evento_creacion = getattr(Audit, "ITEM_CREATED", getattr(Audit, "PRODUCT_CREATED", getattr(Audit, "CREATED", "ITEM_CREATED")))
    evento_sub_creacion = getattr(Audit, "SUBPRODUCT_CREATED", evento_creacion)

    registros_audit.append(Audit(
        company=empresa,
        event_type=evento_creacion,
        involved=formato_involved_simple(vaso_padre),
        move_quantity=0,
        past_count=0,
        user_mail=usuario.mail_user,
    ))
    fechas_historicas.append(hace_12_meses)

    for sub in todos_subs:
        registros_audit.append(Audit(
            company=empresa,
            event_type=evento_sub_creacion,
            involved=formato_involved_sub(vaso_padre, sub),
            move_quantity=sub.stock,
            past_count=0,
            user_mail=usuario.mail_user,
        ))
        fechas_historicas.append(hace_12_meses + timedelta(minutes=5))

    for it in todos_simples:
        registros_audit.append(Audit(
            company=empresa,
            event_type=evento_creacion,
            involved=formato_involved_simple(it),
            move_quantity=it.stock,
            past_count=0,
            user_mail=usuario.mail_user,
        ))
        fechas_historicas.append(hace_12_meses + timedelta(minutes=10))

    # 4. Simular 365 días de ventas (bajadas) y reposiciones (subidas)
    config_movimientos = [
        (sub_minimal, vaso_padre, 9, [1, 2, 11, 12], 1.5, 0),       # Se vende todo el año, pico verano/fin de año
        (sub_floral, vaso_padre, 6, [8, 9, 10, 11], 1.7, 0),       # Pico primavera
        (sub_halloween, vaso_padre, 1, [9, 10], 14.0, 12),         # Pico enorme en octubre
        (sub_navidad, vaso_padre, 0, [11, 12], 18.0, 55),          # Solo se movió en nov/dic, estancado hoy
        (p_dtf_flores, None, 8, [9, 10, 11], 1.5, 0),              # Alta rotación (quedó en 0)
        (p_dtf_retro, None, 5, [1, 2, 7], 1.4, 2),                 # Venta pareja
        (p_dtf_patriota, None, 1, [8, 9], 12.0, 38),               # Pico Fiestas Patrias, estancado hace >30d
        (p_bombillas, None, 7, [1, 2, 12], 1.6, 0),                # Alta rotación (alerta reposición)
        (p_tapa_repuesto, None, 1, [], 1.0, 65),                   # Estancado hace 65 días
        (p_cepillo, None, 3, [1, 12], 1.4, 4),                     # Venta moderada
        (p_pack_regalo, None, 4, [5, 11, 12], 3.2, 1),             # Picos Día de la Madre y Navidad
        (p_pack_pareja, None, 3, [2, 12], 2.8, 3),                 # Picos San Valentín y Navidad
    ]

    for dia_offset in range(360, -1, -1):
        fecha_dia = ahora - timedelta(days=dia_offset)
        mes = fecha_dia.month

        for item, padre, ritmo_sem, meses_pico, factor_pico, dias_quieto in config_movimientos:
            if dia_offset < dias_quieto:
                continue

            if ritmo_sem == 0 and mes not in meses_pico:
                continue

            prob_diaria = (ritmo_sem / 7.0) * (factor_pico if mes in meses_pico else 1.0)
            if random.random() < min(prob_diaria, 0.92):
                vendidos = random.randint(1, 4 if mes in meses_pico else 2)
                hora_evento = fecha_dia.replace(
                    hour=random.randint(10, 20),
                    minute=random.randint(0, 59),
                )
                actor = random.choice(usuarios_empresa)

                if padre:
                    registros_audit.append(Audit(
                        company=empresa,
                        event_type=Audit.SUBPRODUCT_STOCK_UPDATED,
                        involved=formato_involved_sub(padre, item),
                        move_quantity=-vendidos,
                        past_count=item.stock + vendidos,
                        user_mail=actor,
                    ))
                else:
                    registros_audit.append(Audit(
                        company=empresa,
                        event_type=Audit.STOCK_UPDATED,
                        involved=formato_involved_simple(item),
                        move_quantity=-vendidos,
                        past_count=item.stock + vendidos,
                        user_mail=actor,
                    ))
                fechas_historicas.append(hora_evento)

                # Simular reposiciones periódicas cada ~21 días para mantener historial realista
                if dia_offset > 15 and dia_offset % 21 == 0:
                    reposicion = vendidos * 6 + 10
                    registros_audit.append(Audit(
                        company=empresa,
                        event_type=Audit.SUBPRODUCT_STOCK_UPDATED if padre else Audit.STOCK_UPDATED,
                        involved=formato_involved_sub(padre, item) if padre else formato_involved_simple(item),
                        move_quantity=reposicion,
                        past_count=max(2, item.stock),
                        user_mail=usuario.mail_user,
                    ))
                    fechas_historicas.append(hora_evento - timedelta(hours=3))

    Audit.objects.bulk_create(registros_audit, batch_size=500)

# Actualizar fechas históricas directamente en SQL evitando la sobreescritura de auto_now_add
pks_creados = list(
    Audit.objects.filter(company=empresa).order_by("pk").values_list("pk", flat=True)
)
tabla_audit = Audit._meta.db_table
col_fecha = Audit._meta.get_field("date_time").column
col_pk = Audit._meta.pk.column

with connection.cursor() as cursor:
    cursor.executemany(
        f'UPDATE "{tabla_audit}" SET "{col_fecha}" = %s WHERE "{col_pk}" = %s;',
        list(zip(fechas_historicas, pks_creados)),
    )

fechas = Audit.objects.filter(company=empresa).order_by("date_time").values_list("date_time", flat=True)
print(f"Listo: {Item.objects.filter(company=empresa).count()} productos y {fechas.count()} registros creados.")
print(f"Rango de fechas en BD: desde {fechas.first()} hasta {fechas.last()}")