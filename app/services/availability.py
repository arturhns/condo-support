"""Horários do dia de um espaço: slots de 1 hora dentro do funcionamento."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from django.utils import timezone

from app.models import Space
from app.services.reservations import has_overlap

SLOT_DURATION = timedelta(hours=1)

WEEKDAYS_PT = ("Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb")
MONTHS_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def shift_month(day: date, delta: int) -> date:
    """Primeiro dia do mês deslocado em `delta` meses."""
    index = day.month - 1 + delta
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, 1)


def month_label(day: date) -> str:
    return f"{MONTHS_PT[day.month - 1].capitalize()} de {day.year}"


def month_weeks(day: date) -> list[list[date | None]]:
    """Semanas do mês, começando no domingo. Dias fora do mês são None."""
    cal = calendar.Calendar(firstweekday=6)
    weeks: list[list[date | None]] = []
    for week in cal.monthdayscalendar(day.year, day.month):
        weeks.append(
            [
                date(day.year, day.month, number) if number else None
                for number in week
            ]
        )
    return weeks


def _aware(day: date, clock) -> datetime:
    return timezone.make_aware(
        datetime.combine(day, clock),
        timezone.get_current_timezone(),
    )


def iter_slots(space: Space, day: date):
    """Começa em opening_time e avança 1h enquanto o slot terminar até closing_time.

    Se abertura ou fechamento não forem horas cheias, o primeiro slot ainda
    começa exatamente na abertura (ex.: 08:30–09:30).
    """
    opening = space.opening_time
    closing = space.closing_time
    if closing <= opening:
        return
    close_at = _aware(day, closing)
    cursor = _aware(day, opening)
    while cursor + SLOT_DURATION <= close_at:
        yield cursor, cursor + SLOT_DURATION
        cursor = cursor + SLOT_DURATION


def is_within_operating_hours(
    space: Space,
    start_at: datetime,
    end_at: datetime,
) -> bool:
    """True se início e fim caem no mesmo dia local, entre abertura e fechamento."""
    if end_at <= start_at:
        return False
    tz = timezone.get_current_timezone()
    start = timezone.localtime(start_at, tz)
    end = timezone.localtime(end_at, tz)
    if start.date() != end.date():
        return False
    opening = space.opening_time
    closing = space.closing_time
    if isinstance(opening, str):
        opening = datetime.strptime(opening, "%H:%M").time()
    if isinstance(closing, str):
        closing = datetime.strptime(closing, "%H:%M").time()
    if closing <= opening:
        return False
    return start.time() >= opening and end.time() <= closing


def day_slots(
    space: Space,
    day: date,
    *,
    exclude_reservation_id: int | None = None,
    highlight_start=None,
    highlight_end=None,
) -> list[dict]:
    """Slots do dia. Ocupado = reserva ativa que sobrepõe o intervalo.

    Com exclude_reservation_id, a própria reserva não ocupa o slot.
    highlight_start/end marcam o intervalo atual (badge \"atual\").
    """
    slots = []
    for start, end in iter_slots(space, day):
        local_start = timezone.localtime(start)
        local_end = timezone.localtime(end)
        occupied = has_overlap(
            space, start, end, exclude_id=exclude_reservation_id
        )
        is_current = False
        if (
            highlight_start is not None
            and highlight_end is not None
            and start < highlight_end
            and end > highlight_start
        ):
            is_current = True
        slots.append(
            {
                "start": start,
                "end": end,
                "label": local_start.strftime("%H:%M"),
                "start_iso": start.isoformat(),
                "end_iso": end.isoformat(),
                "start_local": local_start.strftime("%Y-%m-%dT%H:%M"),
                "end_local": local_end.strftime("%Y-%m-%dT%H:%M"),
                "occupied": occupied and not is_current,
                "is_current": is_current,
            }
        )
    return slots