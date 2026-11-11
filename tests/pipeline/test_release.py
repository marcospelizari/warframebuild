from collections.abc import Iterator
from pathlib import Path

import pytest

from app.gamedata.builds import WeaponBuilds
from app.gamedata.store import load
from app.pipeline import release

ROOT = Path(__file__).resolve().parents[2]
DATASET = load(ROOT / "gamedata").meta.dataset_hash


def _builds(*slugs: str) -> list[WeaponBuilds]:
    return [WeaponBuilds(weapon=f"/{s}", slug=s, variants=[], elements=[]) for s in slugs]


def _key(budget: int) -> release.Key:
    return release.Key(DATASET, "ref", "calc", budget)


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "enemies.json").write_text("[]")
    return ROOT / "gamedata", reference


def test_publish_writes_the_release_and_points_current_at_it(tmp_path: Path) -> None:
    gamedata, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    folder = release.publish(releases, _key(1), gamedata, reference, _builds("a", "b"), {"a", "b"})
    assert release.current(releases) == folder == releases / _key(1).id
    assert sorted(p.name for p in (folder / "builds").iterdir()) == ["a.json", "b.json"]
    assert (folder / "gamedata/meta.json").exists()
    assert (folder / "reference/enemies.json").exists()
    assert '"weapons": 2' in (folder / "manifest.json").read_text()


def test_missing_builds_leave_current_unchanged(tmp_path: Path) -> None:
    gamedata, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    first = release.publish(releases, _key(1), gamedata, reference, _builds("a"), {"a"})
    with pytest.raises(release.ReleaseError, match="missing"):
        release.publish(releases, _key(2), gamedata, reference, _builds("a"), {"a", "b"})
    assert release.current(releases) == first
    assert not (releases / _key(2).id).exists()


def test_interrupted_run_leaves_current_unchanged(tmp_path: Path) -> None:
    gamedata, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    first = release.publish(releases, _key(1), gamedata, reference, _builds("a"), {"a"})

    def crashing() -> Iterator[WeaponBuilds]:
        yield from _builds("a")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        release.publish(releases, _key(2), gamedata, reference, crashing(), {"a", "b"})
    assert release.current(releases) == first


def test_only_the_last_two_releases_stay(tmp_path: Path) -> None:
    gamedata, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    for budget in (1, 2, 3):
        release.publish(releases, _key(budget), gamedata, reference, _builds("a"), {"a"})
    kept = {p.name for p in releases.iterdir() if p.is_dir() and not p.name.startswith(".")}
    assert kept == {_key(2).id, _key(3).id}


def test_key_changes_with_every_part() -> None:
    base = release.Key("d", "r", "c", 1)
    others = [
        release.Key("x", "r", "c", 1),
        release.Key("d", "x", "c", 1),
        release.Key("d", "r", "x", 1),
        release.Key("d", "r", "c", 2),
    ]
    assert len({base.id, *(k.id for k in others)}) == 5


def test_calculator_version_follows_domain_and_optimize_sources(tmp_path: Path) -> None:
    for layer in ("domain", "gamedata", "optimize", "api"):
        (tmp_path / layer).mkdir()
        (tmp_path / layer / "x.py").write_text("a = 1\n")
    before = release.calculator_version(tmp_path)
    (tmp_path / "api/x.py").write_text("a = 2\n")
    assert release.calculator_version(tmp_path) == before
    (tmp_path / "optimize/x.py").write_text("a = 2\n")
    assert release.calculator_version(tmp_path) != before
    after_optimize = release.calculator_version(tmp_path)
    (tmp_path / "gamedata/x.py").write_text("a = 2\n")
    assert release.calculator_version(tmp_path) != after_optimize


def test_same_key_again_replaces_the_release_in_place(tmp_path: Path) -> None:
    gamedata, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    release.publish(releases, _key(1), gamedata, reference, _builds("a"), {"a"})
    folder = release.publish(releases, _key(1), gamedata, reference, _builds("a"), {"a"})
    assert release.current(releases) == folder
    assert (folder / "builds/a.json").exists()
    assert {p.name for p in releases.iterdir()} == {"current", _key(1).id}


def test_leftovers_of_a_crash_are_cleaned_and_the_live_copy_restored(tmp_path: Path) -> None:
    gamedata, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    release.publish(releases, _key(1), gamedata, reference, _builds("a"), {"a"})
    (releases / _key(1).id).rename(releases / f".{_key(1).id}.tmp.old")  # crash mid-swap
    (releases / ".other.tmp").mkdir()
    release.publish(releases, _key(2), gamedata, reference, _builds("a"), {"a"})
    names = {p.name for p in releases.iterdir()}
    assert names == {"current", _key(1).id, _key(2).id}


def test_a_release_whose_gamedata_differs_from_its_key_is_refused(tmp_path: Path) -> None:
    _, reference = _sources(tmp_path)
    releases = tmp_path / "releases"
    stale = release.Key("0" * 16, "ref", "calc", 1)
    with pytest.raises(release.ReleaseError, match="changed during the run"):
        release.publish(releases, stale, ROOT / "gamedata", reference, _builds("a"), {"a"})
    assert release.current(releases) is None
