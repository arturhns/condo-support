from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Usuário do condomínio com papel e unidade."""

    class Role(models.TextChoices):
        RESIDENT = "resident", "Morador"
        STAFF = "staff", "Gestão"
        ADMIN = "admin", "Admin"

    email = models.EmailField("e-mail", unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RESIDENT,
    )
    block = models.ForeignKey(
        "app.Block",
        on_delete=models.PROTECT,
        related_name="residents",
        null=True,
        blank=True,
        verbose_name="Bloco",
    )
    apartment = models.CharField("apartamento", max_length=20, blank=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self) -> str:
        return self.email or self.username
