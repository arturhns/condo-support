"""URLs da API REST sob /api/."""

from django.urls import path

from app.api.views import (
    MyReservationsAPIView,
    ReservationCancelAPIView,
    ReservationCreateAPIView,
    ReservationRescheduleAPIView,
    SpaceAvailabilityAPIView,
    SpaceListAPIView,
)

urlpatterns = [
    path("spaces/", SpaceListAPIView.as_view(), name="api_space_list"),
    path(
        "spaces/<slug:slug>/availability/",
        SpaceAvailabilityAPIView.as_view(),
        name="api_space_availability",
    ),
    path("reservations/me/", MyReservationsAPIView.as_view(), name="api_reservations_me"),
    path("reservations/", ReservationCreateAPIView.as_view(), name="api_reservation_create"),
    path(
        "reservations/<int:pk>/cancel/",
        ReservationCancelAPIView.as_view(),
        name="api_reservation_cancel",
    ),
    path(
        "reservations/<int:pk>/reschedule/",
        ReservationRescheduleAPIView.as_view(),
        name="api_reservation_reschedule",
    ),
]
