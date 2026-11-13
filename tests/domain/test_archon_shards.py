import pytest

from app.domain.archon_shards import ArchonShards, PerShard, Shard, ShardBuff
from app.domain.effects import DamageType, Effect, Stat

SRC = ["Archon_Shard:1"]
TABLE = ArchonShards(
    buffs={
        Shard.CRIMSON: [
            ShardBuff(
                weapons=["primary"],
                effect=Effect(stat=Stat.STATUS_CHANCE, value=0.25),
                tauforged=0.375,
                source=SRC,
            )
        ],
        Shard.AZURE: [],
        Shard.TOPAZ: [
            ShardBuff(
                weapons=["secondary"],
                effect=Effect(stat=Stat.CRITICAL_CHANCE, value=0.5),
                tauforged=0.75,
                at_cap="at its cap",
                source=SRC,
            )
        ],
        Shard.VIOLET: [
            ShardBuff(
                weapons=["primary"],
                effect=Effect(stat=Stat.ELEMENT, value=0.3, damage_type=DamageType.ELECTRICITY),
                tauforged=0.45,
                per_shard=PerShard(
                    colors=[Shard.CRIMSON, Shard.AZURE, Shard.VIOLET], value=0.1, tauforged=0.15
                ),
                source=SRC,
            )
        ],
    }
)


def test_violet_counts_itself_and_the_listed_colours() -> None:
    """Saved Archon_Shard:388: +10% per Crimson, Azure or Violet shard equipped."""
    chosen = [Shard.VIOLET, Shard.AZURE, Shard.TOPAZ]
    [electricity] = TABLE.effects(chosen, "primary", tauforged=False)
    assert electricity.value == pytest.approx(0.3 + 2 * 0.1)
    [tau] = TABLE.effects(chosen, "primary", tauforged=True)
    assert tau.value == pytest.approx(0.45 + 2 * 0.15)


def test_buffs_apply_to_their_weapon_slot_only() -> None:
    assert [e.stat for e in TABLE.effects([Shard.CRIMSON], "primary", False)] == [
        Stat.STATUS_CHANCE
    ]
    assert TABLE.effects([Shard.CRIMSON], "secondary", False) == []


def test_candidates_include_colours_counted_by_a_buff() -> None:
    assert TABLE.candidates("primary") == [Shard.CRIMSON, Shard.AZURE, Shard.VIOLET]
    assert TABLE.candidates("secondary") == [Shard.TOPAZ]


def test_conditions_of_buffs_counted_at_cap_once() -> None:
    assert TABLE.conditions([Shard.TOPAZ, Shard.TOPAZ], "secondary") == ["at its cap"]
    assert TABLE.conditions([Shard.TOPAZ], "primary") == []
