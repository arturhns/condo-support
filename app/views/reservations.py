from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.models import Reservation


@login_required
def my_reservations(request):
    reservations = (
        Reservation.objects.filter(user=request.user)
        .select_related("space")
        .order_by("-start_at")
    )
    return render(
        request,
        "reservations/my_list.html",
        {"reservations": reservations},
    )
