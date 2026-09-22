import re
from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from app.models import Reservation, User
from app.services.availability import day_slots
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
def space(db):
    from app.models import Space

    return Space.objects.create(
        name="Salão de Festas",
        slug="salao-de-festas",
        capacity=40,
        opening_time="08:00",
        closing_time="22:00",
        min_cancel_hours=48,
    )


def _aware(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def _post_data(start, end, **extra):
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    data = {
        "date": local_start.date().isoformat(),
        "start_time": local_start.strftime("%H:%M"),
        "end_time": local_end.strftime("%H:%M"),
        "guests_count": 2,
        "notes": "",
    }
    data.update(extra)
    return data


def _create_url(space, day=None):
    url = reverse("reservation_create", kwargs={"slug": space.slug})
    if day is not None:
        return f"{url}?date={day.isoformat()}"
    return url


def test_slots_start_at_opening_and_stop_before_closing(space):
    space.opening_time = time(8, 30)
    space.closing_time = time(11, 0)
    space.save(update_fields=["opening_time", "closing_time"])
    day = timezone.localdate() + timedelta(days=2)
    labels = [slot["label"] for slot in day_slots(space, day)]
    assert labels == ["08:30", "09:30"]


def test_calendar_marks_confirmed_slot_as_occupied(client, resident, space):
    other = User.objects.create_user(
        username="outro_morador",
        email="outro@condo.local",
        password="condo123",
        role=User.Role.RESIDENT,
        apartment="202",
    )
    day = timezone.localdate() + timedelta(days=6)
    start = _aware(day, 19)
    create_reservation(
        space=space,
        user=other,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    cancelled_start = _aware(day, 10)
    cancelled = create_reservation(
        space=space,
        user=other,
        start_at=cancelled_start,
        end_at=cancelled_start + timedelta(hours=1),
    )
    cancelled.status = Reservation.Status.CANCELLED
    cancelled.save(update_fields=["status"])

    client.force_login(resident)
    response = client.get(
        reverse("space_detail", kwargs={"slug": space.slug}),
        {"date": day.isoformat()},
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "Reservado 19:00" in html
    assert re.search(r"<a\b[^>]*>\s*Reservado 19:00\s*</a>", html) is None
    assert re.search(
        r'<button type="button"[^>]*disabled[^>]*>Reservado 19:00</button>',
        html,
    )
    assert re.search(
        r'<a [^>]*href="[^"]*reservar/\?start=[^"]*"[^>]*>Reservar 18:00</a>',
        html,
    )
    assert "Reservar 20:00" in html
    assert "Reservar 10:00" in html
    assert other.username not in html
    assert other.email not in html
    assert "Mês anterior" in html
    assert "Próximo mês" in html


def test_get_form_prefills_slot_from_querystring(client, resident, space):
    day = timezone.localdate() + timedelta(days=4)
    start = _aware(day, 19)
    client.force_login(resident)
    response = client.get(
        reverse("reservation_create", kwargs={"slug": space.slug}),
        {"start": start.isoformat()},
    )
    assert response.status_code == 200
    html = response.content.decode()
    local = timezone.localtime(start)
    assert local.strftime("%H:%M") in html
    assert (local + timedelta(hours=1)).strftime("%H:%M") in html
    assert local.strftime("%d/%m/%Y") in html
    assert 'type="time"' in html
    assert 'step="3600"' in html
    assert 'min="08:00"' in html
    assert 'max="22:00"' in html
    assert 'max="21:00"' in html
    assert f"{space.name} · {local.strftime('%d/%m/%Y')}" in html


def test_post_free_slot_creates_reservation_with_protocol(client, resident, space):
    day = timezone.localdate() + timedelta(days=8)
    start = _aware(day, 15)
    end = start + timedelta(hours=1)
    client.force_login(resident)
    response = client.post(
        _create_url(space, day),
        _post_data(start, end, notes="Churrasco"),
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[0][0] == reverse("my_reservations")
    reservation = Reservation.objects.get()
    assert re.fullmatch(r"CA-\d{4}-\d{4}", reservation.protocol)
    assert reservation.space == space
    assert reservation.user == resident
    assert reservation.status == Reservation.Status.CONFIRMED
    html = response.content.decode()
    assert f"Protocolo {reservation.protocol}" in html
    assert reservation.protocol in html
    assert space.name in html
    assert timezone.localtime(reservation.start_at).strftime("%d/%m/%Y %H:%M") in html
    assert timezone.localtime(reservation.end_at).strftime("%d/%m/%Y %H:%M") in html
    assert "Confirmada" in html
    assert "Cancelar" in html
    assert "Reagendar" in html
    assert reverse("reservation_detail", kwargs={"lookup": reservation.protocol}) in html


def test_post_confirmed_slot_does_not_create(client, resident, space):
    day = timezone.localdate() + timedelta(days=9)
    start = _aware(day, 16)
    end = start + timedelta(hours=1)
    create_reservation(space=space, user=resident, start_at=start, end_at=end)
    client.force_login(resident)
    response = client.post(
        _create_url(space, day),
        _post_data(start, end),
    )
    assert response.status_code == 400
    assert Reservation.objects.count() == 1
    assert "Já existe reserva neste horário" in response.content.decode()


def test_post_saves_guests(client, resident, space):
    day = timezone.localdate() + timedelta(days=11)
    start = _aware(day, 11)
    end = start + timedelta(hours=1)
    client.force_login(resident)
    response = client.post(
        _create_url(space, day),
        _post_data(
            start,
            end,
            guests_count=3,
            guest_names=["Ana Silva", "  ", "Bruno Costa"],
        ),
    )
    assert response.status_code == 302
    reservation = Reservation.objects.get()
    names = list(reservation.guests.order_by("name").values_list("name", flat=True))
    assert names == ["Ana Silva", "Bruno Costa"]
    assert reservation.guests_count == 3


def test_post_outside_hours_returns_400(client, resident, space):
    day = timezone.localdate() + timedelta(days=12)
    start = _aware(day, 6)
    end = start + timedelta(hours=1)
    client.force_login(resident)
    response = client.post(
        _create_url(space, day),
        _post_data(start, end),
    )
    assert response.status_code == 400
    assert Reservation.objects.count() == 0
    assert "funcionamento" in response.content.decode().lower()


def test_staff_cannot_create_reservation(client, space, db):
    staff = User.objects.create_user(
        username="gestao",
        email="gestao@condo.local",
        password="condo123",
        role=User.Role.STAFF,
        is_staff=True,
    )
    day = timezone.localdate() + timedelta(days=13)
    start = _aware(day, 12)
    client.force_login(staff)
    response = client.post(
        _create_url(space, day),
        _post_data(start, start + timedelta(hours=1)),
    )
    assert response.status_code == 403
    assert Reservation.objects.count() == 0


def test_create_form_has_no_resumo_card(client, resident, space):
    day = timezone.localdate() + timedelta(days=4)
    start = _aware(day, 19)
    client.force_login(resident)
    response = client.get(
        reverse("reservation_create", kwargs={"slug": space.slug}),
        {"start": start.isoformat()},
    )
    html = response.content.decode()
    local = timezone.localtime(start)
    title = f"{space.name} · {local.strftime('%d/%m/%Y')}"
    assert title in html
    assert f"Data selecionada: {local.strftime('%d/%m/%Y')}" in html
    assert "resumo-reserva" not in html
    assert ">Resumo<" not in html
    assert "Nova reserva" not in html
    assert 'value="19:00"' in html
    assert 'min="08:00"' in html
    assert 'max="21:00"' in html


def test_post_rejects_tampered_date(client, resident, space):
    day = timezone.localdate() + timedelta(days=5)
    other = day + timedelta(days=1)
    start = _aware(other, 15)
    end = start + timedelta(hours=1)
    client.force_login(resident)
    response = client.post(
        _create_url(space, day),
        _post_data(start, end),
    )
    assert response.status_code == 400
    assert Reservation.objects.count() == 0
    assert "dia escolhido" in response.content.decode().lower()


def test_post_rejects_end_before_or_equal_start(client, resident, space):
    day = timezone.localdate() + timedelta(days=7)
    start = _aware(day, 15)
    client.force_login(resident)
    response = client.post(
        _create_url(space, day),
        _post_data(start, start),
    )
    assert response.status_code == 400
    assert Reservation.objects.count() == 0
    assert "posterior ao início" in response.content.decode().lower()


def test_cancel_within_deadline_via_view(client, resident, space):
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    client.force_login(resident)
    confirm = client.get(reverse("reservation_cancel", kwargs={"pk": reservation.pk}))
    assert confirm.status_code == 200
    assert (
        f"Tem certeza que deseja cancelar a reserva {reservation.protocol}?"
        in confirm.content.decode()
    )
    response = client.post(
        reverse("reservation_cancel", kwargs={"pk": reservation.pk}),
        follow=True,
    )
    assert response.status_code == 200
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CANCELLED
    assert f"Reserva {reservation.protocol} cancelada" in response.content.decode()
    assert "Cancelada" in response.content.decode()


def test_cancel_outside_deadline_via_view_keeps_confirmed(client, resident, space):
    start = timezone.now() + timedelta(hours=30)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    client.force_login(resident)
    response = client.post(
        reverse("reservation_cancel", kwargs={"pk": reservation.pk}),
        follow=True,
    )
    assert response.status_code == 200
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED
    assert "Prazo mínimo" in response.content.decode()


def test_reschedule_get_slot_opens_form_without_creating(client, resident, space):
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
        guest_names=["Ana"],
        notes="Festa",
    )
    new_start = _aware(day, 16)
    client.force_login(resident)
    before = Reservation.objects.count()
    response = client.get(
        reverse("reservation_reschedule", kwargs={"pk": reservation.pk}),
        {"start": new_start.isoformat()},
    )
    assert response.status_code == 200
    assert Reservation.objects.count() == before
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED
    html = response.content.decode()
    assert f"Reagendar {reservation.protocol} — {space.name}" in html
    assert 'value="16:00"' in html
    assert 'value="17:00"' in html
    assert "Ana" in html
    assert "Festa" in html
    assert 'type="time"' in html
    assert 'step="3600"' in html
    assert reverse("reservation_create", kwargs={"slug": space.slug}) not in html


def test_reschedule_calendar_links_to_form_not_create(client, resident, space):
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    client.force_login(resident)
    response = client.get(
        reverse("reservation_reschedule", kwargs={"pk": reservation.pk}),
        {"date": day.isoformat()},
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert f"Reagendar {reservation.protocol} — {space.name}" in html
    assert "atual" in html
    assert re.search(
        rf'href="[^"]*/reservas/{reservation.pk}/reagendar/\?start=[^"]*"',
        html,
    )
    assert reverse("reservation_create", kwargs={"slug": space.slug}) not in html
    assert "<form method=\"post\"" not in html.split('id="horarios-dia"')[1]


def test_reschedule_post_form_persists_longer_interval_and_guests(client, resident, space):
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
        guest_names=["Ana"],
        notes="Antiga",
    )
    new_start = _aware(day, 16)
    new_end = new_start + timedelta(hours=2)
    client.force_login(resident)
    response = client.post(
        f"{reverse('reservation_reschedule', kwargs={'pk': reservation.pk})}?date={day.isoformat()}",
        _post_data(
            new_start,
            new_end,
            guests_count=3,
            notes="Nova festa",
            guest_names=["Bruno", "Carla"],
        ),
        follow=True,
    )
    assert response.status_code == 200
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.RESCHEDULED
    new_res = Reservation.objects.exclude(pk=reservation.pk).get()
    assert new_res.status == Reservation.Status.CONFIRMED
    assert new_res.related_reservation_id == reservation.pk
    assert new_res.start_at == new_start
    assert new_res.end_at == new_end
    assert new_res.notes == "Nova festa"
    assert new_res.guests_count == 3
    names = list(new_res.guests.order_by("name").values_list("name", flat=True))
    assert names == ["Bruno", "Carla"]
    html = response.content.decode()
    assert "Reagendada" in html
    assert "Confirmada" in html
    assert new_res.protocol in html


def test_reschedule_post_overlap_with_third_fails(client, resident, space):
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    occupied_start = _aware(day, 16)
    create_reservation(
        space=space,
        user=resident,
        start_at=occupied_start,
        end_at=occupied_start + timedelta(hours=1),
    )
    client.force_login(resident)
    response = client.post(
        f"{reverse('reservation_reschedule', kwargs={'pk': reservation.pk})}?date={day.isoformat()}",
        _post_data(occupied_start, occupied_start + timedelta(hours=1)),
    )
    assert response.status_code == 400
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED
    assert Reservation.objects.filter(status=Reservation.Status.CONFIRMED).count() == 2
    assert "Já existe reserva neste horário" in response.content.decode()


def test_other_resident_cannot_cancel(client, resident, space):
    other = User.objects.create_user(
        username="res2",
        email="res2@condo.local",
        password="condo123",
        role=User.Role.RESIDENT,
        apartment="202",
    )
    day = timezone.localdate() + timedelta(days=10)
    start = _aware(day, 14)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    client.force_login(other)
    response = client.post(reverse("reservation_cancel", kwargs={"pk": reservation.pk}))
    assert response.status_code == 404
    reservation.refresh_from_db()
    assert reservation.status == Reservation.Status.CONFIRMED


def test_detail_shows_cancel_deadline_message(client, resident, space):
    start = timezone.now() + timedelta(hours=30)
    reservation = create_reservation(
        space=space,
        user=resident,
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    client.force_login(resident)
    response = client.get(
        reverse("reservation_detail", kwargs={"lookup": reservation.protocol})
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert (
        f"Cancelamento permitido até {space.min_cancel_hours}h antes do início."
        in html
    )
    assert "Reagendar" in html
