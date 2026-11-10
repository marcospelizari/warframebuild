"""Whether a mod fits a gun by its compatibility tags (G56; e.g. Split_Flights:47-56)."""

from collections.abc import Collection


def fits(
    gun: Collection[str] | None,
    needs: Collection[str] | None,
    excludes: Collection[str] | None,
) -> bool:
    """`needs`: the gun carries at least one of them (none: any gun); `excludes`: it carries
    none of them. Unknown tags (None): only an untagged mod on a gun, never an unknown mod."""
    if needs is None or excludes is None:
        return False
    if gun is None:
        return not needs and not excludes
    tags = set(gun)
    return (not needs or not tags.isdisjoint(needs)) and tags.isdisjoint(excludes)
