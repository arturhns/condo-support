from app.views.auth import ResidentLoginView, ResidentLogoutView
from app.views.reservations import my_reservations
from app.views.spaces import space_detail, space_list

__all__ = [
    "ResidentLoginView",
    "ResidentLogoutView",
    "my_reservations",
    "space_list",
    "space_detail",
]
