"""Stat text -> stored Effects: the step 3 parser plus hand-checked overrides (R6)."""

from typing import Any

from pydantic import ValidationError

from app.domain.effects import Effect, Parsed, Support
from app.gamedata.models import Effects
from app.parse.effects import parse
from app.pipeline.build.inputs import require_verified
from app.pipeline.errors import RefreshError


class Overrides:
    """reference/overrides.json: per uniqueName, `effects` replace the parsed ones;
    `support` / `note` adjust the status. Every entry must be used by the refresh."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._entries: dict[str, dict[str, Any]] = data.get("entries", {})
        self._used: set[str] = set()

    def effects(self, unique_name: str, stats: list[str], description: str = "") -> Effects:
        parsed = parse(stats, description)
        entry = self._entries.get(unique_name)
        if entry is None:
            return _stored(parsed)
        self._used.add(unique_name)
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

    def check_all_used(self) -> None:
        unused = sorted(self._entries.keys() - self._used)
        if unused:
            raise RefreshError(
                f"reference/overrides.json entries match no mod, arcane or set: {unused}"
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
