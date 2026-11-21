from django.urls import path

from . import views

urlpatterns = [
    path("auditoria/", views.auditoria, name="auditoria"),
]