"""Rows of reference/*.json that carry `verified` (G41/G48): which to re-check after a data
change, and which the entry diff touched."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pipeline.changes import EntryDiff

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class RefRow:
    file: str
    key: str  # uniqueName or rule id
    label: str
    verified: str  # ISO date
    depends_on: tuple[str, ...] = ()  # uniqueNames in the row's `mods` list


def reference_rows(reference_dir: Path) -> list[RefRow]:
    """Every row carrying `verified` in reference/*.json: dicts keyed by ID, lists with `id`,
    or a single row under its own key (headshot.json `reference_head`)."""
    rows = []
    for path in sorted(reference_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, container in data.items() if isinstance(data, dict) else []:
            items: list[tuple[str, Any]]
            if isinstance(container, dict) and "verified" in container:
                items = [(name, container)]
            elif isinstance(container, dict):
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


def touched_rows(rows: list[RefRow], diff: EntryDiff) -> list[RefRow]:
    if diff.unavailable is not None:
        return rows  # unknown what changed: every row needs a look
    return [r for r in rows if r.key in diff.ids or not diff.ids.isdisjoint(r.depends_on)]


def stale_lines(stale: list[RefRow], changed_on: str) -> list[str]:
    if not stale:
        return [f"reference rows: all verified on or after the last data change ({changed_on})"]
    by_file: dict[str, int] = {}
    for r in stale:
        by_file[r.file] = by_file.get(r.file, 0) + 1
    parts = ", ".join(f"{f} {n}" for f, n in sorted(by_file.items()))
    return [f"reference rows verified before the last data change ({changed_on}): {parts}"]
