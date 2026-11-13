"""Stat text -> stored Effects: the step 3 parser plus hand-checked overrides (R6)."""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.domain.effects import Effect, Parsed, Support
from app.gamedata.models import Effects
from app.parse.effects import parse
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError


@dataclass(frozen=True)
class SwitchedOff:
    """An override whose entry text changed since it was written (U2): not applied."""

    key: str
    written_for: list[str]
    now: list[str]


class Overrides:
    """reference/overrides.json: per uniqueName, `effects` replace the parsed ones;
    `support` / `note` adjust the status. Every entry must be used by the refresh and
    name the text it was written for; when that text changed, the entry is switched off
    and the parsed effects stand (G90 U2)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._entries: dict[str, dict[str, Any]] = data.get("entries", {})
        self._used: set[str] = set()
        self._missing_text: dict[str, list[str]] = {}
        self.switched_off: list[SwitchedOff] = []

    def effects(self, unique_name: str, stats: list[str], description: str = "") -> Effects:
        text = ([description] if description else []) + list(stats)
        return self.apply(unique_name, parse(stats, description), text)

    def apply(self, unique_name: str, parsed: Parsed, text: list[str]) -> Effects:
        """Parsed effects, replaced or adjusted by the entry for `unique_name` if any."""
        entry = self._entries.get(unique_name)
        if entry is None:
            return _stored(parsed)
        self._used.add(unique_name)
        if "text" not in entry:
            self._missing_text[unique_name] = text
        elif entry["text"] != text:
            self.switched_off.append(SwitchedOff(unique_name, list(entry["text"]), text))
            return _stored(parsed)
        try:
            require_verified(entry, "overrides.json", unique_name)
            effects = [Effect(**e) for e in entry["effects"]] if "effects" in entry else None
            default = Support.FULL if effects is not None else parsed.support
            support = Support(entry.get("support", default))
            if effects is not None:
                unparsed = entry.get("unparsed", [])
            else:
                # `support: full` alone = reviewed: the leftover text changes no damage.
                unparsed = [] if support == Support.FULL else parsed.unparsed
            return Effects(
                support=support,
                effects=effects if effects is not None else parsed.effects,
                unparsed=unparsed,
                requires_trigger=entry.get("requires_trigger", parsed.requires_trigger),
                note=entry.get("note"),
            )
        except (ValidationError, ValueError, KeyError) as error:
            raise RefreshError(f"reference/overrides.json {unique_name}: {error}") from error

    def check_all_used(self, excluded: set[str]) -> None:
        """Entries of `excluded` guns or arcanes (`<uid>` or `<uid>#<perk>`) wait unused."""
        unused = sorted(
            k for k in self._entries.keys() - self._used if k.split("#", 1)[0] not in excluded
        )
        if unused:
            raise RefreshError(
                f"reference/overrides.json entries match no mod, arcane or perk: {unused}"
            )
        if self._missing_text:
            listed = json.dumps(self._missing_text, indent=1, ensure_ascii=False)
            raise RefreshError(
                "reference/overrides.json entries without `text` (the text they were written "
                f"for; check the values against it, then add it):\n{listed}"
            )


def set_bonuses(stats: list[str]) -> list[Effects]:
    """One Effects per equipped piece count (sets are not overridden)."""
    return [_stored(parse([text])) for text in stats]


def _stored(parsed: Parsed) -> Effects:
    return Effects(
        support=parsed.support,
        effects=parsed.effects,
        unparsed=parsed.unparsed,
        requires_trigger=parsed.requires_trigger,
    )
