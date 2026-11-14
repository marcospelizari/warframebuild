"""One WFCD attack as an `Attack`, with the wiki module's numbers for it."""

from typing import Any

from pydantic import ValidationError

from app.domain.direct_bonus import DirectBonus
from app.domain.effects import DamageType
from app.gamedata.models import Attack, Falloff
from app.pipeline.errors import RefreshError
from app.pipeline.sources.wiki_weapon_data import AttackData


def attack(
    a: dict[str, Any],
    weapon: str,
    extra: AttackData | None,
    direct: DirectBonus = DirectBonus.ADDING,
    beam_start: float | None = None,
) -> Attack:
    known = {t.value for t in DamageType}
    unknown = set(a.get("damage", {})) - known
    if unknown:
        raise RefreshError(f"{weapon} / {a.get('name')}: unknown damage types {sorted(unknown)}")
    falloff = a.get("falloff")
    try:
        return _model(a, falloff, extra, direct, beam_start)
    except ValidationError as error:
        raise RefreshError(f"{weapon} / {a.get('name')}: invalid values: {error}") from error


def _model(
    a: dict[str, Any],
    falloff: dict[str, Any] | None,
    extra: AttackData | None,
    direct: DirectBonus,
    beam_start: float | None,
) -> Attack:
    return Attack(
        name=a["name"],
        # WFCD uses speed 0 on DoT pseudo-attacks (e.g. Tysis "Corrosive DoT"): no own rate.
        fire_rate=a.get("speed") or None,
        critical_chance=a["crit_chance"] / 100,
        critical_multiplier=a["crit_mult"],
        status_chance=a["status_chance"] / 100,
        shot_type=a.get("shot_type"),
        damage={DamageType(k): float(v) for k, v in a.get("damage", {}).items() if v},
        falloff=Falloff(**falloff) if falloff else None,
        charge_time=a.get("charge_time"),
        shot_speed=a.get("shot_speed"),
        forced_procs=extra.forced_procs if extra else None,
        burst_count=extra.burst_count if extra else None,
        burst_delay=extra.burst_delay if extra else None,
        ammo_cost=extra.ammo_cost if extra else None,
        multishot=extra.multishot if extra else None,
        extra_headshot=extra.extra_headshot if extra else None,
        parent=extra.parent if extra else None,
        beam_ramp_start=beam_start,
        direct_bonus=direct,
    )
