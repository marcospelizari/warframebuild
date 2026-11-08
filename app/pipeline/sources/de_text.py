"""DE stat-text markup -> plain text (untrusted: kept as plain text only)."""

import re
from typing import Any

from app.pipeline.errors import RefreshError
from app.pipeline.sources.de_export import DAMAGE_TAGS, DAMAGE_WORDS

_TAG = re.compile(r"<([A-Z0-9_]+)>")
_SPACES = re.compile(r"[ \t]{2,}")
_WORD = re.compile(r"[A-Za-z]+")


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
                "in app/pipeline/sources/de_export.py"
            )
        word = damage.value.capitalize()
        following = _WORD.findall(text, match.end())[:2]
        return "" if {word, *DAMAGE_WORDS.get(damage, ())} & set(following) else f"{word} "

    lines = (_SPACES.sub(" ", line).strip() for line in _TAG.sub(tag, text).split("\n"))
    return "\n".join(lines).strip()


def clean_levels(levels: list[dict[str, Any]]) -> list[list[str]]:
    return [[clean_text(s) for s in level["stats"]] for level in levels]
