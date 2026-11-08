import json
import os
from pathlib import Path

import pytest

from app.gamedata import store
from app.pipeline import fixtures
from app.pipeline.publish import StoreError
from app.pipeline.refresh import Paths, run
from app.pipeline.sources import Fetched, read_sources, saved_until_failure, wiki_local


def test_offline_refresh_writes_loadable_gamedata(paths: Paths) -> None:
    report = run(paths, offline=True, fetch_images=False)
    data = store.load(paths.gamedata)
    assert data.meta.dataset_hash == report.meta.dataset_hash
    assert data.meta.game_update
    assert len(data.weapons) == data.meta.counts["weapons"]
    assert "wiki/Status_Effect.wikitext" in read_sources(paths.raw)


def test_refresh_is_deterministic(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    first = {p.name: p.read_bytes() for p in paths.gamedata.iterdir()}
    report = run(paths, offline=True, fetch_images=False)
    assert {p.name: p.read_bytes() for p in paths.gamedata.iterdir()} == first
    assert "  no data change" in report.lines()


def test_failed_refresh_keeps_last_good_dataset(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    before = (paths.gamedata / "meta.json").read_bytes()
    (paths.raw / "de/ExportWeapons_en.json").write_text('{"oops": []}')
    with pytest.raises(Exception, match="ExportWeapons"):
        run(paths, offline=True, fetch_images=False)
    assert (paths.gamedata / "meta.json").read_bytes() == before


def test_missing_wiki_page_fails_before_anything_runs(paths: Paths) -> None:
    (paths.raw / "wiki/Armor.wikitext").unlink()
    with pytest.raises(wiki_local.MissingWikiPages, match="Armor"):
        run(paths, offline=True, fetch_images=False)
    assert not paths.gamedata.exists()


def test_bad_reference_date_fails_before_publishing(paths: Paths) -> None:
    """Review 3 R9: a changed dataset is never published by a refresh that then fails."""
    run(paths, offline=True, fetch_images=False)
    before = (paths.gamedata / "meta.json").read_bytes()
    weapons = paths.raw / "de/ExportWeapons_en.json"
    data = json.loads(weapons.read_text())
    data["ExportWeapons"][0]["criticalChance"] += 0.01
    weapons.write_text(json.dumps(data))
    rules = paths.reference / "mod_filter.json"
    rules.write_text(rules.read_text().replace('"2026-11-08"', '"soon"', 1))
    with pytest.raises(ValueError, match="verified must be YYYY-MM-DD"):
        run(paths, offline=True, fetch_images=False)
    assert (paths.gamedata / "meta.json").read_bytes() == before


def test_second_refresh_is_refused_while_one_runs(paths: Paths) -> None:
    """Review 3 R8: two refreshes never share cache/raw/."""
    (paths.raw / ".refresh.lock").write_text("123")
    with pytest.raises(StoreError, match="another refresh is running"):
        run(paths, offline=True, fetch_images=False)
    assert not paths.gamedata.exists()


def test_fixture_generation_keeps_old_fixtures_on_failure(tmp_path: Path) -> None:
    """Review 3 R12: missing raw input never deletes the existing fixtures."""
    out = tmp_path / "fixtures"
    out.mkdir()
    (out / "keep.json").write_text("{}")
    with pytest.raises(FileNotFoundError):
        fixtures.write(tmp_path / "no-raw", out)
    assert (out / "keep.json").exists()
    assert not list(tmp_path.glob(".*staging"))


def test_setting_aside_fails_midway_restores_every_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 3 R7: an error while moving the old files aside rolls back what was moved."""
    for name in ("a", "b"):
        (tmp_path / name).write_text(f"old {name}")
    real_replace = os.replace
    calls = 0

    def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    fetched = [Fetched(n, "u", b"new") for n in ("a", "b")]
    with pytest.raises(OSError, match="disk full"), saved_until_failure(tmp_path, fetched):
        pass
    assert [(tmp_path / n).read_text() for n in ("a", "b")] == ["old a", "old b"]
    assert not list(tmp_path.glob(".*.prev"))


def test_offline_refuses_files_left_by_a_killed_refresh(paths: Paths) -> None:
    """Review 4 P3: after a hard kill `.prev` copies say the raw files are unverified."""
    run(paths, offline=True, fetch_images=False)
    (paths.raw / "wfcd/.Primary.json.prev").write_text("[]")
    with pytest.raises(RuntimeError, match=r"wfcd/\.Primary\.json\.prev"):
        run(paths, offline=True, fetch_images=False)


def test_report_lists_support_coverage(paths: Paths) -> None:
    report = run(paths, offline=True, fetch_images=False)
    counts = report.meta.counts
    assert (
        counts["mods_full"] + counts["mods_partial"] + counts["mods_unsupported"] == counts["mods"]
    )
    text = "\n".join(report.lines())
    assert "support (damage-related text not modelled):" in text
    assert "Galvanized Aptitude" in text  # partial: per-status-type bonus
