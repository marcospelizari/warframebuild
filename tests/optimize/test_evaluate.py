import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.evaluate import BuildError, evaluate


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _mods(data: GameData, *names: str) -> list[Mod]:
    by_name = {m.name: m for m in data.mods.mods}
    return [by_name[n] for n in names]


def test_unmodded_direct_dps(gamedata: GameData) -> None:
    e = evaluate(_weapon(gamedata, "Soma Prime"), [])
    assert e.direct_burst_dps == pytest.approx(12 * (1 + 0.3 * (3 - 1)) * 15)
    shots = 200
    assert e.direct_sustained_dps == pytest.approx(e.direct_burst_dps * shots / (15 * 3 + shots))


def test_damage_and_multishot_mods(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    plain = evaluate(soma, [])
    modded = evaluate(soma, _mods(gamedata, "Serration", "Split Chamber"))
    assert modded.hit.multishot == pytest.approx(1.9)
    assert modded.direct_burst_dps == pytest.approx(plain.direct_burst_dps * 2.65 * 1.9, rel=0.01)


def test_progenitor_bonus_at_max_share(gamedata: GameData) -> None:
    e = evaluate(_weapon(gamedata, "Kuva Hind"), [], DamageType.HEAT)
    assert e.bonus_element == (DamageType.HEAT, 0.6)
    assert e.hit.damage[DamageType.HEAT] == pytest.approx(19 * 30 / 32)  # 18 quantized


def test_bow_uses_wiki_reload(gamedata: GameData) -> None:
    assert evaluate(_weapon(gamedata, "Nataruk"), []).reload_time == pytest.approx(0.6)


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
        evaluate(_weapon(gamedata, weapon), _mods(gamedata, *mods), bonus)
    assert error.value.code == code


def test_at_most_eight_mods(gamedata: GameData) -> None:
    rifle = [m for m in gamedata.mods.mods if m.category == "primary" and m.family is None]
    with pytest.raises(BuildError, match="at most 8"):
        evaluate(_weapon(gamedata, "Soma Prime"), rifle[:9])
