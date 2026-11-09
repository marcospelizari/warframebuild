"""POST /api/calc: evaluate one build (no search; hit damage, no DoT or Blast)."""

import math

from fastapi import APIRouter, Request

from app.api.errors import ApiFailure
from app.api.schemas import (
    ApiError,
    Arsenal,
    Assumption,
    BonusElement,
    Build,
    CalcRequest,
    Dps,
    HeadDps,
    Headshot,
    Slot,
    Source,
    WeaponRef,
)
from app.domain.headshot import Head
from app.gamedata.models import Mod, ReferenceHead, Weapon
from app.gamedata.store import GameData
from app.optimize.evaluate import MAX_SLOTS, BuildError, Evaluation, evaluate

WIKI = "https://wiki.warframe.com/w/"
ERRORS: dict[int | str, dict[str, object]] = {
    404: {"model": ApiError},
    413: {"model": ApiError},
    422: {"model": ApiError},
}

_MAIN_ATTACK = {
    "normal": "Charge and burst from the first listed attack",
    "incarnon": "Incarnon Form; magazine and reload of the normal form",
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
    try:
        result = evaluate(
            weapon,
            mods,
            body.bonus_element,
            data.incarnon_by_id.get(weapon.unique_name),
            body.perks,
            head=Head(data.reference_head.multiplier, data.reference_head.critical),
        )
    except BuildError as error:
        raise ApiFailure(422, error.code, error.message, error.field) from error
    return _build(data.meta.dataset_hash, weapon, mods, result, data.reference_head)


def _build(
    dataset_hash: str, weapon: Weapon, mods: list[Mod], e: Evaluation, head: ReferenceHead
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
        headshot=Headshot(reason=e.headshot.reason, source=_source(e.headshot.source))
        if e.headshot
        else None,
        assumptions=_assumptions(weapon, e),
    )


def _assumptions(weapon: Weapon, e: Evaluation) -> list[Assumption]:
    out = [
        Assumption(id="max_rank", text="Mods at max rank"),
        Assumption(id="unconditional", text="Only unconditional mod effects (as in the arsenal)"),
        Assumption(id="main_attack", text=_MAIN_ATTACK[e.form]),
        Assumption(id="direct_only", text="DPS from hits on the body; no DoT or Blast"),
    ]
    if e.headshot:
        text = (
            f"Aimed at heads ({e.headshot.reason}): head DPS while aiming, at the highest zoom, "
            "on the reference head; body DPS is hip-fire"
        )
        out.append(Assumption(id="headshot", text=text, source=_source(e.headshot.source)))
        if e.head_triggered:
            text = "Needs headshots, shown at 0 and max stacks: " + ", ".join(e.head_triggered)
            out.append(Assumption(id="head_stacks", text=text))
    if e.not_modelled:
        text = "Effects not modelled yet: " + ", ".join(e.not_modelled)
        out.append(Assumption(id="not_modelled", text=text))
    if e.aoe_parts:
        out.append(Assumption(id="aoe_full", text="AoE parts at full damage, no falloff"))
    if e.note:
        out.append(Assumption(id="incarnon_note", text=e.note))
    if e.inactive_perks:
        text = f"No effect in {e.form} form: " + ", ".join(e.inactive_perks)
        out.append(Assumption(id="inactive_perks", text=text))
    if e.sets_ignored:
        out.append(Assumption(id="sets_ignored", text="Mod set bonuses not applied"))
    if e.ammo_cost_assumed:
        out.append(Assumption(id="ammo_cost", text="1 ammo per shot", value=1))
    if e.bonus_element and weapon.bonus_element:
        out.append(
            Assumption(
                id="bonus_element_share",
                text="Bonus element at its maximum share of base damage",
                value=e.bonus_element[1],
                source=Source(kind="wiki", url=WIKI + weapon.bonus_element.page),
            )
        )
    return out


def _source(title: str | None) -> Source | None:
    return Source(kind="wiki", url=WIKI + title) if title else None
