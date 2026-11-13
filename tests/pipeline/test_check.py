import json

import pytest

from app.domain.effects import DamageType
from app.gamedata import store
from app.gamedata.meta import Meta, SourceRecord
from app.pipeline import check, publish, reference_rows
from app.pipeline.build import build
from app.pipeline.refresh import Paths, load_previous, run
from app.pipeline.sources import de_export as de
from app.pipeline.sources import sha256_16, wfcd
from app.pipeline.sources.http import PoliteClient
from app.pipeline.sources.wiki_local import MissingWikiPages, pages, scan
from tests.conftest import FIXTURE_RAW


class FakeClient(PoliteClient):
    """Serves the fixture files for every DE/WFCD URL the refresh asks for."""

    def __init__(self) -> None:
        super().__init__(sleep=lambda _: None)
        index = (FIXTURE_RAW / "de/index_en.txt.lzma").read_bytes()
        entries = de.decode_index(index)
        self.files = {de.INDEX_URL: index}
        for name in de.EXPORTS:
            self.files[f"{de.BASE_URL}/Manifest/{entries[name]}"] = (
                FIXTURE_RAW / "de" / name
            ).read_bytes()
        for name in wfcd.FILES:
            self.files[f"{wfcd.BASE_URL}/{name}"] = (FIXTURE_RAW / "wfcd" / name).read_bytes()

    def get(self, url: str, *, max_bytes: int) -> bytes:
        return self.files[url]


def _built_from_fixtures() -> list[SourceRecord]:
    entries = de.decode_index((FIXTURE_RAW / "de/index_en.txt.lzma").read_bytes())
    records = [
        SourceRecord(
            path=f"de/{n}",
            url=f"{de.BASE_URL}/Manifest/{entries[n]}",
            retrieved="2026-11-08",
            sha256_16=sha256_16((FIXTURE_RAW / "de" / n).read_bytes()),
        )
        for n in de.EXPORTS
    ]
    records += [
        SourceRecord(
            path=f"wfcd/{n}",
            url=f"{wfcd.BASE_URL}/{n}",
            retrieved="2026-11-08",
            sha256_16=sha256_16((FIXTURE_RAW / "wfcd" / n).read_bytes()),
        )
        for n in wfcd.FILES
    ]
    return records


def test_source_changes_none_when_dataset_matches() -> None:
    assert check.source_changes(FakeClient(), _built_from_fixtures()) == []


def test_source_changes_lists_new_manifest_and_wfcd_file() -> None:
    client = FakeClient()
    client.files[f"{wfcd.BASE_URL}/Primary.json"] = b"[]"
    built = [
        r.model_copy(update={"url": r.url + "-old"}) if r.path == "de/ExportWeapons_en.json" else r
        for r in _built_from_fixtures()
    ]
    assert check.source_changes(client, built) == ["de/ExportWeapons_en.json", "wfcd/Primary.json"]


def test_failed_refresh_does_not_hide_the_change(paths: Paths) -> None:
    """Review bug 1: sources are compared with the dataset, not with SOURCES.json."""
    run(paths, offline=False, fetch_images=False, client=FakeClient())
    meta = store.load(paths.gamedata).meta
    changed_client = FakeClient()
    changed_client.files[f"{wfcd.BASE_URL}/Primary.json"] = b"{}"  # breaks the build
    with pytest.raises(Exception, match="WFCD file is not a list"):
        run(paths, offline=False, fetch_images=False, client=changed_client)
    assert store.load(paths.gamedata).meta == meta
    assert check.source_changes(changed_client, meta.sources) == ["wfcd/Primary.json"]


def test_failed_refresh_restores_the_downloads(paths: Paths) -> None:
    """Review 2 (#1): a refresh that fails after downloading puts the previous raw
    files back, so --offline still rebuilds the last good dataset."""
    run(paths, offline=False, fetch_images=False, client=FakeClient())
    primary = paths.raw / "wfcd/Primary.json"
    good = primary.read_bytes()
    broken = FakeClient()
    broken.files[f"{wfcd.BASE_URL}/Primary.json"] = b"{}"
    with pytest.raises(Exception, match="WFCD file is not a list"):
        run(paths, offline=False, fetch_images=False, client=broken)
    assert primary.read_bytes() == good
    assert not list(paths.raw.rglob(".*.prev"))
    report = run(paths, offline=True, fetch_images=False)
    assert report.meta == store.load(paths.gamedata).meta


def test_online_refresh_downloads_each_source_once(paths: Paths) -> None:
    client = FakeClient()
    asked: list[str] = []
    original = client.get

    def counting_get(url: str, *, max_bytes: int) -> bytes:
        asked.append(url)
        return original(url, max_bytes=max_bytes)

    client.get = counting_get  # type: ignore[method-assign]
    run(paths, offline=False, fetch_images=False, client=client)
    assert len(asked) == len(set(asked)) == 1 + len(de.EXPORTS) + len(wfcd.FILES)


def test_changed_on_moves_only_when_data_changes(paths: Paths) -> None:
    """Review bug 2: staleness follows data changes, not the newest gun's update name."""
    dataset = build(paths.raw, paths.reference)

    def source(day: str) -> list[SourceRecord]:
        return [
            SourceRecord(path="de/ExportWeapons_en.json", url="u", retrieved=day, sha256_16="x")
        ]

    first = publish.write(dataset, source("2026-11-01"), paths.gamedata, None, today="2026-11-01")
    assert first.changed_on == "2026-11-01"
    same = publish.write(dataset, source("2026-11-20"), paths.gamedata, first, today="2026-11-20")
    assert (same.fetched, same.changed_on) == ("2026-11-20", "2026-11-01")

    _bump_first_weapon(paths)
    moved = publish.write(
        build(paths.raw, paths.reference),
        source("2026-12-03"),
        paths.gamedata,
        same,
        today="2026-12-03",
    )
    assert moved.changed_on == "2026-12-03"
    rows = reference_rows.reference_rows(paths.reference)
    assert reference_rows.stale_rows(rows, moved.changed_on) == rows


def test_changed_on_is_the_refresh_date_never_earlier(paths: Paths) -> None:
    """Review 2: an offline rebuild of old downloads that changes the data dates the
    change today, and changed_on never moves backwards."""
    old_download = [
        SourceRecord(
            path="de/ExportWeapons_en.json", url="u", retrieved="2026-10-01", sha256_16="x"
        )
    ]
    first = publish.write(
        build(paths.raw, paths.reference), old_download, paths.gamedata, None, today="2026-11-08"
    )
    assert first.changed_on == "2026-11-08"
    _bump_first_weapon(paths)
    clock_behind = publish.write(
        build(paths.raw, paths.reference), old_download, paths.gamedata, first, today="2026-11-07"
    )
    assert clock_behind.changed_on == "2026-11-08"


def _bump_first_weapon(paths: Paths) -> None:
    weapons = paths.raw / "de/ExportWeapons_en.json"
    data = json.loads(weapons.read_text())
    data["ExportWeapons"][0]["criticalChance"] += 0.01
    weapons.write_text(json.dumps(data))


def test_unreadable_previous_dataset_is_reported(paths: Paths) -> None:
    """Review bug 3: an unreadable previous dataset never reads as 'no changes'."""
    run(paths, offline=True, fetch_images=False)
    (paths.gamedata / "meta.json").write_text('{"schema_version": 1}')
    previous, error = load_previous(paths.gamedata)
    current = Meta.model_fields["schema_version"].default
    assert previous is None and error and f"schema version 1, this code reads {current}" in error
    report = run(paths, offline=True, fetch_images=False)
    text = "\n".join(report.lines())
    assert "no comparison with the previous dataset" in text
    assert "no new, changed or removed" not in text
    assert len(report.touched) == len(reference_rows.reference_rows(paths.reference))


def test_refresh_reports_no_entry_change_on_rerun(paths: Paths) -> None:
    run(paths, offline=True, fetch_images=False)
    lines = run(paths, offline=True, fetch_images=False).lines()
    assert "sources: not checked (offline)" in lines
    assert "entries: no new, changed or removed weapons, mods or arcanes" in lines


def test_missing_page_names_raw_url(paths: Paths) -> None:
    (paths.raw / "wiki/Calculation.wikitext").unlink()
    with pytest.raises(MissingWikiPages, match=r"Damage/Calculation\?action=raw"):
        scan(paths.raw, paths.reference)


def test_wiki_lines_sorted_by_impact(paths: Paths) -> None:
    lines = [ln for ln in check.wiki_lines(paths.raw, paths.reference) if ln.startswith("  [")]
    impacts = [ln.split("]")[0].strip(" [") for ln in lines]
    assert impacts == sorted(impacts, key=["high", "medium", "low"].index)


def test_export_plus_lines_list_each_saved_file(paths: Paths) -> None:
    (paths.raw / "export-plus/ExportWeapons.json").unlink()
    lines = check.export_plus_lines(paths.raw)
    assert any("ExportUpgrades.json (saved 20" in ln for ln in lines)
    assert any("ExportWeapons.json (saved MISSING)" in ln for ln in lines)


def test_unreadable_dataset_source_line_says_so(paths: Paths) -> None:
    """Review 4 P3: the source line no longer claims there is no dataset."""
    run(paths, offline=True, fetch_images=False)
    (paths.gamedata / "meta.json").write_text('{"schema_version": 1}')
    report = run(paths, offline=False, fetch_images=False, client=FakeClient())
    assert report.source_changes == ["previous dataset unreadable"]
    assert not list(paths.raw.rglob(".*.prev"))


def test_status_rule_rows_are_listed_with_their_wiki_pages(paths: Paths) -> None:
    """U13: one row per damage type; every cited saved page names the file in its feeds."""
    rows = [
        r for r in reference_rows.reference_rows(paths.reference) if r.file == "status_rules.json"
    ]
    assert {r.key for r in rows} == {t.value for t in DamageType}
    table = json.loads((paths.reference / "status_rules.json").read_text())
    cited = {c.split(":")[0] for row in table["types"].values() for c in row["source"]}
    assert "Puncture_Damage" in cited and "Status_Effect" in cited
    feeding = {p.stem for p in pages(paths.reference) if any("status_rules" in f for f in p.feeds)}
    assert feeding == cited
    text = "\n".join(check.wiki_lines(paths.raw, paths.reference))
    assert "status_rules.json" in text
