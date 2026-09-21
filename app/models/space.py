from django.db import models
from django.utils.text import slugify


class Space(models.Model):
    """Área comum reservável (salão, churrasqueira, quadra etc.)."""

    name = models.CharField("nome", max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField("descrição", blank=True)
    capacity = models.PositiveIntegerField("capacidade")
    image = models.ImageField(
        "imagem",
        upload_to="spaces/",
        blank=True,
        null=True,
    )
    opening_time = models.TimeField("abertura")
    closing_time = models.TimeField("fechamento")
    min_cancel_hours = models.PositiveIntegerField(
        "antecedência mínima para cancelar (h)",
        default=48,
    )
    is_active = models.BooleanField("ativo", default=True)

    class Meta:
        verbose_name = "espaço"
        verbose_name_plural = "espaços"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
