import shutil
from pathlib import Path

import pytest

from app.pipeline import sample
from tests.conftest import ROOT


def test_sample_searches_the_test_guns_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gamedata = tmp_path / "gamedata"
    shutil.copytree(ROOT / "tests/fixtures/gamedata", gamedata)
    monkeypatch.setattr(sample, "GUNS", ("Soma Prime", "Kuva Hind"))
    lines = sample.run(gamedata, workers=2, budget=1)
    assert sorted(line.split()[1] for line in lines[:2]) == ["kuva-hind", "soma-prime"]
    assert "Recommended" in lines[0] and "faction builds" in lines[0]
    assert lines[-1].startswith("sample: 2 guns in ")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["gamedata"]  # no release
