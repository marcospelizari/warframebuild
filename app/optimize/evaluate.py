"""One build from loaded data: arsenal stats and hit DPS (no search).

Body DPS is hip-fire with unconditional effects, as the arsenal shows. A form aimed at heads
(reference/headshot.json) also gets head DPS on a given head: aiming, the sniper's highest
zoom bonus, and headshot-triggered effects at 0 and at max stacks (PLAN G70).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain import families
from app.domain.effects import DamageType, Stat, Support, Trigger
from app.domain.elements import ELEMENTS
from app.domain.fire_rate import Firing, effective_fire_rate, shooting_share
from app.domain.headshot import Head
from app.domain.hit import AttackStats, Bonus, ModdedHit, modded_hit
from app.domain.stats import modded, modded_time, value_for
from app.gamedata.models import Attack, Effects, Headshot, Incarnon, Mod, Perk, Weapon

MAX_SLOTS = 8
BOW = "Bow"  # WFCD weapon_type
Form = Literal["normal", "incarnon"]
AOE = "AoE"  # WFCD shot_type
FLAT_HEAD = -2.0  # wiki module ExtraHeadshotDmg: heads at 1x (saved Enemy_Body_Parts, Notes)
HEAD_TRIGGERS = frozenset({Trigger.ON_HEADSHOT, Trigger.ON_WEAK_POINT_HIT})
ZOOM = "Zoom bonus"


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
    # Burst DPS on `head` with headshot-triggered effects at 0 and at max stacks.
    head_burst_dps: tuple[float, float] | None = None
    head_triggered: tuple[str, ...] = ()  # entries whose headshot-triggered effects count


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


def bonuses(
    weapon: Weapon,
    entries: Sequence[Effects],
    *,
    aiming: bool = False,
    triggers: frozenset[Trigger] = frozenset(),
) -> list[Bonus]:
    """Effects in slot order, max rank (Q33). By default unconditional and hip-fire: what the
    arsenal shows. `triggers`: conditions counted as met, their effects at max stacks (R2)."""
    out: list[Bonus] = []
    for entry in entries:
        for e in entry.effects:
            if e.while_aiming and not aiming:
                continue
            if e.trigger == Trigger.ALWAYS:
                out.append((e, value_for(e, weapon.weapon_type)))
            elif e.trigger in triggers:
                out.append((e, value_for(e, weapon.weapon_type, e.max_stacks)))
    return out


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
    head: Head | None = None,
) -> Evaluation:
    """`form` defaults to Incarnon Form for Incarnon guns (Q11). `head`: the head a form aimed
    at heads is scored on (until enemies exist, the reference head)."""
    check(weapon, mods, bonus)
    picked = chosen_perks(incarnon, perks)
    form = form or ("incarnon" if incarnon else "normal")
    active = [p for p in picked if p.form in ("both", form)]
    named = [(m.name, m.effects) for m in mods] + [(p.name, p.effects) for p in active]
    b = bonuses(weapon, [e for _, e in named])
    share = weapon.bonus_element.max_share if bonus and weapon.bonus_element else None
    bonus_element = (bonus, share) if bonus is not None and share is not None else None
    parts = _parts(weapon, incarnon, form)
    no_ms = set(incarnon.no_multishot) if incarnon and form == "incarnon" else set()
    body = _shot(weapon, parts, no_ms, b, bonus_element, form)
    burst = math.fsum(h.average_shot() for h in body.hits) * body.rate
    mark = next((h for h in weapon.headshot if h.form == form), None)
    head_dps: tuple[float, float] | None = None
    triggered: tuple[str, ...] = ()
    if mark and head:
        if weapon.zoom:
            named.append((ZOOM, weapon.zoom))
        entries = [e for _, e in named]
        zero = _shot(
            weapon, parts, no_ms, bonuses(weapon, entries, aiming=True), bonus_element, form
        )
        full = bonuses(weapon, entries, aiming=True, triggers=HEAD_TRIGGERS)
        head_dps = (
            _head_burst(zero, parts, head, mark),
            _head_burst(_shot(weapon, parts, no_ms, full, bonus_element, form), parts, head, mark),
        )
        triggered = tuple(n for n, e in named if any(x.trigger in HEAD_TRIGGERS for x in e.effects))
    return Evaluation(
        hit=body.hits[0],
        form=form,
        perks=[p.name for p in picked],
        fire_rate=body.rate,
        magazine=body.magazine,
        reload_time=body.firing.reload_time,
        direct_burst_dps=burst,
        direct_sustained_dps=None
        if body.magazine is not None and body.firing.ammo_cost > body.magazine
        else burst * shooting_share(body.firing, body.rate),
        bonus_element=bonus_element,
        ammo_cost_assumed=body.ammo_cost_assumed,
        not_modelled=[n for n, e in named if e.support != Support.FULL],
        sets_ignored=sorted({m.mod_set for m in mods if m.mod_set}),
        inactive_perks=[p.name for p in picked if p not in active],
        aoe_parts=any(a is not None and a.shot_type == AOE for _, a in parts[1:]),
        note=incarnon.note if incarnon and form == "incarnon" else None,
        headshot=mark,
        head_burst_dps=head_dps,
        head_triggered=triggered,
    )


@dataclass(frozen=True)
class _Shot:
    hits: list[ModdedHit]  # one per shot part
    rate: float  # effective shots/s
    magazine: float | None
    firing: Firing
    ammo_cost_assumed: bool


def _shot(
    weapon: Weapon,
    parts: list[tuple[AttackStats, Attack | None]],
    no_multishot: set[str],
    b: list[Bonus],
    bonus_element: tuple[DamageType, float] | None,
    form: Form,
) -> _Shot:
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
    rate = effective_fire_rate(firing, modded(1.0, Stat.FIRE_RATE, b))
    return _Shot(hits, rate, magazine, firing, ammo_cost is None)


def _head_burst(
    shot: _Shot, parts: list[tuple[AttackStats, Attack | None]], head: Head, mark: Headshot
) -> float:
    """Burst DPS when every direct part lands on `head`; AoE parts never headshot."""
    total = []
    for hit, (_, a) in zip(shot.hits, parts, strict=True):
        if a is not None and a.shot_type == AOE:
            total.append(hit.average_shot())
            continue
        extra = a.extra_headshot if a is not None else None
        flat = mark.flat or extra == FLAT_HEAD
        bonus = extra if extra is not None and extra > 0 else 0.0
        total.append(hit.average_shot(head=head, flat=flat, extra=bonus))
    return math.fsum(total) * shot.rate
