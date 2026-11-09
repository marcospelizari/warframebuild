"""One build from loaded data: arsenal stats and direct DPS (step 4.6, no search)."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain import families
from app.domain.effects import DamageType, Stat, Support, Trigger
from app.domain.elements import ELEMENTS
from app.domain.fire_rate import Firing, effective_fire_rate, shooting_share
from app.domain.hit import AttackStats, Bonus, ModdedHit, modded_hit
from app.domain.stats import modded, modded_time, value_for
from app.gamedata.models import Mod, Weapon

MAX_SLOTS = 8
BOW = "Bow"  # WFCD weapon_type


class BuildError(ValueError):
    def __init__(self, code: str, message: str, field: str) -> None:
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


@dataclass(frozen=True)
class Evaluation:
    hit: ModdedHit
    fire_rate: float  # effective, shots/s
    magazine: float | None
    reload_time: float
    direct_burst_dps: float
    direct_sustained_dps: float
    bonus_element: tuple[DamageType, float] | None
    ammo_cost_assumed: bool  # attack lists none -> 1
    not_modelled: list[str]  # mods with partial/unsupported effects (R6)
    sets_ignored: list[str]  # set bonuses not applied yet


def check(weapon: Weapon, mods: Sequence[Mod], bonus: DamageType | None) -> None:
    """Build rules /calc enforces now; mod compatibility tags follow in step 8 (G56)."""
    if len(mods) > MAX_SLOTS:
        raise BuildError("too_many_mods", f"at most {MAX_SLOTS} mods", "mods")
    seen: set[str] = set()
    for i, m in enumerate(mods):
        if m.unique_name in seen:
            raise BuildError("duplicate_mod", f"{m.name} equipped twice", f"mods[{i}]")
        seen.add(m.unique_name)
        if m.category != weapon.category:
            raise BuildError("incompatible_mod", f"{m.name} is a {m.category} mod", f"mods[{i}]")
    clash = families.clashes((m.unique_name, m.family) for m in mods)
    if clash:
        names = {m.unique_name: m.name for m in mods}
        a, b = clash[0]
        raise BuildError("family_clash", f"{names[a]} and {names[b]} clash", "mods")
    if bonus is not None:
        allowed = weapon.bonus_element.elements if weapon.bonus_element else []
        if bonus not in allowed:
            raise BuildError(
                "no_bonus_element", f"{weapon.name} has no {bonus} bonus", "bonus_element"
            )
        if bonus not in ELEMENTS:
            raise BuildError("not_supported", f"{bonus} bonus not modelled yet", "bonus_element")


def bonuses(weapon: Weapon, mods: Sequence[Mod]) -> list[Bonus]:
    """Unconditional effects in slot order, max rank (Q33): what the arsenal shows."""
    return [
        (e, value_for(e, weapon.weapon_type))
        for m in mods
        for e in m.effects.effects
        if e.trigger == Trigger.ALWAYS and not e.while_aiming
    ]


def evaluate(weapon: Weapon, mods: Sequence[Mod], bonus: DamageType | None = None) -> Evaluation:
    check(weapon, mods, bonus)
    b = bonuses(weapon, mods)
    share = weapon.bonus_element.max_share if bonus and weapon.bonus_element else None
    bonus_element = (bonus, share) if bonus is not None and share is not None else None
    hit = modded_hit(
        AttackStats(
            damage=weapon.damage,
            critical_chance=weapon.critical_chance,
            critical_multiplier=weapon.critical_multiplier,
            status_chance=weapon.status_chance,
            multishot=weapon.multishot,
        ),
        b,
        bonus_element,
    )
    attack = weapon.attacks[0] if weapon.attacks else None  # main attack: step 6 (V6)
    ammo_cost = attack.ammo_cost if attack and attack.ammo_cost is not None else None
    magazine = (
        None
        if weapon.magazine_size is None
        else modded(weapon.magazine_size, Stat.MAGAZINE_CAPACITY, b)
    )
    reload = modded_time(weapon.reload_time, modded(1.0, Stat.RELOAD_SPEED, b) - 1)
    firing = Firing(
        fire_rate=weapon.fire_rate,
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
    rate = effective_fire_rate(firing, modded(1.0, Stat.FIRE_RATE, b))
    burst = hit.average_shot() * rate
    return Evaluation(
        hit=hit,
        fire_rate=rate,
        magazine=magazine,
        reload_time=reload,
        direct_burst_dps=burst,
        direct_sustained_dps=burst * shooting_share(firing, rate),
        bonus_element=bonus_element,
        ammo_cost_assumed=ammo_cost is None,
        not_modelled=[m.name for m in mods if m.effects.support != Support.FULL],
        sets_ignored=sorted({m.mod_set for m in mods if m.mod_set}),
    )
