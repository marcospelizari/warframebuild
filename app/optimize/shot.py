"""One shot of a build: modded hit per shot part and the firing that sets the rate."""

from dataclasses import dataclass
from typing import Literal

from app.domain.effects import DamageType, Stat
from app.domain.fire_rate import Firing, effective_fire_rate
from app.domain.hit import AttackStats, Bonus, ModdedHit, modded_hit
from app.domain.stats import modded, modded_time
from app.domain.status import expected_procs, proc_shares
from app.gamedata.models import Attack, Weapon

BOW = "Bow"  # WFCD weapon_type
Form = Literal["normal", "incarnon"]


@dataclass(frozen=True)
class Shot:
    hits: list[ModdedHit]  # one per shot part
    rate: float  # effective shots/s
    rate_factor: float  # fire-rate multiplier from mods (charge time divides by it)
    magazine: float | None
    firing: Firing
    ammo_cost_assumed: bool


def shot(
    weapon: Weapon,
    parts: list[tuple[AttackStats, Attack | None]],
    no_multishot: set[str],
    b: list[Bonus],
    bonus_element: tuple[DamageType, float] | None,
    form: Form,
) -> Shot:
    no_ms = [x for x in b if x[0].stat != Stat.MULTISHOT]
    hits = [
        modded_hit(stats, no_ms if a and a.name in no_multishot else b, bonus_element)
        for stats, a in parts
    ]
    attack = parts[0][1]
    ammo_cost = attack.ammo_cost if attack and attack.ammo_cost is not None else None
    magazine = (
        None
        if weapon.magazine_size is None
        else modded(weapon.magazine_size, Stat.MAGAZINE_CAPACITY, b)
    )
    reload = modded_time(weapon.reload_time, modded(1.0, Stat.RELOAD_SPEED, b) - 1)
    base_rate = attack.fire_rate if form == "incarnon" and attack else None
    firing = Firing(
        fire_rate=base_rate or weapon.fire_rate,
        charge_time=attack.charge_time if attack else None,
        burst_count=attack.burst_count if attack else None,
        burst_delay=attack.burst_delay if attack else None,
        bow=weapon.weapon_type == BOW,
        magazine=magazine,
        ammo_cost=1.0 if ammo_cost is None else ammo_cost,
        reload_time=reload,  # battery guns: recharge = reload (G59)
        no_reload=weapon.no_reload,
        reload_replaces_shot=weapon.reload_replaces_shot,
    )
    factor = modded(1.0, Stat.FIRE_RATE, b)
    rate = effective_fire_rate(firing, factor)
    return Shot(hits, rate, factor, magazine, firing, ammo_cost is None)


def own_procs(hit: ModdedHit, attack: Attack | None) -> dict[DamageType, float]:
    """Expected damage-type procs of one shot part per shot: status chance by damage share
    plus the attack's forced procs, x multishot."""
    forced = (attack.forced_procs or []) if attack is not None else []
    each = expected_procs(hit.status_chance, proc_shares(hit.damage), forced)
    return {t: p * hit.multishot for t, p in each.items() if isinstance(t, DamageType)}
