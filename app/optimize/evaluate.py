"""One build from loaded data: arsenal stats and hit DPS (no search).

Body DPS is hip-fire with unconditional effects, as the arsenal shows. A form aimed at heads
(reference/headshot.json) also gets head DPS on a given head: aiming, the sniper's highest
zoom bonus, and headshot-triggered effects at 0 and at max stacks (PLAN G70).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.effects import DamageType, Support
from app.domain.fire_rate import shooting_share
from app.domain.headshot import Head
from app.domain.hit import ModdedHit
from app.gamedata.models import Headshot, Incarnon, Mod, Weapon
from app.optimize.head import AOE, HEAD_TRIGGERS, head_burst
from app.optimize.loadout import ZOOM, Loadout, loadout
from app.optimize.shot import Form


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
    sets: list[str]  # mod set bonuses applied (gun pieces only)
    inactive_perks: list[str]  # chosen perks that do nothing in this form
    aoe_parts: bool  # AoE parts counted at full damage on the target
    note: str | None  # main_attack.json limit for this gun
    headshot: Headshot | None  # this form is aimed at heads (R5); None = body
    # Burst DPS on `head` with headshot-triggered effects at 0 and at max stacks.
    head_burst_dps: tuple[float, float] | None = None
    head_triggered: tuple[str, ...] = ()  # entries whose headshot-triggered effects count


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
        sets=lo.sets,
        inactive_perks=[p.name for p in picked if p not in lo.active],
        aoe_parts=any(a is not None and a.shot_type == AOE for _, a in parts[1:]),
        note=lo.note,
        headshot=mark,
        head_burst_dps=head_dps,
        head_triggered=triggered,
    )
