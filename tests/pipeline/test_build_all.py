import dataclasses
import filecmp
import json
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pytest

from app.gamedata.release import current
from app.gamedata.store import GameData, load
from app.optimize.builds import Search
from app.optimize.candidates import fits
from app.pipeline import build_all, refresh, release, search_pool
from app.pipeline.gun_inputs import HASHED, INPUTS, NOT_READ
from app.pipeline.publish import StoreError
from app.pipeline.refresh import Paths as RefreshPaths

ROOT = Path(__file__).resolve().parents[2]
HORNET = "/Lotus/Upgrades/Mods/Pistol/WeaponDamageAmountMod"


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
    lines: list[str] = []
    build_all.run(one, workers=2, budget=1, progress=lines.append)
    build_all.run(two, workers=3, budget=1)
    a, b = current(one.releases), current(two.releases)
    assert a is not None and b is not None
    assert a.name == b.name
    assert _same_tree(a, b)
    guns = {w.slug for w in load(ROOT / "gamedata").weapons}
    assert {p.stem for p in (a / "builds").glob("*.json")} == guns
    assert os.environ.get("PYTHONHASHSEED") == seed  # set for the workers only
    assert lines[0].startswith("build-all: ") and "2 workers" in lines[0]  # before any gun
    assert len(lines) == 1 + len(guns)


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
    monkeypatch.setattr(search_pool, "_data", None)  # restored after the test
    monkeypatch.setattr(search_pool, "_error", None)
    search_pool._load(ROOT / "gamedata", "0" * 16)
    with pytest.raises(release.ReleaseError, match="changed during the run"):
        search_pool._task("lenz", Search("max", None), 1)


def test_stop_kills_running_guns_at_once() -> None:
    """Ctrl+C must not wait for running guns (one can take minutes at the full budget)."""
    pool = ProcessPoolExecutor(1, mp_context=multiprocessing.get_context("spawn"))
    job = pool.submit(time.sleep, 60)
    deadline = time.monotonic() + 10
    while not pool._processes:
        assert time.monotonic() < deadline, "worker never started"
        time.sleep(0.05)
    started = time.monotonic()
    search_pool._stop(pool)
    with pytest.raises(BrokenProcessPool):
        job.result(timeout=10)
    assert time.monotonic() - started < 10


def test_incremental_run_searches_only_changed_guns_and_equals_a_full_run(
    paths: RefreshPaths, tmp_path: Path
) -> None:
    """G90 U3: a pistol mod change re-searches the guns it fits; the rest are copied."""
    refresh.run(paths, offline=True, fetch_images=False)
    inc = build_all.Paths(paths.gamedata, paths.reference, tmp_path / "inc", ROOT / "app")
    build_all.run(inc, workers=2, budget=1)

    upgrades = paths.raw / "de/ExportUpgrades_en.json"
    data = json.loads(upgrades.read_text())
    hornet = next(e for e in data["ExportUpgrades"] if e["uniqueName"] == HORNET)
    hornet["levelStats"][-1]["stats"] = ["+240% Damage"]
    upgrades.write_text(json.dumps(data))
    refresh.run(paths, offline=True, fetch_images=False)

    lines: list[str] = []
    summary = build_all.run(inc, workers=2, budget=1, progress=lines.append)
    searched = {line.split()[1] for line in lines[1:]}
    gamedata = load(paths.gamedata)
    mod = next(m for m in gamedata.mods.mods if m.unique_name == HORNET)
    assert searched == {w.slug for w in gamedata.weapons if fits(w, mod)}
    assert 0 < len(searched) < len(gamedata.weapons)
    assert (
        f"({len(searched)} searched, {len(gamedata.weapons) - len(searched)} copied)"
        in (summary[0])
    )

    full = build_all.Paths(paths.gamedata, paths.reference, tmp_path / "full", ROOT / "app")
    build_all.run(full, workers=2, budget=1)
    a, b = current(inc.releases), current(full.releases)
    assert a is not None and b is not None and a.name == b.name
    assert _same_tree(a / "builds", b / "builds")
    assert (a / INPUTS).read_bytes() == (b / INPUTS).read_bytes()


def test_release_without_input_keys_searches_every_gun(tmp_path: Path) -> None:
    (tmp_path / "builds").mkdir()
    (tmp_path / "builds/lex-prime.json").write_text("{}")
    assert build_all._unchanged(tmp_path, {"lex-prime": "k"}) == set()  # made before U3
    (tmp_path / INPUTS).write_text('{"lex-prime": "k"}')
    assert build_all._unchanged(tmp_path, {"lex-prime": "k"}) == {"lex-prime"}
    assert build_all._unchanged(tmp_path, {"lex-prime": "other"}) == set()


def test_every_gamedata_field_is_hashed_or_never_read() -> None:
    """Review gap: a new data file the search reads must enter the per-gun key (U3)."""
    fields = {f.name for f in dataclasses.fields(GameData)}
    assert fields == HASHED | NOT_READ
    assert not HASHED & NOT_READ


def test_slowest_guns_start_first(gamedata: GameData) -> None:
    """A bonus-element gun searches every element: started last, it ran alone at the end."""
    order = build_all.slowest_first(gamedata, ["braton-prime", "soma-prime", "kuva-hind", "lenz"])
    assert order == ["kuva-hind", "braton-prime", "soma-prime", "lenz"]
