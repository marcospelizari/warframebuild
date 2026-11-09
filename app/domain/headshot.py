"""Damage factor of a hit on a head (saved Enemy_Body_Parts: Weak Point Hits, Headshots, Notes).

`(part + 1.5 x weak point damage) x (1 + headshot bonuses) x extra`: weak-point damage
bonuses (Acuity) add to the part multiplier at 1.5x on a head; headshot-multiplier bonuses
(Deadhead, Target Acquired, sniper zoom) add up with each other and multiply. A "1x head"
attack (wiki module ExtraHeadshotDmg -2: Nataruk Perfect Shot, Lex Incarnon) ignores the
part multiplier and weak-point bonuses but keeps headshot bonuses. `extra` is a weapon's
own multiplicative headshot bonus (Cernos Prime x1.5). AoE parts never hit a head.
"""

from dataclasses import dataclass

HEAD_WEAK_POINT_RATE = 1.5  # weak-point bonuses on a head (Enemy_Body_Parts, Weak Point Hits)


@dataclass(frozen=True)
class Head:
    multiplier: float  # the body part's own multiplier (3 on Grineer humanoid heads)
    critical: bool  # critical-headshot flag: crit damage doubled (saved Critical_Hit)


def factor(
    head: Head,
    weak_point_damage: float,
    headshot_bonus: float,
    *,
    flat: bool = False,
    extra: float = 0.0,
) -> float:
    if flat:
        return 1 + headshot_bonus
    part = head.multiplier + HEAD_WEAK_POINT_RATE * weak_point_damage
    return part * (1 + headshot_bonus) * (1 + extra)
