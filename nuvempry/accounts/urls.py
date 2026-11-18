from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("administracion/", views.administracion, name="administracion"),
    path("administracion/eliminar/", views.eliminar_usuario, name="eliminar_usuario"),
    path("administracion/rol/", views.cambiar_rol, name="cambiar_rol"),
]