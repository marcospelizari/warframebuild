"""Reading raw sources and reference/ files: shape checks that fail the refresh."""

import json
import re
from pathlib import Path
from typing import Any

from app.pipeline.errors import RefreshError


def records(data: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise RefreshError(f"source format changed: no list `{key}`")
    return data[key]  # type: ignore[no-any-return]


def as_list(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise RefreshError("source format changed: WFCD file is not a list")
    return data


def reference(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RefreshError(f"{path}: expected an object")
    return data


def require_verified(entry: dict[str, Any], file: str, key: str) -> None:
    """Hand-checked reference entries carry `verified` (YYYY-MM-DD): `wfb check` lists
    them for re-check once the data changes after that date (G48)."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry.get("verified", ""))):
        raise RefreshError(f"reference/{file} {key}: `verified` (YYYY-MM-DD) is required")


# "Puncture_Damage:18-20" or "Status_Effect:252, :256"
_CITE = re.compile(r"(?P<page>[A-Za-z_()]+):\d+(?:-\d+)?(?:, :\d+(?:-\d+)?)*")


def require_cites(sources: Any, file: str, key: str, titles: dict[str, str]) -> None:
    """`sources`: one or more 'Page:line' of saved pages listed in wiki_pages.json."""
    if not isinstance(sources, list) or not sources:
        raise RefreshError(f"reference/{file} {key}: `source` lists saved pages and lines")
    for cite in sources:
        m = _CITE.fullmatch(cite) if isinstance(cite, str) else None
        if m is None or m["page"] not in titles:
            raise RefreshError(
                f"reference/{file} {key}: source {cite!r} is not 'Page:line' of a saved page "
                "listed in wiki_pages.json"
            )
