import math
from dataclasses import replace

import pytest

from app.domain import debuffs
from app.domain.combat import INDEX
from app.domain.direct_bonus import DirectBonus
from app.domain.effects import DamageType
from app.domain.hit import with_direct_bonus
from app.domain.status import dot_seed, dot_tick
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.conditions import resolve
from app.optimize.evaluate import Loadout, loadout
from app.optimize.shot import own_procs
from app.optimize.timeline import Timeline

SLASH = DamageType.SLASH


def _lo(data: GameData, gun: str, *mods: str) -> Loadout:
    weapon: Weapon = next(w for w in data.weapons if w.name == gun)
    by_name: dict[str, Mod] = {m.name: m for m in data.mods.mods}
    return loadout(weapon, [by_name[n] for n in mods], form="normal")


def test_galvanized_bonus_follows_the_status_types_on_the_target(gamedata: GameData) -> None:
    """Galvanized_Aptitude:42: no bonus on the hit that procs, +40% x 2 stacks per status
    type on the following hits, added to the damage bonuses (Braton Prime: adding)."""
    lo = _lo(gamedata, "Braton Prime", "Serration", "Galvanized Aptitude")
    res = resolve(lo, on_head=False)
    events = Timeline(lo, res, None, None).events()
    hit, attack = res.shot.hits[0], lo.parts[0][1]
    assert math.fsum(events[0].armored) == pytest.approx(hit.average_shot())
    procs = own_procs(hit, attack)
    types = math.fsum(min(1.0, p) for p in procs.values())
    second = with_direct_bonus(hit, DirectBonus.ADDING, 0.8 * types)
    assert second.damage_multiplier == pytest.approx(2.65 + 0.8 * types)
    puncture = debuffs.PUNCTURE.value(procs.get(DamageType.PUNCTURE, 0.0))
    shot_2 = next(e for e in events if e.time > events[0].time and math.fsum(e.armored) > 0)
    assert math.fsum(shot_2.armored) == pytest.approx(second.average_shot(chance_add=puncture))


def test_hunter_munitions_bleeds_carry_the_crit(gamedata: GameData) -> None:
    """Hunter_Munitions: 30% forced Slash per crit; its bleed is seeded by the crit, not by
    the average hit."""
    lo = _lo(gamedata, "Braton Prime", "Hunter Munitions")
    res = resolve(lo, on_head=False)
    hit, attack = res.shot.hits[0], lo.parts[0][1]
    events = Timeline(lo, res, None, None).events()
    first = events[0].time
    tick = next(e for e in events if e.time == pytest.approx(first + 1.0))
    seed = dot_seed(hit.modded_base, hit.hit_factor())
    own = own_procs(hit, attack).get(SLASH, 0.0)
    forced = 0.3 * min(1.0, hit.critical_chance) * hit.multishot
    expected = own * dot_tick(seed, SLASH) + forced * dot_tick(seed * hit.crit_only_ratio(), SLASH)
    assert forced > 0
    assert tick.unarmored[INDEX[SLASH]] == pytest.approx(expected)


def test_no_direct_bonus_without_kill_stack_mods(gamedata: GameData) -> None:
    lo = _lo(gamedata, "Braton Prime", "Serration")
    res = resolve(lo, on_head=False)
    assert res.direct == 0
    with_bonus = Timeline(lo, replace(res, direct=0.8), None, None).events()
    plain = Timeline(lo, res, None, None).events()
    assert math.fsum(with_bonus[0].armored) == pytest.approx(math.fsum(plain[0].armored))
    total = [math.fsum(math.fsum(e.armored) for e in events) for events in (with_bonus, plain)]
    assert total[0] > total[1]
