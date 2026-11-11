import filecmp
import os
from pathlib import Path

import pytest

from app.gamedata.store import load
from app.pipeline import build_all, release
from app.pipeline.publish import StoreError

ROOT = Path(__file__).resolve().parents[2]


def _paths(tmp_path: Path, name: str) -> build_all.Paths:
    p = build_all.Paths.project(ROOT)
    return build_all.Paths(p.gamedata, p.reference, tmp_path / name, p.app)


def _same_tree(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    return not mismatch and not errors and all(_same_tree(a / d, b / d) for d in cmp.common_dirs)


def test_two_runs_give_byte_identical_releases(tmp_path: Path) -> None:
    """E3/G16, across worker counts; budget 1 keeps it quick."""
    one, two = _paths(tmp_path, "one"), _paths(tmp_path, "two")
    seed = os.environ.get("PYTHONHASHSEED")
    build_all.run(one, workers=2, budget=1)
    build_all.run(two, workers=3, budget=1)
    a, b = release.current(one.releases), release.current(two.releases)
    assert a is not None and b is not None
    assert a.name == b.name
    assert _same_tree(a, b)
    guns = {w.slug for w in load(ROOT / "gamedata").weapons}
    assert {p.stem for p in (a / "builds").glob("*.json")} == guns
    assert os.environ.get("PYTHONHASHSEED") == seed  # set for the workers only


def test_a_held_lock_fails_before_any_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _paths(tmp_path, "releases")
    paths.releases.mkdir()
    (paths.releases / ".lock").write_text("1")

    def no_work(_: Path) -> None:
        raise AssertionError("loaded data while the lock was held")

    monkeypatch.setattr(build_all, "load", no_work)
    with pytest.raises(StoreError, match="another build-all"):
        build_all.run(paths, workers=1, budget=1)


def test_a_worker_with_other_data_fails_with_the_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_all, "_data", None)  # restored after the test
    monkeypatch.setattr(build_all, "_error", None)
    build_all._load(ROOT / "gamedata", "0" * 16)
    with pytest.raises(release.ReleaseError, match="changed during the run"):
        build_all._one("lenz", 1)
