"""Raw source files in cache/raw/ and their record in cache/raw/SOURCES.json."""

import datetime
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFile:
    path: str  # relative to cache/raw/
    url: str
    retrieved: str  # ISO date: download date, or save date for hand-saved wiki pages
    sha256_16: str


@dataclass(frozen=True)
class Fetched:
    """A download held in memory; `data` is None when only the URL was resolved."""

    path: str  # relative to cache/raw/
    url: str
    data: bytes | None


def sha256_16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def atomic_write(path: Path, data: bytes) -> None:
    """Write via a temp file and rename, so a reader never sees a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def save(raw_dir: Path, fetched: list[Fetched]) -> list[SourceFile]:
    today = datetime.date.today().isoformat()
    files = []
    for f in fetched:
        if f.data is None:
            raise ValueError(f"{f.path}: nothing downloaded")
        atomic_write(raw_dir / f.path, f.data)
        files.append(SourceFile(f.path, f.url, today, sha256_16(f.data)))
    return files


def write_sources(raw_dir: Path, files: list[SourceFile]) -> None:
    entries = {f.path: {k: v for k, v in asdict(f).items() if k != "path"} for f in files}
    text = json.dumps({"files": dict(sorted(entries.items()))}, indent=2, ensure_ascii=False)
    atomic_write(raw_dir / "SOURCES.json", (text + "\n").encode())


def read_sources(raw_dir: Path) -> dict[str, SourceFile]:
    path = raw_dir / "SOURCES.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files", {})
    return {p: SourceFile(path=p, **entry) for p, entry in files.items()}


def scan_downloaded(raw_dir: Path, names: list[str]) -> list[SourceFile]:
    """Records for already downloaded files (offline refresh), `names` relative to raw_dir.

    Keeps URL and date from SOURCES.json when the hash still matches; otherwise the
    file date stands in and the URL is left empty.
    """
    known = read_sources(raw_dir)
    files = []
    for rel in names:
        path = raw_dir / rel
        if not path.is_file():
            raise FileNotFoundError(f"{path} missing: run `wfb refresh` without --offline")
        digest = sha256_16(path.read_bytes())
        entry = known.get(rel)
        if entry and entry.sha256_16 == digest:
            files.append(entry)
        else:
            saved = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
            files.append(SourceFile(rel, "", saved, digest))
    return files


def load_json(path: Path) -> object:
    # DE exports contain raw control characters inside strings.
    return json.loads(path.read_text(encoding="utf-8"), strict=False)
