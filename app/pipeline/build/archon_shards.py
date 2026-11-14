"""reference/archon_shards.json -> each colour's gun buffs (G91), citing the saved page."""

from typing import Any

from pydantic import ValidationError

from app.domain.archon_shards import ArchonShards, Shard, ShardBuff
from app.pipeline.build.inputs import require_cites, require_verified
from app.pipeline.errors import RefreshError

FILE = "archon_shards.json"


def build(table: dict[str, Any], titles: dict[str, str]) -> ArchonShards:
    """`titles`: saved wiki stem -> title (reference/wiki_pages.json)."""
    rows = table.get("shards")
    if not isinstance(rows, dict) or set(rows) != {s.value for s in Shard}:
        raise RefreshError(f"reference/{FILE}: `shards` needs one row per colour {list(Shard)}")
    buffs: dict[Shard, list[ShardBuff]] = {}
    for key, row in rows.items():
        if not isinstance(row, dict) or set(row) != {"buffs", "verified"}:
            raise RefreshError(f"reference/{FILE} {key}: keys must be buffs, verified")
        require_verified(row, FILE, key)
        try:
            buffs[Shard(key)] = [ShardBuff(**b) for b in row["buffs"]]
        except (ValidationError, TypeError) as error:
            raise RefreshError(f"reference/{FILE} {key}: {error}") from error
        for b in buffs[Shard(key)]:
            require_cites(b.source, FILE, key, titles)
    return ArchonShards(buffs=buffs)
