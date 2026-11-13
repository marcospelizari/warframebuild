"""Primer score (PLAN G49): how much more damage follow-up hits do on primed enemies.

The primer fires a burst, then stops; over the follow-up window an enemy's boost is its
effective HP unprimed / primed (Viral, Magnetic and armor strips, Priming:37), averaged over
time. The target gets every part's statuses; the enemies around it only the AoE parts', each
with its own status roll (Area_of_Effect:35; falloff lowers damage only, :18, :26). Enemies
around = blast area x an assumed crowd density. Enemies combine like the combat score:
geometric mean per faction, then over the factions. Body shots, no Bane: the follow-up
weapon's own damage types are not known.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.domain.combat import effective_hp, geometric_mean
from app.domain.hit import AttackStats
from app.domain.status_rules import StatusRules
from app.gamedata.builds import PrimerNumbers
from app.gamedata.enemies import Enemy
from app.gamedata.models import Attack
from app.optimize.conditions import resolve
from app.optimize.head import AOE
from app.optimize.loadout import Loadout, attack_stats
from app.optimize.search import rounded
from app.optimize.timeline import Debuffs, Timeline

BURST_S = 2.0  # the primer fires this long (project decision 2026-11-13)
FOLLOW_S = 6.0  # then the follow-up weapon hits for this long
SAMPLES = 60  # points in the follow-up window (midpoints of equal steps)
# Assumptions (shown with the build): a Steel Path crowd, enemies per m² of blast area,
# and the most one blast reaches.
DENSITY = 1 / 8
MAX_PRIMED = 12.0


@dataclass(frozen=True)
class Primed:
    boost: float  # follow-up damage multiplier on the target, combined over the enemies
    area_boost: float  # the same on an enemy near the target (1.0 without an AoE part)
    enemies: float  # enemies primed, the target included
    radius: float | None  # m, the largest modded AoE radius; None: no AoE part with one
    status_types: float  # different status types kept up on the target, window average

    @property
    def score(self) -> float:
        """Extra follow-up damage summed over the primed enemies (target = 1 unit)."""
        return (self.boost - 1) + (self.enemies - 1) * (self.area_boost - 1)


# "Good primer" (project decision 2026-11-13): a top Primer score, many status types kept up (a
# primer applies many status effects; an AoE gun with few elements is not one), and not a
# top damage gun (nobody primes with Incarnon Torid): G49's "high relative to its damage".
GOOD_SHARE = 0.10  # at most this share of all guns, the best Primer scores first
MIN_TYPES = 5.0  # status types kept up
DAMAGE_SHARE = 0.25  # Recommended score among the top 25%: a damage gun


def numbers(p: Primed) -> PrimerNumbers:
    return PrimerNumbers(
        boost=rounded(p.boost),
        area_boost=rounded(p.area_boost),
        enemies=rounded(p.enemies),
        radius=rounded(p.radius) if p.radius is not None else None,
        status_types=rounded(p.status_types),
    )


def good_primers(guns: dict[str, tuple[float, float, float]]) -> list[str]:
    """Slugs of good primers from each gun's (Primer score, status types kept up,
    Recommended score)."""
    if not guns:
        return []
    ranked = sorted((r for _, _, r in guns.values()), reverse=True)
    damage = ranked[max(0, math.ceil(len(ranked) * DAMAGE_SHARE) - 1)]
    eligible = [(-p, s) for s, (p, types, r) in guns.items() if types >= MIN_TYPES and r < damage]
    return sorted(s for _, s in sorted(eligible)[: math.ceil(len(guns) * GOOD_SHARE)])


def assumptions() -> list[str]:
    """How the Primer score counts, shown with the build."""
    return [
        f"The primer fires for {BURST_S:g} s, then the follow-up weapon hits for {FOLLOW_S:g} s; "
        "the boost is averaged over that time.",
        "Boost = how much less damage the enemy needs to die (effective HP), from Viral, "
        "Magnetic and armor stripped by Corrosive and Heat.",
        f"Enemies around the target: blast area x 1 enemy per {1 / DENSITY:g} m², at most "
        f"{MAX_PRIMED:g}; each rolls its own statuses from the blast.",
        "Slows, stuns and crit bonuses for the follow-up are not counted.",
    ]


def follow_up_times() -> list[float]:
    step = FOLLOW_S / SAMPLES
    return [BURST_S + (i + 0.5) * step for i in range(SAMPLES)]


def primer_shot(lo: Loadout) -> Loadout:
    """The shot the primer fires: the normal form's `primer_shot` attacks when the gun has
    them (Epitaph's uncharged shot; reference/blasts.json), else the scored shot."""
    names = lo.weapon.primer_shot if lo.form == "normal" else []
    if not names:
        return lo
    by_name = {a.name: a for a in lo.weapon.attacks}
    return replace(lo, parts=[(attack_stats(lo.weapon, by_name[n]), by_name[n]) for n in names])


def blast(lo: Loadout) -> Loadout | None:
    """The primer shot's blast part(s) alone: Incarnon Form parts with an AoE attack, else
    the gun's `blasts` (from its `primer_shot` parts when it has one)."""
    parts: list[tuple[AttackStats, Attack | None]]
    if lo.form != "normal":
        parts = [(s, a) for s, a in lo.parts if a is not None and a.shot_type == AOE]
    elif lo.weapon.primer_shot:
        parts = [(s, a) for s, a in lo.parts if a is not None and a.name in lo.weapon.blasts]
    else:
        by_name = {a.name: a for a in lo.weapon.attacks}
        found = [by_name[n] for n in lo.weapon.blasts if n in by_name]
        parts = [(attack_stats(lo.weapon, a), a) for a in found]
    return replace(lo, parts=parts) if parts else None


def radius(lo: Loadout) -> float | None:
    """The largest radius of `lo`'s AoE parts after radius mods (WFCD falloff end)."""
    hits = lo.shot(lo.body_bonuses()).hits
    sizes = [
        end * (1 + hit.blast_radius)
        for hit, (_, a) in zip(hits, lo.parts, strict=True)
        if (end := _end(a))
    ]
    return max(sizes) if sizes else None


def _end(a: Attack | None) -> float | None:
    return a.falloff.end if a is not None and a.falloff is not None else None


def enemies_reached(r: float | None) -> float:
    if r is None:
        return 1.0
    return min(MAX_PRIMED, max(1.0, DENSITY * math.pi * r * r))


def primed(lo: Loadout, enemies: Sequence[Enemy], rules: StatusRules) -> Primed:
    lo = primer_shot(lo)
    times = follow_up_times()
    target = Timeline(lo, resolve(lo, False), None, None, rules, until=BURST_S)
    area = blast(lo)
    r = radius(area) if area else None
    around = (
        Timeline(area, resolve(area, False), None, None, rules, shots=tuple(target.times))
        if area and r
        else None
    )
    return Primed(
        boost=_combined(enemies, [target.debuffs_at(t) for t in times]),
        area_boost=_combined(enemies, [around.debuffs_at(t) for t in times]) if around else 1.0,
        enemies=enemies_reached(r),
        radius=r,
        status_types=math.fsum(target.status_types_at(t) for t in times) / len(times),
    )


def _combined(enemies: Sequence[Enemy], states: Sequence[Debuffs]) -> float:
    by_faction: dict[str, list[float]] = {}
    for e in enemies:
        by_faction.setdefault(e.faction, []).append(_boost(e, states))
    factions = [geometric_mean(v) for _, v in sorted(by_faction.items())]
    return geometric_mean(factions) if factions else 1.0


def _boost(e: Enemy, states: Sequence[Debuffs]) -> float:
    """Time-averaged EHP ratio unprimed / primed."""
    plain = effective_hp(e.health, e.shield, e.armor)
    return math.fsum(
        plain
        / effective_hp(
            e.health,
            e.shield,
            e.armor,
            armor_kept=s.armor_kept,
            viral=s.viral,
            magnetic=s.magnetic,
        )
        for s in states
    ) / len(states)
