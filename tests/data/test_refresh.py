import pytest

from app.data import store
from app.data.refresh import Paths, run
from app.data.sources import read_sources, wiki_local


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


def test_tampered_gamedata_is_rejected(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    (paths.gamedata / "weapons.json").write_text("[]\n")
    with pytest.raises(ValueError, match="dataset_hash"):
        store.load(paths.gamedata)
