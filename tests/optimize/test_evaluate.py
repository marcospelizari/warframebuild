import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.evaluate import BuildError, Evaluation, evaluate


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


def test_incarnon_form_by_default(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    incarnon = gamedata.incarnon_by_id[soma.unique_name]
    e = evaluate(soma, [], incarnon=incarnon, perks=["Fortifying Bloodshed"])
    assert e.form == "incarnon"
    assert e.hit.multishot == 8
    assert e.fire_rate == pytest.approx(7)
    assert e.hit.base_total == pytest.approx(18 + 10)  # +10 per pellet (saved page note)


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
        evaluate(soma, [], incarnon=gamedata.incarnon_by_id[soma.unique_name], perks=perks)
    assert error.value.code == code


def test_perks_need_an_incarnon_weapon(gamedata: GameData) -> None:
    with pytest.raises(BuildError, match="not an Incarnon"):
        evaluate(_weapon(gamedata, "Kuva Hind"), [], perks=["Fortifying Bloodshed"])


# Step 5 checkpoint: arsenal numbers read in game (2026-11-09), normal form, perks as
# installed. The arsenal shows values before quantization and rounds what it displays.
SOMA_PERKS = ["Fortifying Bloodshed", "Kinetic Battle", "Fresh Havoc"]
LEX_PERKS = ["Hoplite Virtue", "Extended Volley", "Critical Parallel"]


def _run(data: GameData, gun: str, mods: list[str], perks: list[str]) -> Evaluation:
    weapon = next(w for w in data.weapons if w.name == gun)
    by_name = {m.name: m for m in data.mods.mods}
    chosen = [by_name[n] for n in mods]
    incarnon = data.incarnon_by_id[weapon.unique_name]
    return evaluate(weapon, chosen, incarnon=incarnon, perks=perks, form="normal")


def test_soma_prime_unmodded(gamedata: GameData) -> None:
    e = _run(gamedata, "Soma Prime", [], SOMA_PERKS)
    assert e.hit.arsenal_damage[DamageType.IMPACT] == pytest.approx(2.2, abs=0.05)


def test_soma_prime_modded(gamedata: GameData) -> None:
    mods = ["Serration", "Split Chamber", "Point Strike", "Vital Sense", "Hellfire"]
    e = _run(gamedata, "Soma Prime", mods, SOMA_PERKS)
    assert e.hit.multishot == pytest.approx(1.9)
    assert e.hit.critical_chance == pytest.approx(0.75)
    assert e.hit.critical_multiplier == pytest.approx(6.6)
    assert e.hit.arsenal_damage[DamageType.HEAT] == pytest.approx(52.5, abs=0.05)


def test_lex_prime_modded(gamedata: GameData) -> None:
    mods = [
        "Hornet Strike",
        "Barrel Diffusion",
        "Pistol Gambit",
        "Target Cracker",
        "Convulsion",
        "Pathogen Rounds",
    ]
    e = _run(gamedata, "Lex Prime", mods, LEX_PERKS)
    assert e.hit.multishot == pytest.approx(2.2)
    assert e.hit.critical_chance == pytest.approx(0.968, abs=0.0005)
    assert e.hit.critical_multiplier == pytest.approx(3.8, abs=0.05)
    assert e.hit.arsenal_damage[DamageType.CORROSIVE] == pytest.approx(1152, abs=0.5)


def test_incarnon_radial_part_counts(gamedata: GameData) -> None:
    # Laetum: direct Impact plus a 2 m Radiation radius (saved Laetum page).
    laetum = _weapon(gamedata, "Laetum")
    e = evaluate(laetum, [], incarnon=gamedata.incarnon_by_id[laetum.unique_name])
    assert e.direct_burst_dps == pytest.approx(3372.352, rel=1e-6)
    assert e.aoe_parts


def test_part_without_multishot_bonus(gamedata: GameData) -> None:
    # Burston: the Radial Attack ignores Multishot bonuses (saved Incarnon_Evolutions).
    burston = _weapon(gamedata, "Burston Prime")
    incarnon = gamedata.incarnon_by_id[burston.unique_name]
    e = evaluate(burston, _mods(gamedata, "Split Chamber"), incarnon=incarnon)
    assert e.direct_burst_dps == pytest.approx(1176.24, rel=1e-6)


def test_no_sustained_dps_when_magazine_cannot_fire(gamedata: GameData) -> None:
    # Onos Incarnon Form: 50 ammo per shot, normal magazine 20 (own magazine not modelled).
    onos = _weapon(gamedata, "Onos")
    e = evaluate(onos, [], incarnon=gamedata.incarnon_by_id[onos.unique_name])
    assert e.direct_sustained_dps is None
