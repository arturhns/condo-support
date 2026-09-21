from datetime import timedelta

import pytest
from django.utils import timezone

from app.models import Reservation, Space, User
from app.services.reservations import (
    ReservationError,
    cancel_reservation,
    create_reservation,
    has_overlap,
    reschedule_reservation,
)


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
def space(db):
    return Space.objects.create(
        name="Salão de Festas",
        slug="salao-de-festas",
        capacity=40,
        opening_time="08:00",
        closing_time="22:00",
        min_cancel_hours=48,
    )


@pytest.fixture
def base_start():
    return timezone.now() + timedelta(days=10)


def test_overlap_same_space_is_rejected(resident, space, base_start):
    end = base_start + timedelta(hours=2)
    create_reservation(
        space=space,
        user=resident,
        start_at=base_start,
        end_at=end,
    )
    assert has_overlap(space, base_start + timedelta(hours=1), end + timedelta(hours=1))
    with pytest.raises(ReservationError):
        create_reservation(
            space=space,
            user=resident,
            start_at=base_start + timedelta(hours=1),
            end_at=end + timedelta(hours=1),
        )


def test_adjacent_intervals_are_allowed(resident, space, base_start):
    end = base_start + timedelta(hours=2)
    create_reservation(
        space=space,
        user=resident,
        start_at=base_start,
        end_at=end,
    )
    # fim == início do próximo → permitido
    assert not has_overlap(space, end, end + timedelta(hours=2))
    second = create_reservation(
        space=space,
        user=resident,
        start_at=end,
        end_at=end + timedelta(hours=2),
    )
    assert second.status == Reservation.Status.CONFIRMED


def test_cancel_with_more_than_48h_ok(resident, space, base_start):
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=base_start,
        end_at=base_start + timedelta(hours=2),
    )
    now = base_start - timedelta(hours=49)
    cancel_reservation(reservation, now=now)
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CANCELLED


def test_cancel_with_less_than_48h_fails(resident, space, base_start):
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=base_start,
        end_at=base_start + timedelta(hours=2),
    )
    now = base_start - timedelta(hours=47)
    with pytest.raises(ReservationError):
        cancel_reservation(reservation, now=now)
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED


def test_reschedule_to_free_slot_ok(resident, space, base_start):
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=base_start,
        end_at=base_start + timedelta(hours=2),
    )
    new_start = base_start + timedelta(days=1)
    new_end = new_start + timedelta(hours=2)
    new_res = reschedule_reservation(
        reservation,
        start_at=new_start,
        end_at=new_end,
    )
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.RESCHEDULED
    assert new_res.status == Reservation.Status.CONFIRMED
    assert new_res.related_reservation_id == reservation.pk


def test_reschedule_to_occupied_slot_fails(resident, space, base_start):
    first = create_reservation(
        space=space,
        user=resident,
        start_at=base_start,
        end_at=base_start + timedelta(hours=2),
    )
    occupied_start = base_start + timedelta(days=1)
    occupied_end = occupied_start + timedelta(hours=2)
    create_reservation(
        space=space,
        user=resident,
        start_at=occupied_start,
        end_at=occupied_end,
    )
    with pytest.raises(ReservationError):
        reschedule_reservation(
            first,
            start_at=occupied_start,
            end_at=occupied_end,
        )
    first.refresh_from_db()
    assert first.status == Reservation.Status.CONFIRMED
