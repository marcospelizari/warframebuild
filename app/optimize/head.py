"""Head DPS of a form aimed at heads (PLAN G69/G70): every direct part lands on the head;
AoE parts never headshot (saved Enemy_Body_Parts, Notes)."""

import math
from dataclasses import dataclass

from app.domain.effects import Trigger
from app.domain.headshot import Head
from app.domain.hit import AttackStats
from app.gamedata.models import Attack, Headshot
from app.optimize.shot import Shot

AOE = "AoE"  # WFCD shot_type
FLAT_HEAD = -2.0  # wiki module ExtraHeadshotDmg: heads at 1x (saved Enemy_Body_Parts, Notes)
# Hit triggers counted at max stacks; kill triggers wait for the step-8 kill model (G70).
HEAD_TRIGGERS = frozenset({Trigger.ON_HEADSHOT, Trigger.ON_WEAK_POINT_HIT})


@dataclass(frozen=True)
class HeadArgs:
    flat: bool
    extra_bonus: float
    extra_factor: float


def head_args(attack: Attack | None, mark: Headshot) -> HeadArgs | None:
    """How one part lands on a head; None for AoE parts, which never headshot."""
    if attack is not None and attack.shot_type == AOE:
        return None
    extra = attack.extra_headshot if attack is not None else None
    own = extra if extra is not None and extra > 0 else 0.0
    return HeadArgs(
        flat=mark.flat or extra == FLAT_HEAD,
        extra_bonus=0.0 if mark.separate_extra else own,
        extra_factor=own if mark.separate_extra else 0.0,
    )


def head_burst(
    shot: Shot, parts: list[tuple[AttackStats, Attack | None]], head: Head, mark: Headshot
) -> float:
    """Burst DPS on `head`. A positive ExtraHeadshotDmg adds to the headshot bonuses (Kuva
    Chakkhurr, Synapse: Enemy_Body_Parts, Headshot Multiplier Bonuses) unless the table marks
    it as a separate factor (Cernos Prime)."""
    total = []
    for hit, (_, a) in zip(shot.hits, parts, strict=True):
        args = head_args(a, mark)
        if args is None:
            total.append(hit.average_shot())
            continue
        total.append(
            hit.average_shot(
                head=head,
                flat=args.flat,
                extra_bonus=args.extra_bonus,
                extra_factor=args.extra_factor,
            )
        )
    return math.fsum(total) * shot.rate
