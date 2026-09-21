import pytest
from django.db import IntegrityError

from app.models import Block, User


@pytest.mark.django_db
def test_block_name_must_be_unique():
    Block.objects.create(name="Torre Brisas", slug="torre-brisas")
    with pytest.raises(IntegrityError):
        Block.objects.create(name="Torre Brisas", slug="torre-brisas-2")


@pytest.mark.django_db
def test_user_block_points_to_seeded_block():
    block = Block.objects.create(name="Torre Caminhos", slug="torre-caminhos")
    user = User.objects.create_user(
        username="morador_bloco",
        email="morador_bloco@condo.local",
        password="condo123",
        role=User.Role.RESIDENT,
        block=block,
        apartment="54",
    )
    user.refresh_from_db()
    assert user.block_id == block.pk
    assert user.block.name == "Torre Caminhos"
