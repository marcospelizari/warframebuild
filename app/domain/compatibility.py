"""Whether a mod fits a gun (G56, G82; e.g. Split_Flights:47-56, Rifle_Mods:2)."""

from collections.abc import Collection


def fits(
    gun_classes: Collection[str],
    gun_tags: Collection[str] | None,
    mod_class: str | None,
    needs: Collection[str] | None,
    excludes: Collection[str] | None,
) -> bool:
    """`mod_class` (the class or gun the mod is for) is one of `gun_classes`; `needs`: the gun
    carries at least one of them (none: any gun); `excludes`: it carries none of them. Unknown
    data (None): only an untagged mod on a gun without tags, never an unknown mod."""
    if mod_class is None or needs is None or excludes is None or mod_class not in gun_classes:
        return False
    if gun_tags is None:
        return not needs and not excludes
    tags = set(gun_tags)
    return (not needs or not tags.isdisjoint(needs)) and tags.isdisjoint(excludes)
