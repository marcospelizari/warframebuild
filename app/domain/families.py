"""Mod families (V4): one rule for the optimizer and /calc."""

from collections.abc import Iterable


def clashes(mods: Iterable[tuple[str, str | None]]) -> list[tuple[str, str]]:
    """Pairs of mods (by uniqueName) that share a family; `mods` = (uniqueName, family)."""
    seen: dict[str, str] = {}
    out = []
    for unique_name, family in mods:
        if family is None:
            continue
        if family in seen:
            out.append((seen[family], unique_name))
        else:
            seen[family] = unique_name
    return out
