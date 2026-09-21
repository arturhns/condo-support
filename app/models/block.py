from django.db import models
from django.utils.text import slugify


class Block(models.Model):
    """Agrupamento de unidades (torre, bloco, ala ou setor)."""

    name = models.CharField(
        "nome",
        max_length=120,
        unique=True,
        help_text="Bloco, torre, ala ou setor do condomínio.",
    )
    slug = models.SlugField(max_length=140, unique=True)
    code = models.CharField(
        "código",
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text="Código curto opcional (ex.: BRISAS, A).",
    )
    is_active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Bloco"
        verbose_name_plural = "Blocos"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.code == "":
            self.code = None
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
