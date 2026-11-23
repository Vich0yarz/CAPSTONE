from django.urls import path

from . import views

urlpatterns = [
    path("auditoria/", views.auditoria, name="auditoria"),
    path("auditoria/item/<int:pk>/", views.detalle_item_auditoria, name="auditoria_item_detalle"),
]