# Data migration: User.tower (texto livre) → User.block (FK)

from django.db import migrations
from django.utils.text import slugify


def forwards_tower_to_block(apps, schema_editor):
    User = apps.get_model("app", "User")
    Block = apps.get_model("app", "Block")

    for user in User.objects.exclude(tower="").exclude(tower__isnull=True):
        name = user.tower.strip()
        if not name:
            continue
        block, _ = Block.objects.get_or_create(
            name=name,
            defaults={"slug": slugify(name), "is_active": True},
        )
        user.block = block
        user.save(update_fields=["block"])


def backwards_block_to_tower(apps, schema_editor):
    User = apps.get_model("app", "User")

    for user in User.objects.filter(block__isnull=False).select_related("block"):
        user.tower = user.block.name
        user.save(update_fields=["tower"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_block_and_user_block"),
    ]

    operations = [
        migrations.RunPython(forwards_tower_to_block, backwards_block_to_tower),
    ]
