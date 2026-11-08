"""Shared helpers for turning raw sources into gamedata models."""

import json
import re
from pathlib import Path
from typing import Any

_TAG = re.compile(r"<[A-Z0-9_]+>")
_SLUG = re.compile(r"[^a-z0-9]+")


class RefreshError(RuntimeError):
    pass


def clean_text(text: str) -> str:
    """Strip DE markup (`<DT_SLASH_COLOR>` …); untrusted text, kept as plain text only."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("<LINE_SEPARATOR>", "\n")
    return _TAG.sub("", text).strip()


def clean_levels(levels: list[dict[str, Any]]) -> list[list[str]]:
    return [[clean_text(s) for s in level["stats"]] for level in levels]


def slugify(name: str) -> str:
    return _SLUG.sub("-", name.lower()).strip("-")


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
