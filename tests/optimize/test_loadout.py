import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Arcane, Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.loadout import BuildError, loadout


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _mods(data: GameData, *names: str) -> list[Mod]:
    by_name = {m.name: m for m in data.mods.mods}
    return [by_name[n] for n in names]


def _arcane(data: GameData, name: str) -> Arcane:
    return next(a for a in data.arcanes if a.name == name)


@pytest.mark.parametrize(
    ("weapon", "mods", "bonus", "code"),
    [
        ("Soma Prime", ["Serration"] * 2, None, "duplicate_mod"),
        ("Soma Prime", ["Hornet Strike"], None, "incompatible_mod"),
        ("Soma Prime", ["Serration", "Amalgam Serration"], None, "family_clash"),
        ("Soma Prime", [], DamageType.HEAT, "no_bonus_element"),
        ("Kuva Hind", [], DamageType.IMPACT, "not_supported"),
    ],
)
def test_rejected_builds(
    gamedata: GameData, weapon: str, mods: list[str], bonus: DamageType | None, code: str
) -> None:
    with pytest.raises(BuildError) as error:
        loadout(_weapon(gamedata, weapon), _mods(gamedata, *mods), bonus)
    assert error.value.code == code


def test_at_most_eight_mods(gamedata: GameData) -> None:
    rifle = [m for m in gamedata.mods.mods if m.category == "primary" and m.family is None]
    with pytest.raises(BuildError, match="at most 8"):
        loadout(_weapon(gamedata, "Soma Prime"), rifle[:9])


@pytest.mark.parametrize(
    ("perks", "code"),
    [
        (["Nope"], "unknown_perk"),
        (["Fortifying Bloodshed", "Fortress Salvo"], "perk_tier_clash"),
    ],
)
def test_rejected_perks(gamedata: GameData, perks: list[str], code: str) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    with pytest.raises(BuildError) as error:
        loadout(soma, [], incarnon=gamedata.incarnon_by_id[soma.unique_name], perks=perks)
    assert error.value.code == code


def test_perks_need_an_incarnon_weapon(gamedata: GameData) -> None:
    with pytest.raises(BuildError, match="not an Incarnon"):
        loadout(_weapon(gamedata, "Kuva Hind"), [], perks=["Fortifying Bloodshed"])


def test_arcane_must_fit_the_gun(gamedata: GameData) -> None:
    with pytest.raises(BuildError) as error:
        loadout(_weapon(gamedata, "Lex Prime"), [], arcane=_arcane(gamedata, "Primary Merciless"))
    assert error.value.code == "incompatible_arcane"
