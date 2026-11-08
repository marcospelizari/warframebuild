"""Stat text -> effects for one entry (Q8/R2).

Input: DE stat strings and description already reduced to plain text by the
pipeline. Every line is either modelled, on the known utility list, or kept in
`unparsed`, so an unknown rule never passes as full support (R6).
"""

from app.domain.effects import Effect, Parsed
from app.parse.groups import dedupe, groups, sentences, spread_timing
from app.parse.lines import REQUIRES, TRIGGER_NAMES, Context, line_effects
from app.parse.utility import unmodelled


def parse(stats: list[str], description: str = "") -> Parsed:
    """Effects of one entry at one rank: its stat strings plus its description."""
    effects: list[Effect] = []
    unparsed: list[str] = []
    requires: str | None = None
    for group in groups(dedupe(stats)):
        group_effects: list[Effect] = []
        for line in group.lines:
            if group.trigger is None:
                # "On shotgun kill within 5m of target:" -> keep the text, model nothing.
                if unmodelled(line):
                    unparsed.append(f"{group.head}: {line}")
                continue
            found = line_effects(line, group)
            if found is None:
                if unmodelled(line):
                    unparsed.append(line)
            else:
                group_effects.extend(found)
        effects.extend(spread_timing(group_effects, group.lines))
    for line in sentences(description):
        req = REQUIRES.fullmatch(line)
        if req:
            requires = TRIGGER_NAMES[req["trigger"].lower()]
            continue
        found = line_effects(line, Context())
        if found is not None:
            effects.extend(found)
        elif unmodelled(line):
            unparsed.append(line)
    return Parsed(effects=effects, unparsed=unparsed, requires_trigger=requires)
