"""`wfb refresh`: download -> cache/raw/, build, validate, swap into gamedata/ (Q32/T1/T2)."""

from dataclasses import dataclass, field
from pathlib import Path

from app.data import build, images, store
from app.data.http import PoliteClient
from app.data.models import Meta, SourceRecord
from app.data.sources import (
    SourceFile,
    de_export,
    scan_downloaded,
    wfcd,
    wiki_local,
    write_sources,
)

DOWNLOADED = [
    "de/index_en.txt.lzma",
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
    image_failures: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        m, p = self.meta, self.previous
        out = [f"dataset {m.dataset_hash} ({m.game_update}, fetched {m.fetched})"]
        for key, value in m.counts.items():
            before = p.counts.get(key) if p else None
            delta = "" if before is None or before == value else f" (was {before})"
            out.append(f"  {key}: {value}{delta}")
        out.append("  excluded weapons:")
        out += [f"    {e.name}: {e.reason}" for e in m.excluded_weapons]
        out.append("  denied gun mods: " + ", ".join(f"{k} {v}" for k, v in m.denied_mods.items()))
        if p and p.dataset_hash == m.dataset_hash:
            out.append("  no data change")
        if self.image_failures:
            out.append(f"  {len(self.image_failures)} image downloads failed:")
            out += [f"    {f}" for f in self.image_failures]
        return out


def run(
    paths: Paths, *, offline: bool, fetch_images: bool, client: PoliteClient | None = None
) -> Report:
    previous = _previous_meta(paths.gamedata)
    wiki_files = wiki_local.scan(paths.raw)  # fail early: nothing is downloaded on a missing page
    if offline:
        downloaded = scan_downloaded(paths.raw, DOWNLOADED)
    else:
        client = client or PoliteClient()
        downloaded = de_export.download(client, paths.raw) + wfcd.download(client, paths.raw)
    files = sorted(downloaded + wiki_files, key=lambda f: f.path)
    write_sources(paths.raw, files)

    dataset = build.build(paths.raw, paths.reference)
    meta = store.write(dataset, [_record(f) for f in files], paths.gamedata)
    report = Report(meta=meta, previous=previous)
    if fetch_images and not offline:
        report.image_failures = images.fetch_missing(
            client or PoliteClient(), dataset.weapons, paths.img
        )
    return report


def _record(f: SourceFile) -> SourceRecord:
    return SourceRecord(path=f.path, url=f.url, retrieved=f.retrieved, sha256_16=f.sha256_16)


def _previous_meta(gamedata: Path) -> Meta | None:
    try:
        return Meta.model_validate_json((gamedata / "meta.json").read_bytes())
    except (OSError, ValueError):
        return None
