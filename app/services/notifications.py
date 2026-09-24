"""Notificações por e-mail de reservas (backend via settings/env)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from app.models import Reservation

logger = logging.getLogger(__name__)

EVENT_SUBJECT = {
    "created": "Reserva criada",
    "cancelled": "Reserva cancelada",
    "rescheduled": "Reserva reagendada",
}


def send_reservation_email(reservation: Reservation, event: str) -> None:
    """Envia e-mail ao titular da reserva. Falha na API não propaga.

    event: created | cancelled | rescheduled
    Destinatário: apenas reservation.user.email (sem dados de outros moradores).
    """
    if event not in EVENT_SUBJECT:
        logger.error("Evento de e-mail desconhecido: %s", event)
        return

    recipient = (reservation.user.email or "").strip()
    if not recipient:
        logger.warning(
            "Reserva %s sem e-mail do usuário; notificação omitida.",
            reservation.protocol,
        )
        return

    tz = timezone.get_current_timezone()
    local_start = timezone.localtime(reservation.start_at, tz)
    local_end = timezone.localtime(reservation.end_at, tz)
    subject = f"{EVENT_SUBJECT[event]} — {reservation.protocol}"
    body = (
        f"Protocolo: {reservation.protocol}\n"
        f"Espaço: {reservation.space.name}\n"
        f"Data: {local_start.strftime('%d/%m/%Y')}\n"
        f"Início: {local_start.strftime('%H:%M')}\n"
        f"Fim: {local_end.strftime('%H:%M')}\n"
        f"Status: {reservation.get_status_display()}\n"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Falha ao enviar e-mail (%s) da reserva %s; reserva mantida.",
            event,
            reservation.protocol,
        )
