"""Shared helpers for turning raw sources into gamedata models."""

import json
import re
from pathlib import Path
from typing import Any

from app.data.sources.de_export import DAMAGE_TAGS, DAMAGE_WORDS

_TAG = re.compile(r"<([A-Z0-9_]+)>")
_SPACES = re.compile(r"[ \t]{2,}")
_WORD = re.compile(r"[A-Za-z]+")
_SLUG = re.compile(r"[^a-z0-9]+")


class RefreshError(RuntimeError):
    pass


def clean_text(text: str) -> str:
    """DE markup -> plain text; untrusted, kept as plain text only.

    A damage tag becomes its type name unless the name (or a DE synonym) is one of
    the next two words: `<DT_FIRE_COLOR>Heat` -> `Heat`, `<DT_GAS_COLOR>Extra Gas`
    -> `Extra Gas`, `apply <DT_SLASH_COLOR> on` -> `apply Slash on`. Other tags are
    dropped; an unknown `DT_` tag raises RefreshError.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("<LINE_SEPARATOR>", "\n")

    def tag(match: re.Match[str]) -> str:
        name = match.group(1)
        if not name.startswith("DT_"):
            return ""
        damage = DAMAGE_TAGS.get(name.removesuffix("_COLOR"))
        if damage is None:
            raise RefreshError(
                f"unknown DE damage tag <{name}> in {text!r}: add it to DAMAGE_TAGS "
                "in app/data/sources/de_export.py"
            )
        word = damage.value.capitalize()
        following = _WORD.findall(text, match.end())[:2]
        return "" if {word, *DAMAGE_WORDS.get(damage, ())} & set(following) else f"{word} "

    lines = (_SPACES.sub(" ", line).strip() for line in _TAG.sub(tag, text).split("\n"))
    return "\n".join(lines).strip()


def clean_levels(levels: list[dict[str, Any]]) -> list[list[str]]:
    return [[clean_text(s) for s in level["stats"]] for level in levels]


def require_verified(entry: dict[str, Any], file: str, key: str) -> None:
    """Hand-checked reference entries carry `verified` (YYYY-MM-DD): `wfb check` lists
    them for re-check once the data changes after that date (G48)."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry.get("verified", ""))):
        raise RefreshError(f"reference/{file} {key}: `verified` (YYYY-MM-DD) is required")


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
