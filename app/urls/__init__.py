"""URLs do app CondoAgenda (área do morador)."""

from django.urls import path

from app.views import (
    ResidentLoginView,
    ResidentLogoutView,
    my_reservations,
    space_detail,
    space_list,
)

urlpatterns = [
    path("contas/entrar/", ResidentLoginView.as_view(), name="login"),
    path("contas/sair/", ResidentLogoutView.as_view(), name="logout"),
    path("", my_reservations, name="my_reservations"),
    path("areas/", space_list, name="space_list"),
    path("areas/<slug:slug>/", space_detail, name="space_detail"),
]
