"""URLs do app CondoAgenda (área do morador)."""

from django.urls import path

from app.views import (
    ResidentLoginView,
    ResidentLogoutView,
    my_reservations,
    reservation_cancel,
    reservation_create,
    reservation_detail,
    reservation_reschedule,
    space_detail,
    space_list,
)

urlpatterns = [
    path("contas/entrar/", ResidentLoginView.as_view(), name="login"),
    path("contas/sair/", ResidentLogoutView.as_view(), name="logout"),
    path("", my_reservations, name="my_reservations"),
    path("areas/", space_list, name="space_list"),
    path("areas/<slug:slug>/reservar/", reservation_create, name="reservation_create"),
    path("areas/<slug:slug>/", space_detail, name="space_detail"),
    path("reservas/<int:pk>/cancelar/", reservation_cancel, name="reservation_cancel"),
    path(
        "reservas/<int:pk>/reagendar/",
        reservation_reschedule,
        name="reservation_reschedule",
    ),
    path("reservas/<str:lookup>/", reservation_detail, name="reservation_detail"),
]
