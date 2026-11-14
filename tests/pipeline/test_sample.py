import json
import shutil
from pathlib import Path

import pytest

from app.gamedata.release import current
from app.pipeline import build_all, sample
from tests.conftest import ROOT


def test_sample_publishes_its_own_release_of_its_guns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gamedata = tmp_path / "gamedata"
    shutil.copytree(ROOT / "tests/fixtures/gamedata", gamedata)
    before = sorted(p.name for p in gamedata.iterdir())
    monkeypatch.setattr(sample, "GUNS", ("Soma Prime", "Kuva Hind"))
    paths = build_all.Paths(
        tmp_path / "sample/gamedata", ROOT / "reference", tmp_path / "sample/releases", ROOT / "app"
    )
    lines = sample.run(gamedata, paths, workers=2, budget=1)
    assert lines[-1].endswith("now current")
    folder = current(paths.releases)
    assert folder is not None
    assert sorted(p.name for p in (folder / "builds").iterdir()) == [
        "kuva-hind.json",
        "soma-prime.json",
    ]
    rows = json.loads((folder / "gamedata/weapons.json").read_text())
    assert sorted(r["name"] for r in rows) == ["Kuva Hind", "Soma Prime"]  # served gun list
    assert sorted(p.name for p in gamedata.iterdir()) == before  # real data untouched
