"""Combat score of one build against the representative enemies (PLAN R1, step 8b).

One timeline per (head, Bane faction) is shared by the enemies that have them;
`domain.combat.fight` then plays it against each enemy. A form aimed at heads hits each
enemy's own head spot (the body if it has none) with its head bonuses at max hit stacks, as
/calc ranks head DPS (G70); headshot-triggered bonuses only where there is a headshot spot.
"""

from dataclasses import dataclass

from app.domain.combat import TYPES, Event, Outcome, Target, fight, geometric_mean
from app.domain.effects import Faction
from app.domain.headshot import Head
from app.domain.status_rules import StatusRules
from app.gamedata.models import Enemy, FactionModifiers
from app.optimize.conditions import Resolved, resolve
from app.optimize.loadout import Loadout
from app.optimize.timeline import Timeline


@dataclass(frozen=True)
class EnemyResult:
    enemy: Enemy
    outcome: Outcome


@dataclass(frozen=True)
class Combat:
    enemies: list[EnemyResult]
    factions: dict[str, float]  # geometric mean cost per faction
    score: float  # geometric mean over the factions
    conditions: Resolved  # how conditional effects counted (on heads for aimed forms)


def timeline(lo: Loadout, enemy: Enemy, rules: StatusRules) -> list[Event]:
    """Damage events of `lo` against `enemy` (before its faction modifiers and defences)."""
    head, bane = _key(lo, enemy)
    return Timeline(lo, resolve(lo, head is not None), head, bane, rules).events()


def _key(lo: Loadout, enemy: Enemy) -> tuple[Head | None, Faction | None]:
    head = enemy.head if lo.mark is not None else None
    return (Head(head.multiplier, head.critical) if head else None, enemy.bane)


def combat(
    lo: Loadout, enemies: list[Enemy], factions: list[FactionModifiers], rules: StatusRules
) -> Combat:
    modifiers = {f.faction: f.modifiers for f in factions}
    resolved: dict[bool, Resolved] = {}
    timelines: dict[tuple[Head | None, Faction | None], list[Event]] = {}
    results = []
    for e in enemies:
        key = _key(lo, e)
        if key not in timelines:
            on_head = key[0] is not None
            if on_head not in resolved:
                resolved[on_head] = resolve(lo, on_head)
            timelines[key] = Timeline(lo, resolved[on_head], *key, rules).events()
        mods = modifiers[e.faction]
        target = Target(
            health=e.health,
            shield=e.shield,
            armor=e.armor,
            modifiers=tuple(mods.get(t, 1.0) for t in TYPES),
            toxin_bypasses_shield=e.toxin_bypasses_shield,
        )
        results.append(EnemyResult(e, fight(timelines[key], target)))
    by_faction: dict[str, list[float]] = {}
    for r in results:
        by_faction.setdefault(r.enemy.faction, []).append(r.outcome.cost)
    scores = {f: geometric_mean(c) for f, c in sorted(by_faction.items())}
    aimed = lo.mark is not None
    return Combat(
        results,
        scores,
        geometric_mean(list(scores.values())) if scores else 0.0,
        resolved.get(aimed) or resolve(lo, aimed),
    )
