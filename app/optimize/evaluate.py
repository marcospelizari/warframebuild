"""One build from loaded data: arsenal stats and hit DPS (no search).

Body DPS is hip-fire with unconditional effects, as the arsenal shows. A form aimed at heads
(reference/headshot.json) also gets head DPS on a given head: aiming, the sniper's highest
zoom bonus, and headshot-triggered effects at 0 and at max stacks (PLAN G70).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain import families
from app.domain.effects import DamageType, Support, Trigger
from app.domain.elements import ELEMENTS
from app.domain.fire_rate import shooting_share
from app.domain.headshot import Head
from app.domain.hit import AttackStats, Bonus, ModdedHit
from app.domain.stats import value_for
from app.gamedata.models import Attack, Effects, Headshot, Incarnon, Mod, Perk, Weapon
from app.optimize.head import AOE, HEAD_TRIGGERS, head_burst
from app.optimize.shot import Form, Shot, shot

MAX_SLOTS = 8
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


@dataclass(frozen=True)
class Loadout:
    """A checked build, ready to shoot: shared by `evaluate` and the combat timeline."""

    weapon: Weapon
    form: Form
    picked: list[Perk]
    active: list[Perk]
    named: list[tuple[str, Effects]]  # mods + active perks, slot order
    parts: list[tuple[AttackStats, Attack | None]]
    no_multishot: set[str]
    bonus_element: tuple[DamageType, float] | None
    mark: Headshot | None  # this form is aimed at heads
    sets_ignored: list[str]  # mod set bonuses not applied yet
    note: str | None  # main_attack.json limit for this form

    def body_bonuses(self) -> list[Bonus]:
        return bonuses(self.weapon, [e for _, e in self.named])

    def aimed(self) -> list[tuple[str, Effects]]:
        """Entries counted on a form aimed at heads: + the sniper's highest zoom."""
        zoom = self.weapon.zoom
        return self.named + ([(ZOOM, zoom)] if zoom else [])

    def head_bonuses(self, triggered: bool) -> list[Bonus]:
        entries = [e for _, e in self.aimed()]
        triggers = HEAD_TRIGGERS if triggered else frozenset()
        return bonuses(self.weapon, entries, aiming=True, triggers=triggers)

    def shot(self, b: list[Bonus]) -> Shot:
        return shot(self.weapon, self.parts, self.no_multishot, b, self.bonus_element, self.form)


def loadout(
    weapon: Weapon,
    mods: Sequence[Mod],
    bonus: DamageType | None = None,
    incarnon: Incarnon | None = None,
    perks: Sequence[str] = (),
    form: Form | None = None,
) -> Loadout:
    """`form` defaults to Incarnon Form for Incarnon guns (Q11)."""
    check(weapon, mods, bonus)
    picked = chosen_perks(incarnon, perks)
    form = form or ("incarnon" if incarnon else "normal")
    active = [p for p in picked if p.form in ("both", form)]
    share = weapon.bonus_element.max_share if bonus and weapon.bonus_element else None
    return Loadout(
        weapon=weapon,
        form=form,
        picked=picked,
        active=active,
        named=[(m.name, m.effects) for m in mods] + [(p.name, p.effects) for p in active],
        parts=_parts(weapon, incarnon, form),
        no_multishot=set(incarnon.no_multishot) if incarnon and form == "incarnon" else set(),
        bonus_element=(bonus, share) if bonus is not None and share is not None else None,
        mark=next((h for h in weapon.headshot if h.form == form), None),
        sets_ignored=sorted({m.mod_set for m in mods if m.mod_set}),
        note=incarnon.note if incarnon and form == "incarnon" else None,
    )


def evaluate(
    weapon: Weapon,
    mods: Sequence[Mod],
    bonus: DamageType | None = None,
    incarnon: Incarnon | None = None,
    perks: Sequence[str] = (),
    form: Form | None = None,
    head: Head | None = None,
) -> Evaluation:
    """`head`: the head a form aimed at heads is scored on (the reference head in /calc)."""
    return evaluate_loadout(loadout(weapon, mods, bonus, incarnon, perks, form), head)


def evaluate_loadout(lo: Loadout, head: Head | None = None) -> Evaluation:
    weapon = lo.weapon
    body = lo.shot(lo.body_bonuses())
    burst = math.fsum(h.average_shot() for h in body.hits) * body.rate
    head_dps: tuple[float, float] | None = None
    triggered: tuple[str, ...] = ()
    named = list(lo.named)
    if lo.mark and head:
        head_dps = (
            head_burst(lo.shot(lo.head_bonuses(False)), lo.parts, head, lo.mark),
            head_burst(lo.shot(lo.head_bonuses(True)), lo.parts, head, lo.mark),
        )
        triggered = tuple(
            n for n, e in lo.aimed() if any(x.trigger in HEAD_TRIGGERS for x in e.effects)
        )
    if lo.mark and weapon.zoom and weapon.zoom.support != Support.FULL:
        named.append((ZOOM, weapon.zoom))  # the zoom belongs to every form aimed at heads
    parts, mark, picked = lo.parts, lo.mark, lo.picked
    return Evaluation(
        hit=body.hits[0],
        form=lo.form,
        perks=[p.name for p in picked],
        fire_rate=body.rate,
        magazine=body.magazine,
        reload_time=body.firing.reload_time,
        direct_burst_dps=burst,
        direct_sustained_dps=None
        if body.magazine is not None and body.firing.ammo_cost > body.magazine
        else burst * shooting_share(body.firing, body.rate),
        bonus_element=lo.bonus_element,
        ammo_cost_assumed=body.ammo_cost_assumed,
        not_modelled=[n for n, e in named if e.support != Support.FULL],
        sets_ignored=lo.sets_ignored,
        inactive_perks=[p.name for p in picked if p not in lo.active],
        aoe_parts=any(a is not None and a.shot_type == AOE for _, a in parts[1:]),
        note=lo.note,
        headshot=mark,
        head_burst_dps=head_dps,
        head_triggered=triggered,
    )
