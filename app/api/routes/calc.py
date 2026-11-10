"""POST /api/calc: evaluate one build (no search): hit DPS and the combat score."""

import math

from fastapi import APIRouter, Request

from app.api.assumptions import WIKI, assumptions, source
from app.api.errors import ApiFailure
from app.api.schemas import (
    ApiError,
    Arsenal,
    BonusElement,
    Build,
    CalcRequest,
    Combat,
    Dps,
    EnemyFight,
    FactionScore,
    HeadDps,
    Headshot,
    Slot,
    Source,
    WeaponRef,
)
from app.domain.combat import CAP_S
from app.domain.headshot import Head
from app.gamedata.models import Mod, ReferenceHead, Weapon
from app.gamedata.store import GameData
from app.optimize import combat
from app.optimize.conditions import Resolved
from app.optimize.evaluate import Evaluation, evaluate_loadout
from app.optimize.loadout import MAX_SLOTS, BuildError, loadout

ERRORS: dict[int | str, dict[str, object]] = {
    404: {"model": ApiError},
    413: {"model": ApiError},
    422: {"model": ApiError},
}

router = APIRouter()


@router.post("/api/calc", responses=ERRORS)
def calc(body: CalcRequest, request: Request) -> Build:
    data: GameData = request.app.state.data
    weapon = data.weapon_by_slug.get(body.weapon)
    if weapon is None:
        raise ApiFailure(404, "unknown_weapon", "no such weapon", "weapon")
    mods = []
    for i, uid in enumerate(body.mods):
        mod = data.mod_by_id.get(uid)
        if mod is None:
            raise ApiFailure(422, "unknown_mod", "no such mod", f"mods[{i}]")
        mods.append(mod)
    incarnon = data.incarnon_by_id.get(weapon.unique_name)
    try:
        lo = loadout(weapon, mods, body.bonus_element, incarnon, body.perks, sets=data.set_by_id)
    except BuildError as error:
        raise ApiFailure(422, error.code, error.message, error.field) from error
    head = Head(data.reference_head.multiplier, data.reference_head.critical)
    result = evaluate_loadout(lo, head)
    scored = combat.combat(lo, data.enemies, data.factions)
    fights = _combat(scored, lo.mark is not None)
    return _build(
        data.meta.dataset_hash, weapon, mods, result, data.reference_head, fights, scored.conditions
    )


def _combat(c: combat.Combat, aimed: bool) -> Combat:
    return Combat(
        level=c.enemies[0].enemy.level if c.enemies else 0,
        cap_s=CAP_S,
        enemies=[
            EnemyFight(
                name=r.enemy.name,
                faction=r.enemy.faction,
                target=r.enemy.head.part if aimed and r.enemy.head else "Body",
                ttk=r.outcome.ttk,
                removed=r.outcome.removed,
                cost=r.outcome.cost,
            )
            for r in c.enemies
        ],
        factions=[FactionScore(faction=f, score=v) for f, v in c.factions.items()],
        score=c.score,
    )


def _build(
    dataset_hash: str,
    weapon: Weapon,
    mods: list[Mod],
    e: Evaluation,
    head: ReferenceHead,
    fights: Combat,
    conditions: Resolved,
) -> Build:
    hit = e.hit
    slots = [
        Slot(
            index=i,
            mod=m.unique_name if m else None,
            name=m.name if m else None,
            rank=m.fusion_limit if m else None,
            polarity=m.polarity if m else None,
        )
        for i, m in enumerate([*mods, *[None] * (MAX_SLOTS - len(mods))])
    ]
    return Build(
        dataset_hash=dataset_hash,
        weapon=WeaponRef(
            slug=weapon.slug,
            name=weapon.name,
            category=weapon.category,
            weapon_type=weapon.weapon_type,
        ),
        form=e.form,
        perks=e.perks,
        slots=slots,
        bonus_element=BonusElement(damage_type=e.bonus_element[0], share=e.bonus_element[1])
        if e.bonus_element
        else None,
        arsenal=Arsenal(
            damage=hit.arsenal_damage,
            total_damage=math.fsum(hit.arsenal_damage.values()),
            critical_chance=hit.critical_chance,
            critical_multiplier=hit.critical_multiplier,
            status_chance=hit.status_chance,
            multishot=hit.multishot,
            fire_rate=e.fire_rate,
            magazine=e.magazine,
            reload_time=e.reload_time,
            beam_ramp_start=weapon.beam_ramp_start,
        ),
        dps=Dps(
            direct_burst=e.direct_burst_dps,
            direct_sustained=e.direct_sustained_dps,
            head=HeadDps(
                head=head.name,
                multiplier=head.multiplier,
                critical=head.critical,
                zero_stacks=e.head_burst_dps[0],
                max_stacks=e.head_burst_dps[1],
                triggered=list(e.head_triggered),
                source=Source(kind="wiki", url=WIKI + head.source),
            )
            if e.head_burst_dps
            else None,
        ),
        headshot=Headshot(reason=e.headshot.reason, source=source(e.headshot.source))
        if e.headshot
        else None,
        combat=fights,
        assumptions=assumptions(weapon, e, fights, conditions),
    )
