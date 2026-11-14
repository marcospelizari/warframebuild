"""Tier list (PLAN G92): a class's guns tiered by their Recommended kill time, as a ratio to
the class's fastest gun."""

import math

# Highest ratio to the fastest gun for each tier, best first; F takes the rest. Each tier
# doubles the one above: kill times span about 500x (release db2e44fbdacf44d0: primaries
# 2/13/15/43/52/48/23 from S to F, secondaries 4/5/11/20/45/41/22; G92).
TIERS: tuple[tuple[str, float], ...] = (
    ("S", 2.0),
    ("A", 4.0),
    ("B", 8.0),
    ("C", 16.0),
    ("D", 32.0),
    ("E", 64.0),
    ("F", math.inf),
)


def tier(ratio: float) -> str:
    """The tier of a gun whose kill time is `ratio` times the fastest gun's (ratio >= 1)."""
    return next(name for name, top in TIERS if ratio <= top)
