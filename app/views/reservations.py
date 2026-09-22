from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app.forms.reservations import ReservationForm, RescheduleForm
from app.models import Reservation, Space, User
from app.services.availability import (
    WEEKDAYS_PT,
    day_slots,
    month_label,
    month_weeks,
    shift_month,
)
from app.services.reservations import (
    ReservationError,
    can_cancel,
    create_reservation,
    cancel_reservation,
    reschedule_reservation,
)
from app.views.spaces import _selected_date

MY_RESERVATIONS_PER_PAGE = 20


def _parse_start(raw):
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _parse_date(raw):
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _page_title(space, day):
    if day is None:
        return space.name
    if isinstance(day, date):
        return f"{space.name} · {day.strftime('%d/%m/%Y')}"
    return f"{space.name} · {day}"


def _back_date(form):
    value = form["date"].value()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return ""


def _locked_date_from_request(request):
    """Dia escolhido no calendário: ?date= ou data do ?start=."""
    locked = _parse_date(request.GET.get("date"))
    if locked is not None:
        return locked
    start = _parse_start(request.GET.get("start"))
    if start is not None:
        return timezone.localtime(start).date()
    return None


def _can_reschedule(reservation, now=None):
    if now is None:
        now = timezone.now()
    return (
        reservation.status == Reservation.Status.CONFIRMED
        and reservation.start_at > now
    )


def _get_owned_reservation(request, pk):
    return get_object_or_404(
        Reservation.objects.select_related("space").prefetch_related("guests"),
        pk=pk,
        user=request.user,
    )


def _get_visible_reservation(request, lookup):
    """Dono ou staff; lookup por protocol (str) ou id (int)."""
    qs = Reservation.objects.select_related("space").prefetch_related("guests")
    if isinstance(lookup, int) or (isinstance(lookup, str) and lookup.isdigit()):
        reservation = get_object_or_404(qs, pk=int(lookup))
    else:
        reservation = get_object_or_404(qs, protocol=lookup)
    if reservation.user_id != request.user.id and not (
        request.user.is_staff or request.user.role in (User.Role.STAFF, User.Role.ADMIN)
    ):
        raise Http404()
    return reservation


def _guest_names_from_reservation(reservation):
    return list(reservation.guests.order_by("pk").values_list("name", flat=True))


def _render_form(
    request,
    space,
    form,
    guest_names,
    *,
    status=200,
    reservation=None,
):
    locked = form.locked_date
    if locked is None:
        raw = form.date_iso
        locked = _parse_date(raw) if raw else None
    return render(
        request,
        "reservations/form.html",
        {
            "space": space,
            "form": form,
            "guest_names": guest_names,
            "page_title": (
                f"Reagendar {reservation.protocol} — {space.name}"
                if reservation
                else _page_title(space, locked)
            ),
            "back_date": _back_date(form),
            "locked_date": locked,
            "reschedule_of": reservation,
        },
        status=status,
    )


def _render_reschedule_calendar(request, reservation, *, status=200):
    space = reservation.space
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
            "slots": day_slots(
                space,
                selected,
                exclude_reservation_id=reservation.pk,
                highlight_start=reservation.start_at,
                highlight_end=reservation.end_at,
            ),
            "reschedule_of": reservation,
        },
        status=status,
    )


@login_required
def my_reservations(request):
    now = timezone.now()
    reservations = (
        Reservation.objects.filter(user=request.user)
        .select_related("space")
        .order_by("-created_at")
    )
    rows = []
    for reservation in reservations:
        is_confirmed = reservation.status == Reservation.Status.CONFIRMED
        cancel_ok = is_confirmed and can_cancel(reservation, now=now)
        rows.append(
            {
                "reservation": reservation,
                "allow_cancel": cancel_ok,
                # Mostra o botão (ativo ou desabilitado) em confirmadas futuras.
                "cancel_blocked_reason": (
                    f"Cancelamento permitido até {reservation.space.min_cancel_hours}h "
                    "antes do início."
                    if is_confirmed and reservation.start_at > now and not cancel_ok
                    else ""
                ),
                "allow_reschedule": _can_reschedule(reservation, now=now),
            }
        )
    paginator = Paginator(rows, MY_RESERVATIONS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "reservations/my_list.html",
        {"page_obj": page_obj},
    )


@login_required
@require_http_methods(["GET", "POST"])
def reservation_create(request, slug):
    space = get_object_or_404(Space, slug=slug, is_active=True)
    if request.user.role != User.Role.RESIDENT:
        return render(
            request,
            "reservations/residents_only.html",
            {"space": space},
            status=403,
        )

    locked_date = _locked_date_from_request(request)

    if request.method == "POST":
        form = ReservationForm(
            request.POST,
            space=space,
            locked_date=locked_date,
        )
        guest_names = request.POST.getlist("guest_names")
        if form.is_valid():
            try:
                reservation = create_reservation(
                    space=space,
                    user=request.user,
                    start_at=form.cleaned_data["start_at"],
                    end_at=form.cleaned_data["end_at"],
                    notes=form.cleaned_data["notes"],
                    guests_count=form.cleaned_data["guests_count"],
                    guest_names=guest_names,
                )
            except ReservationError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    f"Reserva confirmada. Protocolo {reservation.protocol}.",
                )
                return redirect("my_reservations")
        return _render_form(request, space, form, guest_names, status=400)

    initial = {}
    start = _parse_start(request.GET.get("start"))
    if start is not None:
        local = timezone.localtime(start)
        locked_date = local.date()
        initial["date"] = locked_date
        initial["start_time"] = local.time().replace(second=0, microsecond=0)
        initial["end_time"] = (
            local + timedelta(hours=1)
        ).time().replace(second=0, microsecond=0)
    elif locked_date is not None:
        initial["date"] = locked_date
    form = ReservationForm(
        initial=initial,
        space=space,
        locked_date=locked_date,
    )
    return _render_form(request, space, form, [])


@login_required
def reservation_detail(request, lookup):
    reservation = _get_visible_reservation(request, lookup)
    now = timezone.now()
    allow_cancel = (
        reservation.user_id == request.user.id
        and reservation.status == Reservation.Status.CONFIRMED
        and can_cancel(reservation, now=now)
    )
    allow_reschedule = (
        reservation.user_id == request.user.id
        and _can_reschedule(reservation, now=now)
    )
    cancel_deadline_passed = (
        reservation.status == Reservation.Status.CONFIRMED
        and reservation.start_at > now
        and not can_cancel(reservation, now=now)
    )
    return render(
        request,
        "reservations/detail.html",
        {
            "reservation": reservation,
            "allow_cancel": allow_cancel,
            "allow_reschedule": allow_reschedule,
            "cancel_deadline_passed": cancel_deadline_passed,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def reservation_cancel(request, pk):
    reservation = _get_owned_reservation(request, pk)
    if request.method == "GET":
        if reservation.status != Reservation.Status.CONFIRMED:
            messages.error(request, "Somente reservas confirmadas podem ser canceladas.")
            return redirect("reservation_detail", lookup=reservation.protocol)
        return render(
            request,
            "reservations/cancel_confirm.html",
            {"reservation": reservation},
        )

    try:
        cancel_reservation(reservation)
    except ReservationError as exc:
        messages.error(request, str(exc))
        return redirect("reservation_detail", lookup=reservation.protocol)

    messages.success(
        request,
        f"Reserva {reservation.protocol} cancelada.",
    )
    return redirect("my_reservations")


@login_required
@require_http_methods(["GET", "POST"])
def reservation_reschedule(request, pk):
    """Calendário (GET) → form (GET ?start=) → POST chama reschedule_reservation."""
    reservation = _get_owned_reservation(request, pk)
    if not _can_reschedule(reservation):
        messages.error(
            request,
            "Somente reservas confirmadas e futuras podem ser reagendadas.",
        )
        return redirect("reservation_detail", lookup=reservation.protocol)

    space = reservation.space
    locked_date = _locked_date_from_request(request)

    if request.method == "POST":
        form = RescheduleForm(
            request.POST,
            space=space,
            locked_date=locked_date,
        )
        guest_names = request.POST.getlist("guest_names")
        if form.is_valid():
            try:
                new_reservation = reschedule_reservation(
                    reservation,
                    start_at=form.cleaned_data["start_at"],
                    end_at=form.cleaned_data["end_at"],
                    notes=form.cleaned_data["notes"],
                    guests_count=form.cleaned_data["guests_count"],
                    guest_names=guest_names,
                )
            except ReservationError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    f"Reserva reagendada. Novo protocolo {new_reservation.protocol}.",
                )
                return redirect("my_reservations")
        return _render_form(
            request,
            space,
            form,
            guest_names,
            status=400,
            reservation=reservation,
        )

    start = _parse_start(request.GET.get("start"))
    if start is not None:
        local = timezone.localtime(start)
        locked_date = local.date()
        initial = {
            "date": locked_date,
            "start_time": local.time().replace(second=0, microsecond=0),
            "end_time": (
                local + timedelta(hours=1)
            ).time().replace(second=0, microsecond=0),
            "guests_count": reservation.guests_count or 1,
            "notes": reservation.notes,
        }
        form = RescheduleForm(
            initial=initial,
            space=space,
            locked_date=locked_date,
        )
        return _render_form(
            request,
            space,
            form,
            _guest_names_from_reservation(reservation),
            reservation=reservation,
        )

    return _render_reschedule_calendar(request, reservation)
