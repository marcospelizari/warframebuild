import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.domain.effects import DamageType
from app.gamedata.store import GameData
from app.pipeline.build import build, status_rules
from app.pipeline.errors import RefreshError
from app.pipeline.gun_inputs import gun_keys
from app.pipeline.refresh import Paths
from app.pipeline.sources import wiki_local

ROOT = Path(__file__).resolve().parents[2]


def _table() -> dict[str, Any]:
    return json.loads((ROOT / "reference" / status_rules.FILE).read_text())  # type: ignore[no-any-return]


def _titles() -> dict[str, str]:
    return {p.stem: p.title for p in wiki_local.pages(ROOT / "reference")}


def test_refresh_builds_the_committed_rules(paths: Paths, gamedata: GameData) -> None:
    assert build(paths.raw, paths.reference).status_rules == gamedata.status_rules


def test_row_needs_a_verified_date_and_a_saved_page_source() -> None:
    table = _table()
    del table["types"]["puncture"]["verified"]
    with pytest.raises(RefreshError, match="puncture: `verified`"):
        status_rules.build(table, _titles())
    table = _table()
    table["types"]["cold"]["source"] = ["Cold_Damage"]
    with pytest.raises(RefreshError, match="cold: source 'Cold_Damage'"):
        status_rules.build(table, _titles())
    table["types"]["cold"]["source"] = ["Unsaved_Page:3"]
    with pytest.raises(RefreshError, match="Unsaved_Page:3"):
        status_rules.build(table, _titles())


def test_unknown_type_or_missing_mechanic_fails() -> None:
    table = _table()
    table["types"]["true"] = table["types"].pop("tau")
    with pytest.raises(RefreshError, match="unknown damage type 'true'"):
        status_rules.build(table, _titles())
    table = _table()
    del table["types"]["blast"]["blast"]
    with pytest.raises(RefreshError, match="blast only"):
        status_rules.build(table, _titles())


def test_a_status_number_rebuilds_every_gun(gamedata: GameData) -> None:
    rules = gamedata.status_rules
    puncture = rules.types[DamageType.PUNCTURE]
    stacking = rules.stacking(DamageType.PUNCTURE).model_copy(update={"cap": 6})
    types = rules.types | {DamageType.PUNCTURE: puncture.model_copy(update={"stacking": stacking})}
    changed = replace(gamedata, status_rules=rules.model_copy(update={"types": types}))
    before, after = gun_keys(gamedata, "v", 1), gun_keys(changed, "v", 1)
    assert before.keys() == after.keys()
    assert all(before[g] != after[g] for g in before)
