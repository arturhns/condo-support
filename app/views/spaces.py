from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from app.models import Space
from app.services.availability import (
    WEEKDAYS_PT,
    day_slots,
    month_label,
    month_weeks,
    shift_month,
)


def _selected_date(raw):
    if raw:
        try:
            return datetime.strptime(raw.strip(), "%Y-%m-%d").date(), False
        except ValueError:
            return timezone.localdate(), True
    return timezone.localdate(), False


@login_required
def space_list(request):
    spaces = Space.objects.filter(is_active=True)
    return render(request, "spaces/list.html", {"spaces": spaces})


@login_required
def space_detail(request, slug):
    space = get_object_or_404(Space, slug=slug, is_active=True)
    selected, date_invalid = _selected_date(request.GET.get("date"))
    return render(
        request,
        "spaces/detail.html",
        {
            "space": space,
            "selected": selected,
            "date_invalid": date_invalid,
            "month_label": month_label(selected),
            "weekdays": WEEKDAYS_PT,
            "weeks": month_weeks(selected),
            "prev_month": shift_month(selected, -1),
            "next_month": shift_month(selected, 1),
            "slots": day_slots(space, selected),
        },
    )
