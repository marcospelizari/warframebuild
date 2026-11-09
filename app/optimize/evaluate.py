"""One build from loaded data: arsenal stats and hit DPS (no search)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain import families
from app.domain.effects import DamageType, Stat, Support, Trigger
from app.domain.elements import ELEMENTS
from app.domain.fire_rate import Firing, effective_fire_rate, shooting_share
from app.domain.hit import AttackStats, Bonus, ModdedHit, modded_hit
from app.domain.stats import modded, modded_time, value_for
from app.gamedata.models import Attack, Effects, Headshot, Incarnon, Mod, Perk, Weapon

MAX_SLOTS = 8
BOW = "Bow"  # WFCD weapon_type
Form = Literal["normal", "incarnon"]
AOE = "AoE"  # WFCD shot_type


class BuildError(ValueError):
    def __init__(self, code: str, message: str, field: str) -> None:
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


@dataclass(frozen=True)
class Evaluation:
    hit: ModdedHit  # first part of the shot
    form: Form
    perks: list[str]
    fire_rate: float  # effective, shots/s
    magazine: float | None
    reload_time: float
    direct_burst_dps: float
    direct_sustained_dps: float | None  # None: one shot costs more ammo than the magazine
    bonus_element: tuple[DamageType, float] | None
    ammo_cost_assumed: bool  # attack lists none -> 1
    not_modelled: list[str]  # mods with partial/unsupported effects (R6)
    sets_ignored: list[str]  # set bonuses not applied yet
    inactive_perks: list[str]  # chosen perks that do nothing in this form
    aoe_parts: bool  # AoE parts counted at full damage on the target
    note: str | None  # main_attack.json limit for this gun
    headshot: Headshot | None  # this form is aimed at heads (R5); None = body


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


def bonuses(weapon: Weapon, entries: Sequence[Effects]) -> list[Bonus]:
    """Unconditional effects in slot order, max rank (Q33): what the arsenal shows."""
    return [
        (e, value_for(e, weapon.weapon_type))
        for entry in entries
        for e in entry.effects
        if e.trigger == Trigger.ALWAYS and not e.while_aiming
    ]


def chosen_perks(incarnon: Incarnon | None, names: Sequence[str]) -> list[Perk]:
    if names and incarnon is None:
        raise BuildError("no_perks", "not an Incarnon weapon", "perks")
    by_name = {p.name: p for p in incarnon.perks} if incarnon else {}
    out: list[Perk] = []
    for i, name in enumerate(names):
        perk = by_name.get(name)
        if perk is None:
            raise BuildError("unknown_perk", f"no perk {name!r}", f"perks[{i}]")
        if any(p.tier == perk.tier for p in out):
            raise BuildError("perk_tier_clash", f"two perks in EVO{perk.tier}", f"perks[{i}]")
        out.append(perk)
    return out


def _parts(
    weapon: Weapon, incarnon: Incarnon | None, form: Form
) -> list[tuple[AttackStats, Attack | None]]:
    """(stats, attack) per part of one shot; normal form = the DE summary + first attack."""
    if form == "normal":
        stats = AttackStats(
            damage=weapon.damage,
            critical_chance=weapon.critical_chance,
            critical_multiplier=weapon.critical_multiplier,
            status_chance=weapon.status_chance,
            multishot=weapon.multishot,
        )
        return [(stats, weapon.attacks[0] if weapon.attacks else None)]  # main attack: step 8
    if incarnon is None:
        raise ValueError(f"{weapon.name} has no Incarnon Form")
    attacks = {a.name: a for a in weapon.attacks}
    return [
        (
            AttackStats(
                damage=a.damage,
                critical_chance=a.critical_chance,
                critical_multiplier=a.critical_multiplier,
                status_chance=a.status_chance,
                multishot=a.multishot or weapon.multishot,
            ),
            a,
        )
        for a in (attacks[n] for n in incarnon.attacks)
    ]


def evaluate(
    weapon: Weapon,
    mods: Sequence[Mod],
    bonus: DamageType | None = None,
    incarnon: Incarnon | None = None,
    perks: Sequence[str] = (),
    form: Form | None = None,
) -> Evaluation:
    """`form` defaults to Incarnon Form for Incarnon guns (Q11)."""
    check(weapon, mods, bonus)
    picked = chosen_perks(incarnon, perks)
    form = form or ("incarnon" if incarnon else "normal")
    active = [p for p in picked if p.form in ("both", form)]
    b = bonuses(weapon, [m.effects for m in mods] + [p.effects for p in active])
    share = weapon.bonus_element.max_share if bonus and weapon.bonus_element else None
    bonus_element = (bonus, share) if bonus is not None and share is not None else None
    parts = _parts(weapon, incarnon, form)
    flat = set(incarnon.no_multishot) if incarnon and form == "incarnon" else set()
    no_ms = [x for x in b if x[0].stat != Stat.MULTISHOT]
    hits = [
        modded_hit(stats, no_ms if a and a.name in flat else b, bonus_element) for stats, a in parts
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
    rate = effective_fire_rate(firing, modded(1.0, Stat.FIRE_RATE, b))
    burst = math.fsum(h.average_shot() for h in hits) * rate
    return Evaluation(
        hit=hits[0],
        form=form,
        perks=[p.name for p in picked],
        fire_rate=rate,
        magazine=magazine,
        reload_time=reload,
        direct_burst_dps=burst,
        direct_sustained_dps=None
        if magazine is not None and firing.ammo_cost > magazine
        else burst * shooting_share(firing, rate),
        bonus_element=bonus_element,
        ammo_cost_assumed=ammo_cost is None,
        not_modelled=[m.name for m in mods if m.effects.support != Support.FULL]
        + [p.name for p in active if p.effects.support != Support.FULL],
        sets_ignored=sorted({m.mod_set for m in mods if m.mod_set}),
        inactive_perks=[p.name for p in picked if p not in active],
        aoe_parts=any(a is not None and a.shot_type == AOE for _, a in parts[1:]),
        note=incarnon.note if incarnon and form == "incarnon" else None,
        headshot=next((h for h in weapon.headshot if h.form == form), None),
    )
