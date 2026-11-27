from django.urls import reverse

# Lista configurable de pasos del recorrido inicial.
# Cada paso acepta:
# - url_name: nombre de la ruta Django donde ocurre el paso
# - selector: selector CSS del elemento a resaltar (puede llevar alternativas separadas por coma)
# - titulo / texto: contenido de la tarjeta flotante
# - avanzar_al_click: True si hacer clic en el elemento avanza automáticamente al siguiente paso
# - pausa_en_modal: True si el botón abre un modal de Bootstrap (oculta el foco mientras el modal esté abierto)

PASOS_TOUR_INICIAL = [
    {
        "url_name": "home",
        "selector": '.nav-nv a[href*="inventario"]',
        "titulo": "¡Bienvenido a Nuvempry!",
        "texto": "¿Te gustaría un recorrido guiado por las principales funciones del sistema?",
        "avanzar_al_click": True,
        "obligatorio": True,
    },
    {
        "url_name": "inventario",
        "selector": 'button[data-modal-url*="nuevo"]',
        "titulo": "Agrega tu primer producto",
        "texto": "Presiona «Nuevo producto» y completa el formulario para registrar tus artículos.",
        "avanzar_al_click": False,
        "pausa_en_modal": True,
        "obligatorio_si_no_existe": ".nv-card",
    },
    {
        "url_name": "inventario",
        "selector": ".nv-card",
        "avanzar_al_click_selector": ".nv-check",
        "titulo": "Controla entradas y salidas de stock",
        "texto": "En la tarjeta del producto, usa los botones morados para sumar o descontar unidades y confirma con el botón ✓.",
        "avanzar_al_click": False,
    },
    {
        "url_name": "inventario",
        "selector": '.nav-nv a[href*="auditoria"]',
        "titulo": "Revisa el historial de movimientos",
        "texto": "Cada cambio de stock queda registrado, facilitando funciones de auditoría.",
        "avanzar_al_click": True,
        "obligatorio": True,
    },
    {
        "url_name": "auditoria",
        "selector": '.card',
        "titulo": "Historial de Auditoría",
        "texto": "Aquí puedes auditar quién modificó cada producto, cuándo y qué modificó.",
        "avanzar_al_click": False,
        "obligatorio": False,
    },
    {
        "url_name": "auditoria",
        "selector": '.nav-nv a[href*="administracion"]',
        "titulo": "Invita a tus trabajadores",
        "texto": "**¿\"Quién\"?** Exacto, puedes agregar gente que colabore en la gestión de tus productos.",
        "avanzar_al_click": True,
        "obligatorio": True,
    },
    {
        "url_name": "administracion",
        "selector": 'button[data-bs-target="#modal-agregar"]',
        "titulo": "Invita a tus trabajadores",
        "texto": "Desde «Agregar Usuario» puedes crear cuentas para vendedores o bodegueros con permisos personalizados.",
        "avanzar_al_click": False,
        "pausa_en_modal": True,
    },
    {
        "url_name": "administracion",
        "selector": '.nav-nv a[href*="/"]',
        "titulo": "Resumen de tu negocio",
        "texto": "Ya conoces lo básico. Ahora ve a tu panel principal para ver información sobre cómo va tu negocio.",
        "avanzar_al_click": True,
        "obligatorio": True,
    },
    {
        "url_name": "home",
        "selector": '.nav-nv a[href*="/"]',
        "titulo": "Resumen de tu negocio",
        "texto": "Aquí verás datos útiles para tu negocio, alertas cuando un producto esté por agotarse, tus productos estrella y otros datos útiles.",
        "avanzar_al_click": False,
        "obligatorio": False,
    }
]


def obtener_pasos_tour():
    pasos_resueltos = []
    for paso in PASOS_TOUR_INICIAL:
        pasos_resueltos.append({
            "ruta": reverse(paso["url_name"]),
            "selector": paso["selector"],
            "avanzarAlClickSelector": paso.get("avanzar_al_click_selector"),
            "titulo": paso["titulo"],
            "texto": paso["texto"],
            "avanzarAlClick": paso.get("avanzar_al_click", False),
            "pausaEnModal": paso.get("pausa_en_modal", False),
            "obligatorio": paso.get("obligatorio", False),
            "obligatorioSiNoExiste": paso.get("obligatorio_si_no_existe"),
        })
    return pasos_resueltos