from django.conf import settings
from django.db import models


class Reservation(models.Model):
    """Reserva de uma área comum por um morador."""

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmada"
        CANCELLED = "cancelled", "Cancelada"
        RESCHEDULED = "rescheduled", "Reagendada"

    space = models.ForeignKey(
        "app.Space",
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="espaço",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="usuário",
    )
    start_at = models.DateTimeField("início")
    end_at = models.DateTimeField("fim")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    notes = models.TextField("observações", blank=True)
    protocol = models.CharField("protocolo", max_length=32, unique=True)
    guests_count = models.PositiveIntegerField("qtd. convidados", default=0)
    related_reservation = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reschedules",
        verbose_name="reserva relacionada",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-start_at"]

    def __str__(self) -> str:
        return f"{self.protocol} — {self.space}"


class Guest(models.Model):
    """Convidado vinculado a uma reserva."""

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="guests",
        verbose_name="reserva",
    )
    name = models.CharField("nome", max_length=120)

    class Meta:
        verbose_name = "convidado"
        verbose_name_plural = "convidados"

    def __str__(self) -> str:
        return self.name


class ReservationEvent(models.Model):
    """Histórico de ações sobre uma reserva."""

    class Action(models.TextChoices):
        CREATED = "created", "Criada"
        CANCELLED = "cancelled", "Cancelada"
        RESCHEDULED = "rescheduled", "Reagendada"

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="reserva",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "evento de reserva"
        verbose_name_plural = "eventos de reserva"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reservation.protocol}: {self.action}"
