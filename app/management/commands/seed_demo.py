from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from app.models import Block, Reservation, Space, User
from app.services.reservations import create_reservation


class Command(BaseCommand):
    help = "Cria dados de demonstração do CondoAgenda (idempotente)."

    def handle(self, *args, **options):
        blocks = {}
        for name in ("Torre Brisas", "Torre Caminhos"):
            block, created = Block.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "is_active": True},
            )
            blocks[name] = block
            msg = "criado" if created else "já existe"
            self.stdout.write(f"Bloco {block.name}: {msg}.")

        staff, created = User.objects.get_or_create(
            username="staff",
            defaults={
                "email": "staff@condo.local",
                "role": User.Role.STAFF,
                "is_staff": True,
            },
        )
        if created or not staff.has_usable_password():
            staff.set_password("condo123")
            staff.email = "staff@condo.local"
            staff.role = User.Role.STAFF
            staff.is_staff = True
            staff.save()
            self.stdout.write(self.style.SUCCESS("Usuário staff criado/atualizado."))
        else:
            self.stdout.write("Usuário staff já existe.")

        residents = [
            ("morador1", "morador1@condo.local", "Torre Brisas", "36"),
            ("morador2", "morador2@condo.local", "Torre Caminhos", "54"),
        ]
        resident_objs = []
        for username, email, block_name, apartment in residents:
            block = blocks[block_name]
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": User.Role.RESIDENT,
                    "block": block,
                    "apartment": apartment,
                },
            )
            if created or not user.has_usable_password():
                user.set_password("condo123")
                user.email = email
                user.role = User.Role.RESIDENT
                user.block = block
                user.apartment = apartment
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Usuário {email} criado/atualizado.")
                )
            else:
                # Garante bloco/apto corretos em re-seed
                if user.block_id != block.pk or user.apartment != apartment:
                    user.block = block
                    user.apartment = apartment
                    user.save(update_fields=["block", "apartment"])
                self.stdout.write(f"Usuário {email} já existe.")
            resident_objs.append(user)

        spaces_data = [
            {
                "name": "Salão de Festas",
                "slug": "salao-de-festas",
                "capacity": 40,
                "description": "Salão para festas e eventos do condomínio.",
            },
            {
                "name": "Churrasqueira",
                "slug": "churrasqueira",
                "capacity": 20,
                "description": "Área gourmet com churrasqueira.",
            },
            {
                "name": "Quadra",
                "slug": "quadra",
                "capacity": 12,
                "description": "Quadra poliesportiva.",
            },
        ]
        spaces = {}
        for data in spaces_data:
            space, created = Space.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "capacity": data["capacity"],
                    "opening_time": time(8, 0),
                    "closing_time": time(22, 0),
                    "min_cancel_hours": 48,
                    "is_active": True,
                },
            )
            spaces[data["slug"]] = space
            msg = "criado" if created else "já existe"
            self.stdout.write(f"Espaço {space.name}: {msg}.")

        salao = spaces["salao-de-festas"]
        morador1 = resident_objs[0]
        now = timezone.now()

        # Reserva futura confirmada
        future_start = (now + timedelta(days=7)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        future_end = future_start + timedelta(hours=3)
        if not Reservation.objects.filter(
            space=salao, user=morador1, start_at=future_start
        ).exists():
            create_reservation(
                space=salao,
                user=morador1,
                start_at=future_start,
                end_at=future_end,
                notes="Reserva demo futura",
                guests_count=5,
            )
            self.stdout.write(self.style.SUCCESS("Reserva futura criada."))
        else:
            self.stdout.write("Reserva futura já existe.")

        # Reserva passada
        past_start = (now - timedelta(days=10)).replace(
            hour=15, minute=0, second=0, microsecond=0
        )
        past_end = past_start + timedelta(hours=2)
        if not Reservation.objects.filter(
            space=salao, user=morador1, start_at=past_start
        ).exists():
            create_reservation(
                space=salao,
                user=morador1,
                start_at=past_start,
                end_at=past_end,
                notes="Reserva demo passada",
                guests_count=3,
            )
            self.stdout.write(self.style.SUCCESS("Reserva passada criada."))
        else:
            self.stdout.write("Reserva passada já existe.")

        self.stdout.write(self.style.SUCCESS("seed_demo concluído."))
