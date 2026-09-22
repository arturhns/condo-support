"""Regras de negócio de reserva, cancelamento e reagendamento."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from app.models import Guest, Reservation, ReservationEvent, Space, User


class ReservationError(Exception):
    """Erro de regra de negócio em reservas."""


def has_overlap(
    space: Space,
    start_at: datetime,
    end_at: datetime,
    exclude_id: int | None = None,
) -> bool:
    """True se já existir reserva ativa no mesmo espaço no intervalo.

    Intervalos adjacentes (fim == início) não se sobrepõem.
    Ignora status cancelled e rescheduled.
    """
    if end_at <= start_at:
        raise ReservationError("O horário de término deve ser posterior ao início.")

    qs = Reservation.objects.filter(space=space).exclude(
        status__in=[
            Reservation.Status.CANCELLED,
            Reservation.Status.RESCHEDULED,
        ]
    )
    # start < other.end AND end > other.start
    qs = qs.filter(start_at__lt=end_at, end_at__gt=start_at)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def can_cancel(reservation: Reservation, now: datetime | None = None) -> bool:
    """True se ainda estiver dentro do prazo mínimo de cancelamento."""
    if now is None:
        now = timezone.now()
    deadline = reservation.start_at - timedelta(
        hours=reservation.space.min_cancel_hours
    )
    return now <= deadline


def _next_protocol(at: datetime | None = None) -> str:
    year = (at or timezone.now()).year
    prefix = f"CA-{year}-"
    last = (
        Reservation.objects.filter(protocol__startswith=prefix)
        .order_by("-protocol")
        .values_list("protocol", flat=True)
        .first()
    )
    seq = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


@transaction.atomic
def create_reservation(
    *,
    space: Space,
    user: User,
    start_at: datetime,
    end_at: datetime,
    notes: str = "",
    guests_count: int = 0,
    guest_names: Iterable[str] | None = None,
) -> Reservation:
    """Cria reserva confirmada com protocolo e evento created."""
    if has_overlap(space, start_at, end_at):
        raise ReservationError("Já existe reserva neste horário para o espaço.")

    names = [n.strip() for n in (guest_names or []) if n and n.strip()]
    count = guests_count if guests_count else len(names)

    reservation = Reservation.objects.create(
        space=space,
        user=user,
        start_at=start_at,
        end_at=end_at,
        status=Reservation.Status.CONFIRMED,
        notes=notes,
        protocol=_next_protocol(start_at),
        guests_count=count,
    )
    Guest.objects.bulk_create(
        [Guest(reservation=reservation, name=name) for name in names]
    )
    ReservationEvent.objects.create(
        reservation=reservation,
        action=ReservationEvent.Action.CREATED,
        note="Reserva criada.",
    )
    return reservation


@transaction.atomic
def cancel_reservation(
    reservation: Reservation,
    *,
    now: datetime | None = None,
    note: str = "",
) -> Reservation:
    """Cancela se estiver no prazo; grava evento cancelled."""
    if reservation.status != Reservation.Status.CONFIRMED:
        raise ReservationError("Somente reservas confirmadas podem ser canceladas.")

    if not can_cancel(reservation, now=now):
        raise ReservationError(
            "Prazo mínimo para cancelamento não respeitado "
            f"({reservation.space.min_cancel_hours}h antes do início)."
        )

    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    ReservationEvent.objects.create(
        reservation=reservation,
        action=ReservationEvent.Action.CANCELLED,
        note=note or "Reserva cancelada.",
    )
    return reservation


@transaction.atomic
def reschedule_reservation(
    reservation: Reservation,
    *,
    start_at: datetime,
    end_at: datetime,
    notes: str | None = None,
    guests_count: int | None = None,
    guest_names: Iterable[str] | None = None,
) -> Reservation:
    """Marca a original como rescheduled e cria nova confirmed ligada.

    Sempre na mesma área. Início e fim devem cair no mesmo dia local.
    Sobreposição ignora a reserva original (exclude_id).
    """
    from app.services.availability import is_within_operating_hours

    if reservation.status != Reservation.Status.CONFIRMED:
        raise ReservationError("Somente reservas confirmadas podem ser reagendadas.")

    if end_at <= start_at:
        raise ReservationError("O horário de término deve ser posterior ao início.")

    tz = timezone.get_current_timezone()
    local_start = timezone.localtime(start_at, tz)
    local_end = timezone.localtime(end_at, tz)
    if local_start.date() != local_end.date():
        raise ReservationError("A reserva não pode cruzar a meia-noite.")

    if not is_within_operating_hours(reservation.space, start_at, end_at):
        opening = reservation.space.opening_time.strftime("%H:%M")
        closing = reservation.space.closing_time.strftime("%H:%M")
        raise ReservationError(
            "Horário fora do funcionamento do espaço "
            f"({opening} às {closing}, no mesmo dia)."
        )

    if has_overlap(
        reservation.space,
        start_at,
        end_at,
        exclude_id=reservation.pk,
    ):
        raise ReservationError("Já existe reserva neste horário para o espaço.")

    if guest_names is not None:
        names = [n.strip() for n in guest_names if n and n.strip()]
    else:
        names = [g.name for g in reservation.guests.all()]

    if guests_count is not None:
        count = guests_count
    elif guest_names is not None:
        count = len(names)
    else:
        count = reservation.guests_count

    reservation.status = Reservation.Status.RESCHEDULED
    reservation.save(update_fields=["status", "updated_at"])
    ReservationEvent.objects.create(
        reservation=reservation,
        action=ReservationEvent.Action.RESCHEDULED,
        note="Reserva reagendada; nova reserva criada.",
    )

    new_reservation = Reservation.objects.create(
        space=reservation.space,
        user=reservation.user,
        start_at=start_at,
        end_at=end_at,
        status=Reservation.Status.CONFIRMED,
        notes=notes if notes is not None else reservation.notes,
        protocol=_next_protocol(start_at),
        guests_count=count,
        related_reservation=reservation,
    )
    Guest.objects.bulk_create(
        [Guest(reservation=new_reservation, name=name) for name in names]
    )
    ReservationEvent.objects.create(
        reservation=new_reservation,
        action=ReservationEvent.Action.CREATED,
        note=f"Criada a partir de {reservation.protocol}.",
    )
    return new_reservation