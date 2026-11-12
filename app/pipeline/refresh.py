"""`wfb refresh`: download, compare, build, validate, swap into gamedata/ (Q32/T1/T2/G48)."""

from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from app.gamedata import store
from app.gamedata.models import Meta, SourceRecord
from app.pipeline import check, images, publish
from app.pipeline.build import build
from app.pipeline.sources import (
    SourceFile,
    de_export,
    export_plus,
    interrupted_saves,
    saved_until_failure,
    scan_downloaded,
    wfcd,
    wiki_local,
    write_sources,
)
from app.pipeline.sources.http import PoliteClient

DOWNLOADED = [
    de_export.INDEX_PATH,
    *(f"de/{n}" for n in de_export.EXPORTS),
    *(f"wfcd/{n}" for n in wfcd.FILES),
]


@dataclass(frozen=True)
class Paths:
    raw: Path
    reference: Path
    gamedata: Path
    img: Path

    @classmethod
    def project(cls, root: Path) -> "Paths":
        return cls(root / "cache/raw", root / "reference", root / "gamedata", root / "cache/img")


@dataclass
class Report:
    meta: Meta
    previous: Meta | None
    source_changes: list[str] | None = None  # None = not checked (offline)
    diff: check.EntryDiff = field(default_factory=check.EntryDiff)
    touched: list[check.RefRow] = field(default_factory=list)
    wiki: list[str] = field(default_factory=list)
    support: list[str] = field(default_factory=list)
    untagged: list[str] = field(default_factory=list)
    export_plus: list[str] = field(default_factory=list)
    image_failures: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = check.source_lines(self.source_changes)
        out += self._dataset_lines(self.meta, self.previous)
        out += check.diff_lines(self.diff, self.touched, self.meta.changed_on)
        out += self.support
        out += self.untagged
        out += self.wiki
        out += self.export_plus
        if self.image_failures:
            out.append(f"{len(self.image_failures)} image downloads failed:")
            out += [f"  {f}" for f in self.image_failures]
        return out

    @staticmethod
    def _dataset_lines(m: Meta, p: Meta | None) -> list[str]:
        out = [
            f"dataset {m.dataset_hash} ({m.game_update}, fetched {m.fetched}, "
            f"changed {m.changed_on})"
        ]
        for key, value in m.counts.items():
            before = p.counts.get(key) if p else None
            delta = "" if before is None or before == value else f" (was {before})"
            out.append(f"  {key}: {value}{delta}")
        out.append("  excluded weapons:")
        out += [f"    {e.name}: {e.reason}" for e in m.excluded_weapons]
        out.append("  denied gun mods: " + ", ".join(f"{k} {v}" for k, v in m.denied_mods.items()))
        if p and p.dataset_hash == m.dataset_hash:
            out.append("  no data change")
        return out


def run(
    paths: Paths, *, offline: bool, fetch_images: bool, client: PoliteClient | None = None
) -> Report:
    """One refresh at a time: the lock covers the raw cache from download to publish."""
    paths.raw.mkdir(parents=True, exist_ok=True)
    with publish.exclusive(paths.raw / ".refresh.lock"):
        return _run(paths, offline=offline, fetch_images=fetch_images, client=client)


def _run(paths: Paths, *, offline: bool, fetch_images: bool, client: PoliteClient | None) -> Report:
    previous, previous_error = load_previous(paths.gamedata)
    # Fail early: nothing is downloaded while a hand-saved file is missing.
    saved_files = wiki_local.scan(paths.raw, paths.reference) + export_plus.scan(paths.raw)
    reference_rows = check.reference_rows(paths.reference)  # bad dates fail before publishing
    changes: list[str] | None = None
    saving: AbstractContextManager[list[SourceFile]]
    if offline:
        leftovers = interrupted_saves(paths.raw)
        if leftovers:
            raise RuntimeError(
                "an interrupted refresh left previous downloads aside "
                f"({', '.join(leftovers)}); which copy is good is unknown: "
                "run `wfb refresh` without --offline"
            )
        saving = nullcontext(scan_downloaded(paths.raw, DOWNLOADED))
    else:
        client = client or PoliteClient()
        fetched = de_export.fetch(client) + wfcd.fetch(client)
        changes = check.changed(
            fetched,
            previous.meta.sources if previous else None,
            "previous dataset unreadable" if previous_error else "no current dataset",
        )
        saving = saved_until_failure(paths.raw, fetched)
    with saving as downloaded:
        files = sorted(downloaded + saved_files, key=lambda f: f.path)
        dataset = build(paths.raw, paths.reference)
        meta = publish.write(
            dataset,
            [_record(f) for f in files],
            paths.gamedata,
            previous.meta if previous else None,
        )
    write_sources(paths.raw, files)  # only once the new dataset is in place

    diff = check.entry_diff(previous, previous_error, dataset)
    report = Report(
        meta=meta,
        previous=previous.meta if previous else None,
        source_changes=changes,
        diff=diff,
        touched=check.touched_rows(reference_rows, diff),
        support=check.support_lines(dataset),
        untagged=check.untagged_lines(dataset)
        + check.module_gap_lines(dataset)
        + check.incarnon_gap_lines(dataset),
        # After a game update the hand-saved files need a look too.
        wiki=check.wiki_lines(paths.raw, paths.reference) if changes else [],
        export_plus=check.export_plus_lines(paths.raw) if changes else [],
    )
    if fetch_images and client is not None:
        report.image_failures = images.fetch_missing(
            client,
            images.weapon_pictures(dataset.weapons, paths.img)
            + images.item_pictures("mods", dataset.mods, paths.img)
            + images.item_pictures("arcanes", dataset.arcanes, paths.img),
        )
    return report


def load_previous(gamedata: Path) -> tuple[store.GameData | None, str | None]:
    """(dataset, None), (None, None) on first run, or (None, reason) when unreadable.

    Read-only: after a crash between the swap renames, reads the `.old` copy that
    publish.write will restore under its lock.
    """
    source = gamedata if gamedata.exists() else publish.backup_dir(gamedata)
    if not (source / "meta.json").exists():
        return None, None
    try:
        return store.load(source), None
    except (OSError, ValueError) as error:
        return None, str(error).splitlines()[0]


def _record(f: SourceFile) -> SourceRecord:
    return SourceRecord(path=f.path, url=f.url, retrieved=f.retrieved, sha256_16=f.sha256_16)
