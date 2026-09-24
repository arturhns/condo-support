"""Testes de e-mail e API REST."""

from datetime import datetime, time, timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from app.models import Reservation, Space, User
from app.services.availability import day_slots
from app.services.notifications import send_reservation_email
from app.services.reservations import create_reservation


@pytest.fixture
def resident(db):
    return User.objects.create_user(
        username="res1",
        email="res1@condo.local",
        password="condo123",
        role=User.Role.RESIDENT,
        apartment="101",
    )


@pytest.fixture
def other_resident(db):
    return User.objects.create_user(
        username="res2",
        email="res2@condo.local",
        password="condo123",
        role=User.Role.RESIDENT,
        apartment="202",
    )


@pytest.fixture
def space(db):
    return Space.objects.create(
        name="Salão de Festas",
        slug="salao-de-festas",
        capacity=40,
        opening_time=time(8, 0),
        closing_time=time(22, 0),
        min_cancel_hours=48,
    )


@pytest.fixture
def api(resident):
    client = APIClient()
    client.force_authenticate(user=resident)
    return client


def _aware(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def test_create_reservation_console_backend_does_not_raise(settings, resident, space):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=2),
    )
    assert reservation.protocol
    assert len(mail.outbox) == 1
    assert resident.email in mail.outbox[0].to
    assert reservation.protocol in mail.outbox[0].subject
    assert space.name in mail.outbox[0].body


def test_availability_marks_confirmed_slot_unavailable(resident, space):
    day = timezone.localdate() + timedelta(days=6)
    start = _aware(day, 19)
    create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    slots = day_slots(space, day)
    occupied = [s for s in slots if s["start"] == start]
    assert occupied and occupied[0]["occupied"] is True

    client = APIClient()
    client.force_authenticate(user=resident)
    response = client.get(
        reverse("api_space_availability", kwargs={"slug": space.slug}),
        {"date": day.isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == day.isoformat()
    slot_19 = next(s for s in payload["slots"] if s["start"] == "19:00")
    assert slot_19["available"] is False
    assert "user" not in slot_19
    assert all(set(s.keys()) == {"start", "end", "available"} for s in payload["slots"])


def test_api_post_reservation_authenticated_creates(api, resident, space):
    day = timezone.localdate() + timedelta(days=8)
    response = api.post(
        reverse("api_reservation_create"),
        {
            "space": space.slug,
            "date": day.isoformat(),
            "start_time": "15:00",
            "end_time": "16:00",
            "guest_names": ["Ana", "Bruno"],
            "notes": "Festa",
        },
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == Reservation.Status.CONFIRMED
    assert data["notes"] == "Festa"
    assert Reservation.objects.filter(user=resident, protocol=data["protocol"]).exists()


def test_api_cancel_outside_deadline_returns_400(api, resident, space):
    start = timezone.now() + timedelta(hours=30)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    response = api.post(reverse("api_reservation_cancel", kwargs={"pk": reservation.pk}))
    assert response.status_code == 400
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED
    assert "Prazo mínimo" in response.json()["detail"]


def test_api_user_b_cannot_cancel_user_a(api, resident, other_resident, space):
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    other_client = APIClient()
    other_client.force_authenticate(user=other_resident)
    response = other_client.post(
        reverse("api_reservation_cancel", kwargs={"pk": reservation.pk})
    )
    assert response.status_code == 404
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED


@patch("app.services.reservations.send_reservation_email")
def test_send_reservation_email_called_on_created(mock_send, resident, space):
    day = timezone.localdate() + timedelta(days=5)
    start = _aware(day, 10)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    mock_send.assert_called_once_with(reservation, "created")


def test_send_reservation_email_body_pt_br(settings, resident, space):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    day = timezone.localdate() + timedelta(days=3)
    start = _aware(day, 11)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    mail.outbox.clear()
    send_reservation_email(reservation, "created")
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert f"Protocolo: {reservation.protocol}" in body
    assert f"Espaço: {space.name}" in body
    assert "Data:" in body
    assert "Início:" in body
    assert "Fim:" in body
    assert "Status:" in body
