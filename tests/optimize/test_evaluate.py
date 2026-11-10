import pytest

from app.domain import crit
from app.domain.effects import DamageType
from app.domain.headshot import Head
from app.domain.hit import AttackStats, modded_hit
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.evaluate import Evaluation, evaluate


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


def test_incarnon_form_by_default(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    incarnon = gamedata.incarnon_by_id[soma.unique_name]
    e = evaluate(soma, [], incarnon=incarnon, perks=["Fortifying Bloodshed"])
    assert e.form == "incarnon"
    assert e.hit.multishot == 8
    assert e.fire_rate == pytest.approx(7)
    assert e.hit.base_total == pytest.approx(18 + 10)  # +10 per pellet (saved page note)


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


def test_headshot_form_from_the_table(gamedata: GameData) -> None:
    latron = _weapon(gamedata, "Latron Prime")
    incarnon = gamedata.incarnon_by_id[latron.unique_name]
    e = evaluate(latron, [], incarnon=incarnon)
    assert e.headshot is not None and "Deadhead" in e.headshot.reason
    assert evaluate(_weapon(gamedata, "Braton Prime"), []).headshot is None


# Step 7b (PLAN G70): head DPS on the reference head, aiming, highest zoom.
GRINEER = Head(3.0, critical=True)


def test_body_forms_have_no_head_dps(gamedata: GameData) -> None:
    assert evaluate(_weapon(gamedata, "Braton Prime"), [], head=GRINEER).head_burst_dps is None


def test_sniper_head_dps_uses_the_highest_zoom(gamedata: GameData) -> None:
    rubico = _weapon(gamedata, "Rubico Prime")
    e = evaluate(rubico, [], head=GRINEER)
    assert e.head_burst_dps is not None
    zoom_cd = e.hit.critical_multiplier * 1.5  # 5x zoom: +50% critical multiplier
    crit_avg = crit.average_multiplier(e.hit.critical_chance, zoom_cd, headcrit=True)
    expected = e.hit.arsenal_total * 3 * crit_avg * e.fire_rate
    assert e.head_burst_dps == pytest.approx((expected, expected))


def test_galvanized_scope_counts_only_at_max_stacks(gamedata: GameData) -> None:
    rubico = _weapon(gamedata, "Rubico Prime")
    plain = evaluate(rubico, [], head=GRINEER).head_burst_dps
    scoped = evaluate(rubico, _mods(gamedata, "Galvanized Scope"), head=GRINEER)
    assert plain is not None and scoped.head_burst_dps is not None
    assert scoped.head_burst_dps[0] == pytest.approx(plain[0])
    assert scoped.head_burst_dps[1] > plain[1]
    assert scoped.head_triggered == ("Galvanized Scope",)
    assert scoped.direct_burst_dps == pytest.approx(evaluate(rubico, []).direct_burst_dps)


def test_deadhead_perk_doubles_the_head_factor(gamedata: GameData) -> None:
    latron = _weapon(gamedata, "Latron Prime")
    incarnon = gamedata.incarnon_by_id[latron.unique_name]
    # Normal form: one direct part (the Incarnon shot's AoE part never headshots).
    without = evaluate(latron, [], incarnon=incarnon, form="normal", head=GRINEER).head_burst_dps
    deadhead = evaluate(
        latron, [], incarnon=incarnon, perks=["Deadhead"], form="normal", head=GRINEER
    )
    assert without is not None and deadhead.head_burst_dps is not None
    assert deadhead.head_burst_dps[0] == pytest.approx(2 * without[0])


def test_lex_incarnon_head_is_flat(gamedata: GameData) -> None:
    """Saved Enemy_Body_Parts, Notes: Lex Incarnon Genesis heads at 1x, no Acuity; saved
    Critical_Hit:425: no critical-headshot bonus either, so unmodded = body damage."""
    lex = _weapon(gamedata, "Lex Prime")
    e = evaluate(lex, [], incarnon=gamedata.incarnon_by_id[lex.unique_name], head=GRINEER)
    assert e.headshot is not None and e.headshot.flat
    assert e.head_burst_dps == pytest.approx((e.direct_burst_dps, e.direct_burst_dps))


def test_headshot_fire_rate_perk_at_max_stacks(gamedata: GameData) -> None:
    furis = _weapon(gamedata, "Furis")
    e = evaluate(
        furis,
        [],
        incarnon=gamedata.incarnon_by_id[furis.unique_name],
        perks=["Headcracker"],
        head=GRINEER,
    )
    assert e.head_burst_dps is not None
    assert e.head_burst_dps[1] > e.head_burst_dps[0]
    assert e.head_triggered == ("Headcracker",)


def test_aoe_part_never_headshots(gamedata: GameData) -> None:
    """Saved Enemy_Body_Parts, Notes: radial parts hit at 1x, so Deadhead doubles only the
    direct part."""
    latron = _weapon(gamedata, "Latron Prime")
    incarnon = gamedata.incarnon_by_id[latron.unique_name]
    without = evaluate(latron, [], incarnon=incarnon, head=GRINEER)
    deadhead = evaluate(latron, [], incarnon=incarnon, perks=["Deadhead"], head=GRINEER)
    assert without.head_burst_dps is not None and deadhead.head_burst_dps is not None
    direct_on_head = without.hit.average_shot(head=GRINEER) * without.fire_rate
    gain = deadhead.head_burst_dps[0] - without.head_burst_dps[0]
    assert gain == pytest.approx(direct_on_head)


def test_zoom_not_modelled_reported_without_a_head(gamedata: GameData) -> None:
    komorex = _weapon(gamedata, "Komorex")
    assert "Zoom bonus" in evaluate(komorex, []).not_modelled
    assert "Zoom bonus" in evaluate(komorex, [], head=GRINEER).not_modelled


def test_cernos_prime_bonus_multiplies_on_top(gamedata: GameData) -> None:
    cernos = _weapon(gamedata, "Cernos Prime")
    assert all(h.separate_extra for h in cernos.headshot)
    e = evaluate(cernos, [], head=GRINEER)
    crit_avg = crit.average_multiplier(
        e.hit.critical_chance, e.hit.critical_multiplier, headcrit=True
    )
    expected = e.hit.arsenal_total * 3 * 1.5 * crit_avg * e.fire_rate
    assert e.head_burst_dps == pytest.approx((expected, expected))


def test_komorex_max_zoom(gamedata: GameData) -> None:
    """Saved Komorex, Notes: 3.5x zoom +100% Impact/Puncture/Slash (quantized like physical
    mods), -75% fire rate additive with mods."""
    komorex = _weapon(gamedata, "Komorex")
    assert komorex.zoom is not None
    zoom = [(x, x.value) for x in komorex.zoom.effects]
    base = AttackStats(
        damage=komorex.damage,
        critical_chance=komorex.critical_chance,
        critical_multiplier=komorex.critical_multiplier,
        status_chance=komorex.status_chance,
        multishot=komorex.multishot,
    )
    e = evaluate(komorex, [], head=GRINEER)
    expected = modded_hit(base, zoom).average_shot(head=GRINEER) * e.fire_rate * 0.25
    assert e.head_burst_dps is not None
    assert e.head_burst_dps[0] == pytest.approx(expected)
