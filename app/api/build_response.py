"""One build's choices -> the `Build` response: hit DPS, Max score, combat (shared by
/calc and /builds, so a shown build and the editor agree, E8)."""

import math

from app.api.assumptions import WIKI, assumptions, source
from app.api.errors import ApiFailure
from app.api.schemas import (
    ArcaneRef,
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
from app.domain.elements import PARTS
from app.domain.headshot import Head
from app.gamedata.builds import Forma
from app.gamedata.models import Arcane, Mod, ReferenceHead, Weapon
from app.gamedata.store import GameData
from app.optimize import combat
from app.optimize.conditions import Resolved
from app.optimize.evaluate import Evaluation, evaluate_loadout
from app.optimize.forma import forma_layout, stored_forma
from app.optimize.loadout import MAX_SLOTS, BuildError, loadout
from app.optimize.scoring import max_score


def build_response(data: GameData, body: CalcRequest) -> Build:
    """Score `body`'s choices (no search); ApiFailure on an unknown or illegal choice."""
    weapon = data.weapon_by_slug.get(body.weapon)
    if weapon is None:
        raise ApiFailure(404, "unknown_weapon", "no such weapon", "weapon")
    mods = []
    for i, uid in enumerate(body.mods):
        mod = data.mod_by_id.get(uid)
        if mod is None:
            raise ApiFailure(422, "unknown_mod", "no such mod", f"mods[{i}]")
        mods.append(mod)
    exilus = data.mod_by_id.get(body.exilus) if body.exilus else None
    if body.exilus and exilus is None:
        raise ApiFailure(422, "unknown_mod", "no such mod", "exilus")
    arcane = data.arcane_by_id.get(body.arcane) if body.arcane else None
    if body.arcane and arcane is None:
        raise ApiFailure(422, "unknown_arcane", "no such arcane", "arcane")
    incarnon = data.incarnon_by_id.get(weapon.unique_name)
    try:
        lo = loadout(
            weapon,
            mods,
            body.bonus_element,
            incarnon,
            body.perks,
            arcane=arcane,
            sets=data.set_by_id,
            exilus=exilus,
        )
    except BuildError as error:
        raise ApiFailure(422, error.code, error.message, error.field) from error
    head = Head(data.reference_head.multiplier, data.reference_head.critical)
    result = evaluate_loadout(lo, head)
    scored = combat.combat(lo, data.enemies, data.factions)
    fights = _combat(scored, lo.mark is not None)
    return _build(
        data.meta.dataset_hash,
        weapon,
        mods,
        exilus,
        arcane,
        stored_forma(forma_layout(weapon, mods, exilus)),
        result,
        max_score(lo, head),
        data.reference_head,
        fights,
        scored.conditions,
    )


def weapon_ref(weapon: Weapon) -> WeaponRef:
    return WeaponRef(
        slug=weapon.slug, name=weapon.name, category=weapon.category, weapon_type=weapon.weapon_type
    )


def _slot(index: int, m: Mod | None) -> Slot:
    return Slot(
        index=index,
        mod=m.unique_name if m else None,
        name=m.name if m else None,
        rank=m.fusion_limit if m else None,
        polarity=m.polarity if m else None,
    )


def _combat(c: combat.Combat, aimed: bool) -> Combat:
    return Combat(
        level=c.enemies[0].enemy.level if c.enemies else 0,
        cap_s=CAP_S,
        enemies=[
            EnemyFight(
                name=r.enemy.name,
                unique_name=r.enemy.unique_name,
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
    exilus: Mod | None,
    arcane: Arcane | None,
    forma: Forma | None,
    e: Evaluation,
    max_dps: float,
    head: ReferenceHead,
    fights: Combat,
    conditions: Resolved,
) -> Build:
    hit = e.hit
    slots = [_slot(i, m) for i, m in enumerate([*mods, *[None] * (MAX_SLOTS - len(mods))])]
    return Build(
        dataset_hash=dataset_hash,
        weapon=weapon_ref(weapon),
        form=e.form,
        perks=e.perks,
        slots=slots,
        exilus=_slot(MAX_SLOTS, exilus) if exilus else None,
        arcane=ArcaneRef(unique_name=arcane.unique_name, name=arcane.name) if arcane else None,
        bonus_element=BonusElement(damage_type=e.bonus_element[0], share=e.bonus_element[1])
        if e.bonus_element
        else None,
        forma=forma,
        arsenal=Arsenal(
            damage=hit.arsenal_damage,
            combined={t: list(PARTS[t]) for t in hit.arsenal_damage if t in PARTS},
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
            max_score=max_dps,
        ),
        headshot=Headshot(reason=e.headshot.reason, source=source(e.headshot.source))
        if e.headshot
        else None,
        combat=fights,
        assumptions=assumptions(weapon, e, fights, conditions),
    )
