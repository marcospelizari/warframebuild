import pytest
from pydantic import ValidationError

from app.domain.auras import Aura, Auras
from app.domain.effects import Effect, Stat

AMP = Aura(
    unique_name="amp",
    name="Rifle Amp",
    weapon_types=["Rifle", "Bow"],
    effect=Effect(stat=Stat.DAMAGE, value=0.27),
    source=["Rifle_Amp:29"],
)
PROJECTION = Aura(
    unique_name="cp", name="Corrosive Projection", weapon_types=None, armor_kept=0.82, source=[]
)


def test_an_aura_fits_its_weapon_types_or_every_gun() -> None:
    """Saved Rifle_Amp:29: rifles, bows, snipers and launchers, not shotguns."""
    table = Auras(auras=[AMP, PROJECTION])
    assert table.for_weapon("Bow") == [AMP, PROJECTION]
    assert table.for_weapon("Shotgun") == [PROJECTION]


def test_an_aura_changes_the_gun_or_the_enemy_never_both() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        Aura.model_validate(AMP.model_dump() | {"armor_kept": 0.82})
    with pytest.raises(ValidationError, match="exactly one"):
        Aura(unique_name="x", name="x", weapon_types=None, source=[])
