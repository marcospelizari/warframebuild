import math

import pytest

from app.domain.class_mechanics import beam_ramp
from app.domain.combat import INDEX
from app.domain.effects import DamageType
from app.domain.fire_rate import shot_times
from app.domain.headshot import Head
from app.domain.status import blast_proc, expected_procs, proc_shares
from app.gamedata.models import Enemy, Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.combat import combat, timeline
from app.optimize.loadout import Loadout, loadout


def _weapon(data: GameData, name: str) -> Weapon:
    return next(w for w in data.weapons if w.name == name)


def _enemy(data: GameData, name: str) -> Enemy:
    return next(e for e in data.enemies if e.name == name)


def _mods(data: GameData, *names: str) -> list[Mod]:
    by_name = {m.name: m for m in data.mods.mods}
    return [by_name[n] for n in names]


def test_sniper_hits_the_enemy_head_with_the_shot_combo(gamedata: GameData) -> None:
    """Rubico Prime (minimum combo 1): the first shot already builds 1.5x (G73 screenshots),
    lands at one interval (G72) on the Lancer's 3x headcrit head (Enemy_Body_Parts:322)."""
    lo = loadout(_weapon(gamedata, "Rubico Prime"), [])
    shot = lo.shot(lo.head_bonuses(True))
    first = timeline(lo, _enemy(gamedata, "Lancer"), gamedata.status_rules)[0]
    assert first.time == pytest.approx(1 / shot.rate)
    expected = shot.hits[0].average_shot(head=Head(3.0, critical=True)) * 1.5
    assert math.fsum(first.armored) == pytest.approx(expected)


def test_enemy_without_a_head_spot_takes_body_hits_without_headshot_bonuses(
    gamedata: GameData,
) -> None:
    """Argon Scope needs weak-point hits: none on the Lumbering Fragment (no headshot spot,
    Enemy_Body_Parts:840); aiming bonuses (zoom) still count."""
    lo = loadout(_weapon(gamedata, "Rubico Prime"), _mods(gamedata, "Argon Scope"))
    aimed = lo.shot(lo.head_bonuses(False)).hits[0]
    first = timeline(lo, _enemy(gamedata, "Lumbering Fragment"), gamedata.status_rules)[0]
    assert math.fsum(first.armored) == pytest.approx(aimed.average_shot() * 1.5)
    triggered = lo.shot(lo.head_bonuses(True)).hits[0]
    assert triggered.critical_chance > aimed.critical_chance  # what a head would add


def test_target_acquired_reaches_the_head_hit(gamedata: GameData) -> None:
    """G73 through the build path: Rubico Prime with Target Acquired, non-crit head hit on a
    3x head = body x 3 x 1.6 (Simulacrum: body 381, head 1.8k)."""
    lo = loadout(_weapon(gamedata, "Rubico Prime"), _mods(gamedata, "Target Acquired"))
    hit = lo.shot(lo.head_bonuses(True)).hits[0]
    no_crit = -hit.head_critical_chance
    head = hit.hit_factor(head=Head(3.0, critical=True), chance_add=no_crit)
    body = hit.hit_factor(chance_add=-hit.critical_chance)
    assert head / body == pytest.approx(3 * 1.6)


def test_charge_weapon_first_shot_at_the_charge_time(gamedata: GameData) -> None:
    """G72: Opticor (2 s charge, then 1 s between shots) lands its first shot at 2 s."""
    events = timeline(
        loadout(_weapon(gamedata, "Opticor"), []), _enemy(gamedata, "Lancer"), gamedata.status_rules
    )
    assert events[0].time == pytest.approx(2.0)


def test_beam_ramps_up_on_the_target(gamedata: GameData) -> None:
    """Continuous_Weapon (checklist, Beam ramp-up): 20% at first contact, 100% at 0.6 s."""
    lo = loadout(_weapon(gamedata, "Ignis Wraith"), [])
    events = timeline(lo, _enemy(gamedata, "Charger"), gamedata.status_rules)
    full = lo.shot(lo.body_bonuses()).hits[0].average_shot()
    first = events[0]
    assert math.fsum(first.armored) == pytest.approx(full * beam_ramp(0.2, first.time))
    late = next(e for e in events if e.time > 0.7)
    assert math.fsum(late.armored) >= full


def test_slash_procs_tick_without_armor_one_second_after_the_hit(gamedata: GameData) -> None:
    lo = loadout(_weapon(gamedata, "Soma Prime"), [])
    events = timeline(lo, _enemy(gamedata, "Lancer"), gamedata.status_rules)
    first_shot = events[0].time
    tick = next(e for e in events if e.unarmored[INDEX[DamageType.SLASH]] > 0)
    assert tick.time == pytest.approx(first_shot + 1.0)
    assert tick.armored[INDEX[DamageType.SLASH]] == 0 or tick.time != first_shot


def _stacks(lo: Loadout, dt: DamageType, at: float, seconds: float) -> float:
    """Expected stacks at `at`: procs per shot x shots in the window before it."""
    shot = lo.shot(lo.body_bonuses())
    hit = shot.hits[0]
    per_shot = expected_procs(hit.status_chance, proc_shares(hit.damage))[dt] * hit.multishot
    times = shot_times(shot.firing, shot.rate_factor, at)
    before = at - 1e-6  # the model's own tolerance: a shot never counts at its own time
    return per_shot * sum(1 for t in times if before - seconds < t < before)


def test_corrosive_procs_strip_armor_over_time(gamedata: GameData) -> None:
    lo = loadout(_weapon(gamedata, "Soma Prime"), _mods(gamedata, "Infected Clip", "Stormbringer"))
    events = timeline(lo, _enemy(gamedata, "Heavy Gunner"), gamedata.status_rules)
    assert events[0].armor_kept == 1.0  # no stack before the first hit lands
    last = events[-1]
    stacks = _stacks(lo, DamageType.CORROSIVE, last.time, 8.0)  # 8 s each (Corrosive_Damage:21)
    assert last.armor_kept == pytest.approx(
        1 - gamedata.status_rules.stacking(DamageType.CORROSIVE).value(stacks)
    )
    assert last.armor_kept < events[len(events) // 4].armor_kept < 1


def test_viral_procs_amplify_health_damage(gamedata: GameData) -> None:
    lo = loadout(_weapon(gamedata, "Soma Prime"), _mods(gamedata, "Infected Clip", "Cryo Rounds"))
    events = timeline(lo, _enemy(gamedata, "Lancer"), gamedata.status_rules)
    last = events[-1]
    stacks = _stacks(lo, DamageType.VIRAL, last.time, 6.0)
    assert events[0].viral == 1.0
    assert last.viral == pytest.approx(
        1 + gamedata.status_rules.stacking(DamageType.VIRAL).value(stacks)
    )


def test_combat_scores_every_enemy_and_faction(gamedata: GameData) -> None:
    lo = loadout(_weapon(gamedata, "Soma Prime"), _mods(gamedata, "Serration"))
    c = combat(lo, gamedata.enemies, gamedata.factions, gamedata.status_rules)
    assert len(c.enemies) == len(gamedata.enemies)
    assert set(c.factions) == {e.faction for e in gamedata.enemies}
    logs = [math.log(v) for v in c.factions.values()]
    assert c.score == pytest.approx(math.exp(sum(logs) / len(logs)))
    killed = [r for r in c.enemies if r.outcome.ttk is not None]
    assert all(r.outcome.cost == r.outcome.ttk for r in killed)


def test_more_damage_kills_faster(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    plain = combat(
        loadout(soma, []), gamedata.enemies, gamedata.factions, gamedata.status_rules
    ).score
    modded = combat(
        loadout(soma, _mods(gamedata, "Serration", "Split Chamber")),
        gamedata.enemies,
        gamedata.factions,
        gamedata.status_rules,
    ).score
    assert modded < plain


def test_vectis_incarnon_counts_three_embed_hits(gamedata: GameData) -> None:
    vectis = _weapon(gamedata, "Vectis Prime")
    incarnon = gamedata.incarnon_by_id[vectis.unique_name]
    parts = [a for a in incarnon.attacks if a == "Incarnon Form Embed AoE"]
    assert len(parts) == 3  # PLAN G75, video evidence
    lo = loadout(vectis, [], None, incarnon)
    assert len(lo.parts) == 4


def test_blast_stack_hits_its_target_after_the_fuse(gamedata: GameData) -> None:
    """Blast_Damage: each stack deals 0.3 x modded base x crit when its 1.5 s fuse ends."""
    lo = loadout(_weapon(gamedata, "Soma Prime"), _mods(gamedata, "Hellfire", "Cryo Rounds"))
    events = timeline(lo, _enemy(gamedata, "Charger"), gamedata.status_rules)
    hit = lo.shot(lo.body_bonuses()).hits[0]
    per_shot = expected_procs(hit.status_chance, proc_shares(hit.damage))[DamageType.BLAST]
    fuse_end = events[0].time + 1.5  # between two shots (every 1/15 s): only the stack hit
    first_blast = next(e for e in events if abs(e.time - fuse_end) < 1e-6)
    stack = blast_proc(
        gamedata.status_rules.blast, hit.modded_base, hit.hit_factor()
    )  # no Puncture stack yet on shot 1
    assert first_blast.armored[INDEX[DamageType.BLAST]] == pytest.approx(
        per_shot * hit.multishot * stack
    )
    assert sum(first_blast.armored) == first_blast.armored[INDEX[DamageType.BLAST]]


def test_bane_multiplies_hits_against_its_faction_only(gamedata: GameData) -> None:
    soma = _weapon(gamedata, "Soma Prime")
    bane = _mods(gamedata, "Bane of Grineer")
    lancer, crewman = _enemy(gamedata, "Lancer"), _enemy(gamedata, "Crewman")
    factor = bane[0].effects.effects[0].value  # x1.3, a separate multiplier
    plain = math.fsum(timeline(loadout(soma, []), lancer, gamedata.status_rules)[0].armored)
    banned = math.fsum(timeline(loadout(soma, bane), lancer, gamedata.status_rules)[0].armored)
    assert banned == pytest.approx(plain * factor)
    other = math.fsum(timeline(loadout(soma, bane), crewman, gamedata.status_rules)[0].armored)
    assert other == pytest.approx(
        math.fsum(timeline(loadout(soma, []), crewman, gamedata.status_rules)[0].armored)
    )


@pytest.mark.parametrize(("name", "beam"), [("Torid", True), ("Atomos", False)])
def test_beam_ramp_follows_the_scored_form(gamedata: GameData, name: str, beam: bool) -> None:
    """Continuous_Weapon:47-71: Torid is a beam only in Incarnon Form, Atomos only in its
    normal form (its Incarnon Form is Semi-Auto in the saved module)."""
    weapon = _weapon(gamedata, name)
    lo = loadout(weapon, [], None, gamedata.incarnon_by_id[weapon.unique_name])
    assert lo.form == "incarnon"
    events = timeline(lo, _enemy(gamedata, "Charger"), gamedata.status_rules)
    full = math.fsum(h.average_shot() for h in lo.shot(lo.body_bonuses()).hits)
    first = math.fsum(events[0].armored)
    if beam:
        assert first == pytest.approx(full * beam_ramp(0.2, events[0].time))
    else:
        assert first == pytest.approx(full)


def test_bow_slowed_past_minus_100_percent_still_fires(gamedata: GameData) -> None:
    """Review 2026-11-11: Lenz + Critical Delay + Vile Precision (x2 on bows) divided by
    zero; it fires at the 10x charge (saved Fire_Rate:29)."""
    lenz = _weapon(gamedata, "Lenz")
    mods = _mods(gamedata, "Amalgam Serration", "Critical Delay", "Vile Precision")
    result = combat(loadout(lenz, mods), gamedata.enemies, gamedata.factions, gamedata.status_rules)
    assert math.isfinite(result.score) and result.score > 0
    assert (
        timeline(loadout(lenz, mods), gamedata.enemies[0], gamedata.status_rules) == []
    )  # 1st shot at 12 s > cap
