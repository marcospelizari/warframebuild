"""WARFRAME Wiki pages saved by hand (T2): never fetched, only read from cache/raw/wiki/.

The page list lives in reference/wiki_pages.json (stem, canonical title, what it feeds).
"""

import datetime
import json
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.sources import SourceFile, sha256_16

WIKI_URL = "https://wiki.warframe.com/w"
IMPACT_ORDER = {"high": 0, "medium": 1, "low": 2}


class MissingWikiPages(RuntimeError):
    pass


@dataclass(frozen=True)
class Page:
    stem: str  # file name in cache/raw/wiki/ without .wikitext
    title: str
    impact: str
    feeds: list[str]

    @property
    def url(self) -> str:
        return f"{WIKI_URL}/{self.title}"

    @property
    def history_url(self) -> str:
        return f"{self.url}?action=history"

    @property
    def raw_url(self) -> str:
        return f"{self.url}?action=raw"


def pages(reference_dir: Path) -> list[Page]:
    data = json.loads((reference_dir / "wiki_pages.json").read_text(encoding="utf-8"))
    out = [
        Page(stem, p["title"], p["impact"], list(p["feeds"])) for stem, p in data["pages"].items()
    ]
    unknown = [p.stem for p in out if p.impact not in IMPACT_ORDER]
    if unknown:
        raise ValueError(f"wiki_pages.json: unknown impact for {unknown}")
    return sorted(out, key=lambda p: (IMPACT_ORDER[p.impact], p.stem))


def scan(raw_dir: Path, reference_dir: Path) -> list[SourceFile]:
    """Fail on a listed page that is missing; record every saved page (listed or not)."""
    wiki_dir = raw_dir / "wiki"
    listed = {p.stem: p for p in pages(reference_dir)}
    missing = [p for p in listed.values() if not (wiki_dir / f"{p.stem}.wikitext").is_file()]
    if missing:
        hint = "\n".join(f"  {p.raw_url} -> {wiki_dir}/{p.stem}.wikitext" for p in missing)
        raise MissingWikiPages(f"save these wiki pages by browser:\n{hint}")
    files = []
    for path in sorted(wiki_dir.glob("*.wikitext")):
        page = listed.get(path.stem)
        url = page.url if page else f"{WIKI_URL}/{path.stem}"
        files.append(
            SourceFile(f"wiki/{path.name}", url, saved_date(path), sha256_16(path.read_bytes()))
        )
    return files


def saved_date(path: Path) -> str:
    return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
