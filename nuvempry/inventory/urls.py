from django.urls import path

from . import views

urlpatterns = [
    path("inventario/", views.inventario, name="inventario"),
    path("inventario/nuevo/", views.producto_nuevo, name="producto_nuevo"),
    path("inventario/<int:pk>/", views.producto_detalle, name="producto_detalle"),
    path("inventario/<int:pk>/editar/", views.editar_producto, name="editar_producto"),
    path("inventario/<int:pk>/eliminar/", views.eliminar_producto, name="eliminar_producto"),
    path("inventario/<int:pk>/subproducto/", views.subproducto_nuevo, name="subproducto_nuevo"),
    path("inventario/<int:pk>/stock/", views.actualizar_stock, name="actualizar_stock"),
]