"""Change detection after a game update (G41/G48).

Sources are compared with what the current gamedata/ was built from (meta.json), so a
failed refresh never hides a change. `wfb check` (before a refresh) lists changed
sources, reference rows verified before the last data change, and the wiki pages.
`wfb refresh` adds, after building, new/changed/removed entries and the rows they touch.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.data.build import Dataset
from app.data.http import PoliteClient
from app.data.models import SourceRecord
from app.data.sources import Fetched, sha256_16, wfcd
from app.data.sources import de_export as de
from app.data.sources.wiki_local import pages, saved_date
from app.data.store import GameData
from app.domain.effects import Support

MAX_LISTED = 25
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


# ---------- sources ----------


def changed(
    fetched: list[Fetched],
    built_from: list[SourceRecord] | None,
    no_dataset: str = "no current dataset",
) -> list[str]:
    """Sources that differ from the ones the current dataset was built from.

    `no_dataset` is the line when there is nothing to compare with (unreadable or none).
    """
    if built_from is None:
        return [no_dataset]
    known = {s.path: s for s in built_from}
    out = []
    for f in fetched:
        if f.path == de.INDEX_PATH:
            continue  # changes whenever any export changes; the exports are listed instead
        rec = known.get(f.path)
        if (
            rec is None
            or rec.url != f.url
            or (f.data is not None and rec.sha256_16 != sha256_16(f.data))
        ):
            out.append(f.path)
    return out


def source_changes(client: PoliteClient, built_from: list[SourceRecord] | None) -> list[str]:
    """For `wfb check`: DE index only (export URLs carry their hash), WFCD into memory."""
    _, exports = de.resolve(client)
    return changed(exports + wfcd.fetch(client), built_from)


# ---------- reference rows ----------


@dataclass(frozen=True)
class RefRow:
    file: str
    key: str  # uniqueName or rule id
    label: str
    verified: str  # ISO date
    depends_on: tuple[str, ...] = ()  # uniqueNames in the row's `mods` list


def reference_rows(reference_dir: Path) -> list[RefRow]:
    """Every row carrying `verified` in reference/*.json (dicts keyed by ID, or lists with `id`)."""
    rows = []
    for path in sorted(reference_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for container in data.values() if isinstance(data, dict) else []:
            items: list[tuple[str, Any]]
            if isinstance(container, dict):
                items = list(container.items())
            elif isinstance(container, list):
                items = [
                    (str(r.get("id", i)), r) for i, r in enumerate(container) if isinstance(r, dict)
                ]
            else:
                continue
            for key, row in items:
                if isinstance(row, dict) and "verified" in row:
                    verified = str(row["verified"])
                    if not _ISO_DATE.fullmatch(verified):
                        raise ValueError(
                            f"{path.name} {key}: verified must be YYYY-MM-DD, got {verified!r}"
                        )
                    mods = row.get("mods", [])
                    rows.append(
                        RefRow(
                            path.name,
                            key,
                            str(row.get("name", key)),
                            verified,
                            tuple(m for m in mods if isinstance(m, str)),
                        )
                    )
    return rows


def stale_rows(rows: list[RefRow], changed_on: str) -> list[RefRow]:
    """Rows verified before the data last changed."""
    return [r for r in rows if r.verified < changed_on]


# ---------- entry diff ----------


@dataclass
class EntryDiff:
    new: dict[str, list[str]] = field(default_factory=dict)  # kind -> names
    changed: dict[str, list[str]] = field(default_factory=dict)
    removed: dict[str, list[str]] = field(default_factory=dict)
    ids: set[str] = field(default_factory=set)  # every new/changed/removed uniqueName
    unavailable: str | None = None  # previous dataset could not be read: no diff possible

    @property
    def empty(self) -> bool:
        return self.unavailable is None and not self.ids


def entry_diff(
    previous: GameData | None, previous_error: str | None, dataset: Dataset
) -> EntryDiff:
    if previous_error is not None:
        return EntryDiff(unavailable=previous_error)
    diff = EntryDiff()
    if previous is None:
        return diff  # first refresh: nothing to compare with
    kinds: dict[str, tuple[list[Any], list[Any]]] = {
        "weapons": (previous.weapons, dataset.weapons),
        "mods": (previous.mods.mods, dataset.mods),
        "arcanes": (previous.arcanes, dataset.arcanes),
    }
    for kind, (old, new) in kinds.items():
        before = {e.unique_name: e for e in old}
        after = {e.unique_name: e for e in new}
        changed_ids = {u for u in after.keys() & before.keys() if _differs(before[u], after[u])}
        diff.new[kind] = sorted(after[u].name for u in after.keys() - before.keys())
        diff.removed[kind] = sorted(before[u].name for u in before.keys() - after.keys())
        diff.changed[kind] = sorted(after[u].name for u in changed_ids)
        diff.ids |= (after.keys() ^ before.keys()) | changed_ids
    return diff


def _differs(a: BaseModel, b: BaseModel) -> bool:
    # Slugs can move when a new namesake appears; that is not a data change.
    return a.model_dump(exclude={"slug"}) != b.model_dump(exclude={"slug"})


def touched_rows(rows: list[RefRow], diff: EntryDiff) -> list[RefRow]:
    if diff.unavailable is not None:
        return rows  # unknown what changed: every row needs a look
    return [r for r in rows if r.key in diff.ids or not diff.ids.isdisjoint(r.depends_on)]


# ---------- report text ----------


def _names(names: list[str]) -> str:
    shown = ", ".join(names[:MAX_LISTED])
    return shown + (f" … (+{len(names) - MAX_LISTED})" if len(names) > MAX_LISTED else "")


def support_lines(dataset: Dataset) -> list[str]:
    """R6: entries the calculator does not fully model; builds leave them out."""
    out = []
    for kind, entries in (("mods", dataset.mods), ("arcanes", dataset.arcanes)):
        for level in (Support.UNSUPPORTED, Support.PARTIAL):
            names = sorted(e.name for e in entries if e.effects.support == level)
            if names:
                out.append(f"  {level.value} {kind} ({len(names)}): " + ", ".join(names))
    return ["support (damage-related text not modelled):", *out] if out else []


def source_lines(changes: list[str] | None) -> list[str]:
    if changes is None:
        return ["sources: not checked (offline)"]
    if not changes:
        return ["sources: DE and WFCD unchanged since the current dataset"]
    return ["sources changed since the current dataset: " + ", ".join(changes)]


def diff_lines(diff: EntryDiff, touched: list[RefRow], changed_on: str) -> list[str]:
    if diff.unavailable is not None:
        out = [
            f"entries: previous dataset unreadable ({diff.unavailable}); "
            "diff unavailable, re-check every reference row"
        ]
    elif diff.empty:
        return ["entries: no new, changed or removed weapons, mods or arcanes"]
    else:
        out = ["entries since the previous dataset:"]
        for label, part in (
            ("new", diff.new),
            ("changed", diff.changed),
            ("removed", diff.removed),
        ):
            for kind, names in part.items():
                if names:
                    out.append(f"  {label} {kind} ({len(names)}): {_names(names)}")
        if diff.new.get("weapons"):
            out.append("  new weapons need their reference rows (headshot, main attack, fire data)")
    if touched:
        out.append(f"reference rows to re-check (data changed on {changed_on}):")
        out += [f"  {r.file}: {r.label} (verified {r.verified})" for r in touched]
    return out


def wiki_lines(raw_dir: Path, reference_dir: Path) -> list[str]:
    out = ["wiki pages to compare with their history (open, re-save changed ones):"]
    for p in pages(reference_dir):
        path = raw_dir / "wiki" / f"{p.stem}.wikitext"
        saved = saved_date(path) if path.is_file() else "MISSING"
        out.append(f"  [{p.impact}] {p.title} (saved {saved}) {p.history_url}")
        out.append(f"      feeds: {'; '.join(p.feeds)}")
    return out


def stale_lines(stale: list[RefRow], changed_on: str) -> list[str]:
    if not stale:
        return [f"reference rows: all verified on or after the last data change ({changed_on})"]
    by_file: dict[str, int] = {}
    for r in stale:
        by_file[r.file] = by_file.get(r.file, 0) + 1
    parts = ", ".join(f"{f} {n}" for f, n in sorted(by_file.items()))
    return [f"reference rows verified before the last data change ({changed_on}): {parts}"]
