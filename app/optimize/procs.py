"""Expected status procs of one shot part: its own, plus the forced procs of mods."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.crit import non_crit_chance
from app.domain.effects import DamageType, Effect, Trigger
from app.domain.headshot import Head
from app.domain.hit import ModdedHit
from app.domain.status import boosted, chance_of_at_least_one, combined_chance, proc_shares
from app.gamedata.models import Attack, Headshot
from app.optimize.head import head_args
from app.optimize.shot import Shot, own_procs


@dataclass(frozen=True)
class Procs:
    """Expected procs of one shot part per shot."""

    normal: dict[DamageType, float]  # seeded by the average hit
    on_crit: dict[DamageType, float]  # applied by crits only: seeded by the average crit
    crit_ratio: float  # average crit multiplier / average hit multiplier

    @property
    def total(self) -> dict[DamageType, float]:
        keys = sorted(self.normal.keys() | self.on_crit.keys())
        return {t: self.normal.get(t, 0.0) + self.on_crit.get(t, 0.0) for t in keys}

    def seeded(self) -> list[tuple[DamageType, float, float]]:
        """(type, procs, seed ratio) with procs > 0."""
        out = [(t, p, 1.0) for t, p in self.normal.items() if p]
        return out + [(t, p, self.crit_ratio) for t, p in self.on_crit.items() if p]


def part_procs(
    hit: ModdedHit,
    attack: Attack | None,
    mark: Headshot | None,
    head: Head | None,
    shot: Shot,
    forced: Sequence[Effect],
) -> Procs:
    """Procs of one shot part: its own, plus the forced procs of mods (Hunter Munitions on
    crits, Internal Bleeding on Impact procs): sources of one type apply it at most once
    per projectile (checklist, Hunter Munitions + Internal Bleeding)."""
    normal = own_procs(hit, attack)
    args = head_args(attack, mark) if mark else None
    head = head if args is not None else None
    flat = bool(args and args.flat)
    f = shot.firing
    rate = f.fire_rate * shot.rate_factor if f.fire_rate else shot.rate
    shares = proc_shares(hit.damage)
    guaranteed = set((attack.forced_procs or []) if attack else [])
    crit: dict[DamageType, list[float]] = {}
    other: dict[DamageType, list[float]] = {}
    for e in forced:
        if e.damage_type is None:
            continue
        value = boosted(e.value, e.fire_rate_boost, rate)
        if e.trigger == Trigger.ON_CRIT:
            p = value * (1 - non_crit_chance(hit.crit_chance(head, flat=flat)))
            crit.setdefault(e.damage_type, []).append(p)
            continue
        on = e.trigger_damage_type
        if on in guaranteed:
            met = 1.0
        else:
            share = shares.get(on, 0.0) if on else 1.0
            met = chance_of_at_least_one(hit.status_chance, share)
        other.setdefault(e.damage_type, []).append(value * met)
    on_crit: dict[DamageType, float] = {}
    for dt in sorted(crit.keys() | other.keys()):
        first = combined_chance(crit.get(dt, []))
        both = combined_chance(crit.get(dt, []) + other.get(dt, []))
        on_crit[dt] = first * hit.multishot
        normal[dt] = normal.get(dt, 0.0) + (both - first) * hit.multishot
    return Procs(normal, on_crit, hit.crit_only_ratio(head, flat=flat))
