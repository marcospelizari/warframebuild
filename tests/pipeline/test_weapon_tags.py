import json
from pathlib import Path

import pytest

from app.pipeline.build import build
from app.pipeline.errors import RefreshError
from app.pipeline.refresh import Paths

BRATON = "/Lotus/Weapons/Tenno/Rifle/BratonPrime"


def _row(paths: Paths, tags: list[str]) -> None:
    table = paths.reference / "weapon_tags.json"
    data = json.loads(table.read_text())
    data["weapons"] = {
        BRATON: {"name": "Braton Prime", "tags": tags, "source": "test", "verified": "2026-11-10"}
    }
    table.write_text(json.dumps(data))


def _drop_from_export_plus(raw: Path) -> None:
    path = raw / "export-plus" / "ExportWeapons.json"
    data = json.loads(path.read_text())
    del data[BRATON]
    path.write_text(json.dumps(data))


def test_row_fills_a_gun_export_plus_lacks(paths: Paths) -> None:
    _drop_from_export_plus(paths.raw)
    _row(paths, ["SEMI_AUTO", "ASSAULT_AMMO"])
    braton = next(w for w in build(paths.raw, paths.reference).weapons if w.name == "Braton Prime")
    assert braton.compatibility_tags == ["ASSAULT_AMMO", "SEMI_AUTO"]


def test_row_for_a_gun_export_plus_lists_fails(paths: Paths) -> None:
    _row(paths, ["ASSAULT_AMMO"])
    with pytest.raises(RefreshError, match="export-plus lists it now"):
        build(paths.raw, paths.reference)


def test_unknown_tag_fails(paths: Paths) -> None:
    _drop_from_export_plus(paths.raw)
    _row(paths, ["NEW_TAG"])
    with pytest.raises(RefreshError, match="unknown export-plus tags"):
        build(paths.raw, paths.reference)


def test_unknown_tag_in_export_plus_fails(paths: Paths) -> None:
    path = paths.raw / "export-plus" / "ExportWeapons.json"
    data = json.loads(path.read_text())
    data[BRATON]["compatibilityTags"] = ["NEW_TAG"]
    path.write_text(json.dumps(data))
    with pytest.raises(RefreshError, match="Braton Prime: unknown export-plus tags"):
        build(paths.raw, paths.reference)
