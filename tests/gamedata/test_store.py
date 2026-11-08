"""Read side of gamedata/ (app/gamedata/store.py): only a matching, current dataset loads."""

import json

import pytest

from app.gamedata import store
from app.pipeline.refresh import Paths, run


def test_loads_what_refresh_published(paths: Paths) -> None:
    report = run(paths, offline=True, fetch_images=False)
    assert store.load(paths.gamedata).meta == report.meta


def test_tampered_gamedata_is_rejected(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    (paths.gamedata / "weapons.json").write_text("[]\n")
    with pytest.raises(ValueError, match="dataset_hash"):
        store.load(paths.gamedata)


def test_old_schema_is_named(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    meta = paths.gamedata / "meta.json"
    data = json.loads(meta.read_text())
    data["schema_version"] = 1
    meta.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="schema version 1, this code reads"):
        store.load(paths.gamedata)
