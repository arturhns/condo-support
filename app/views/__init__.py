from app.views.auth import ResidentLoginView, ResidentLogoutView
from app.views.reservations import (
    my_reservations,
    reservation_cancel,
    reservation_create,
    reservation_detail,
    reservation_reschedule,
)
from app.views.spaces import space_detail, space_list

__all__ = [
    "ResidentLoginView",
    "ResidentLogoutView",
    "my_reservations",
    "reservation_cancel",
    "reservation_create",
    "reservation_detail",
    "reservation_reschedule",
    "space_list",
    "space_detail",
]
