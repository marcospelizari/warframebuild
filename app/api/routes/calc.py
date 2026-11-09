"""POST /api/calc: evaluate one build (step 4.6: no search, direct damage only)."""

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
    Slot,
    Source,
    WeaponRef,
)
from app.gamedata.models import Mod, Weapon
from app.gamedata.store import GameData
from app.optimize.evaluate import MAX_SLOTS, BuildError, Evaluation, evaluate

WIKI = "https://wiki.warframe.com/w/"
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
    try:
        result = evaluate(weapon, mods, body.bonus_element)
    except BuildError as error:
        raise ApiFailure(422, error.code, error.message, error.field) from error
    return _build(data.meta.dataset_hash, weapon, mods, result)


def _build(dataset_hash: str, weapon: Weapon, mods: list[Mod], e: Evaluation) -> Build:
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
        slots=slots,
        bonus_element=BonusElement(damage_type=e.bonus_element[0], share=e.bonus_element[1])
        if e.bonus_element
        else None,
        arsenal=Arsenal(
            damage=hit.damage,
            total_damage=hit.projectile_damage,
            critical_chance=hit.critical_chance,
            critical_multiplier=hit.critical_multiplier,
            status_chance=hit.status_chance,
            multishot=hit.multishot,
            fire_rate=e.fire_rate,
            magazine=e.magazine,
            reload_time=e.reload_time,
            beam_ramp_start=weapon.beam_ramp_start,
        ),
        dps=Dps(direct_burst=e.direct_burst_dps, direct_sustained=e.direct_sustained_dps),
        assumptions=_assumptions(weapon, e),
    )


def _assumptions(weapon: Weapon, e: Evaluation) -> list[Assumption]:
    out = [
        Assumption(id="max_rank", text="Mods at max rank"),
        Assumption(id="unconditional", text="Only unconditional mod effects (as in the arsenal)"),
        Assumption(id="main_attack", text="Charge and burst from the first listed attack"),
        Assumption(id="direct_only", text="DPS from direct hits on the body; no DoT or Blast"),
    ]
    if e.not_modelled:
        text = "Effects not modelled yet: " + ", ".join(e.not_modelled)
        out.append(Assumption(id="not_modelled", text=text))
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
