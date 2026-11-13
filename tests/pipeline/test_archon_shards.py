import copy
import json
from typing import Any

import pytest

from app.domain.archon_shards import Shard
from app.pipeline.build import archon_shards
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths

TITLES = {"Archon_Shard": "Archon_Shard"}


def _table(paths: Paths) -> dict[str, Any]:
    return json.loads((paths.reference / archon_shards.FILE).read_text())  # type: ignore[no-any-return]


def test_the_table_builds_from_the_saved_page(paths: Paths) -> None:
    table = archon_shards.build(_table(paths), TITLES)
    assert set(table.buffs) == set(Shard)
    assert table.candidates("secondary") == [Shard.CRIMSON, Shard.EMERALD, Shard.TOPAZ]


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda t: t["shards"].pop("amber"), "one row per colour"),
        (lambda t: t["shards"]["crimson"].pop("verified"), "keys must be"),
        (lambda t: t["shards"]["crimson"]["buffs"][0].update(source=["Nope:1"]), "saved page"),
        (lambda t: t["shards"]["crimson"]["buffs"][0].update(weapons=["melee"]), "crimson"),
    ],
)
def test_bad_rows_stop_the_refresh(paths: Paths, change: Any, error: str) -> None:
    table = copy.deepcopy(_table(paths))
    change(table)
    with pytest.raises(RefreshError, match=error):
        archon_shards.build(table, TITLES)
