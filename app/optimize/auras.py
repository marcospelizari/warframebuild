"""Aura beside a build (G91): every aura that fits the gun, scored on the fixed build."""

from collections.abc import Callable, Sequence
from dataclasses import replace

from app.domain.auras import Aura, Auras
from app.domain.effects import Support
from app.gamedata.builds import AuraGain
from app.gamedata.enemies import Enemy
from app.gamedata.models import Effects
from app.optimize.loadout import Loadout
from app.optimize.scoring import Objective
from app.optimize.search import rounded

# The build's objective over given enemies (Max ignores them: a neutral target).
Against = Callable[[Sequence[Enemy]], Objective]


def advice(lo: Loadout, auras: Auras, enemies: Sequence[Enemy], against: Against) -> list[AuraGain]:
    gains = [
        AuraGain(aura=a.unique_name, score=rounded(_score(lo, a, enemies, against)))
        for a in auras.for_weapon(lo.weapon.weapon_type)
    ]
    return sorted(gains, key=lambda g: -g.score)


def _score(lo: Loadout, aura: Aura, enemies: Sequence[Enemy], against: Against) -> float:
    if aura.effect is not None:
        entry = Effects(support=Support.FULL, effects=[aura.effect], unparsed=[])
        return against(enemies)(replace(lo, named=[*lo.named, (aura.name, entry)]))
    weakened = [
        e.model_copy(
            update={"armor": e.armor * aura.armor_kept, "shield": e.shield * aura.shield_kept}
        )
        for e in enemies
    ]
    return against(weakened)(lo)
