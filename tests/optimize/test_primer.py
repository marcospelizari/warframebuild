import pytest

from app.domain.effects import DamageType
from app.gamedata.models import Mod
from app.gamedata.store import GameData
from app.optimize.conditions import resolve
from app.optimize.loadout import Loadout, loadout
from app.optimize.primer import BURST_S, FOLLOW_S, follow_up_times, primed
from app.optimize.timeline import Timeline


def _soma(data: GameData, *mods: str) -> Loadout:
    by_name: dict[str, Mod] = {m.name: m for m in data.mods.mods}
    weapon = next(w for w in data.weapons if w.name == "Soma Prime")
    return loadout(weapon, [by_name[n] for n in mods])


def test_follow_up_window_starts_when_the_burst_ends() -> None:
    times = follow_up_times()
    assert BURST_S < times[0] < times[-1] < BURST_S + FOLLOW_S


def test_corrosive_and_viral_prime_more_than_plain_damage(gamedata: GameData) -> None:
    """Priming:21-23: Viral and Corrosive are the elements to prime with."""
    plain = primed(_soma(gamedata, "Serration"), gamedata.enemies, gamedata.status_rules)
    corrosive = _soma(gamedata, "Infected Clip", "Stormbringer")
    viral = _soma(gamedata, "Infected Clip", "Cryo Rounds")
    for lo in (corrosive, viral):
        p = primed(lo, gamedata.enemies, gamedata.status_rules)
        assert p.boost > plain.boost >= 1.0
        assert p.status_types > 0
    assert set(plain.by_enemy) == {e.unique_name for e in gamedata.enemies}


def test_a_burst_wears_off_over_the_follow_up(gamedata: GameData) -> None:
    lo = _soma(gamedata, "Infected Clip", "Stormbringer")
    tl = Timeline(lo, resolve(lo, False), None, None, gamedata.status_rules, until=BURST_S)
    assert tl.times and tl.times[-1] <= BURST_S
    window = gamedata.status_rules.types[DamageType.CORROSIVE].duration_s * tl.duration
    early, late = tl.debuffs_at(BURST_S + 0.1), tl.debuffs_at(tl.times[-1] + window + 0.1)
    assert early.armor_kept < late.armor_kept == pytest.approx(1.0)  # Corrosive expired


def test_heat_armor_comes_back_after_the_last_burning_shot(gamedata: GameData) -> None:
    """Heat_Damage:81: the strip holds while burning, then returns step by step."""
    lo = _soma(gamedata, "Hellfire")
    tl = Timeline(lo, resolve(lo, False), None, None, gamedata.status_rules, until=BURST_S)
    life = gamedata.status_rules.types[DamageType.HEAT].duration_s * tl.duration
    end = tl.times[-1] + life
    kept = [tl.debuffs_at(end + s).armor_kept for s in (-0.1, 1.6, 3.1, 7.0)]
    assert kept == sorted(kept) and kept[0] < kept[-1] == pytest.approx(1.0)
