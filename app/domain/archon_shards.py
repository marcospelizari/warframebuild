"""Archon Shards (G91): each colour's gun buffs, as effects for a chosen set of shards."""

from collections.abc import Collection, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.effects import DamageType, Effect

SLOTS = 5  # shards per Warframe
WeaponSlot = Literal["primary", "secondary"]


class Shard(StrEnum):
    CRIMSON = "crimson"
    AMBER = "amber"
    AZURE = "azure"
    EMERALD = "emerald"
    TOPAZ = "topaz"
    VIOLET = "violet"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class PerShard(_Model):
    """Extra value per equipped shard of `colors`, the buff's own shard included."""

    colors: list[Shard]
    value: float
    tauforged: float


class ShardBuff(_Model):
    weapons: list[WeaponSlot]
    effect: Effect  # at the normal value
    tauforged: float  # `effect`'s value on a Tauforged shard
    per_shard: PerShard | None = None  # Violet's Electricity
    # A buff that builds up in a fight, counted at its cap: what it needs (Topaz).
    at_cap: str | None = None
    # Counted only when the gun itself applies this status (Topaz: kills on Heat).
    needs_status: DamageType | None = None
    source: list[str]  # saved page and line


class ArchonShards(_Model):
    buffs: dict[Shard, list[ShardBuff]]

    def effects(
        self,
        chosen: Sequence[Shard],
        slot: WeaponSlot,
        tauforged: bool,
        applied: Collection[DamageType] = (),
    ) -> list[Effect]:
        """The effects `chosen` give a gun in `slot` that applies the `applied` statuses."""
        out = []
        for shard in chosen:
            for b in self._counted(shard, slot, applied):
                value = b.tauforged if tauforged else b.effect.value
                if b.per_shard is not None:
                    per = b.per_shard.tauforged if tauforged else b.per_shard.value
                    value += per * sum(c in b.per_shard.colors for c in chosen)
                out.append(b.effect.model_copy(update={"value": value}))
        return out

    def candidates(self, slot: WeaponSlot, applied: Collection[DamageType] = ()) -> list[Shard]:
        """Colours that can change the gun: own buffs, or counted by one (Azure)."""
        found: set[Shard] = set()
        for shard in self.buffs:
            for b in self._counted(shard, slot, applied):
                found.add(shard)
                found.update(b.per_shard.colors if b.per_shard else [])
        return [s for s in Shard if s in found]

    def conditions(
        self, chosen: Sequence[Shard], slot: WeaponSlot, applied: Collection[DamageType] = ()
    ) -> list[str]:
        """What the counted-at-cap buffs of `chosen` need, once each."""
        seen = dict.fromkeys(
            b.at_cap for s in chosen for b in self._counted(s, slot, applied) if b.at_cap
        )
        return list(seen)

    def _counted(
        self, shard: Shard, slot: WeaponSlot, applied: Collection[DamageType]
    ) -> list[ShardBuff]:
        return [
            b
            for b in self.buffs.get(shard, [])
            if slot in b.weapons and (b.needs_status is None or b.needs_status in applied)
        ]
