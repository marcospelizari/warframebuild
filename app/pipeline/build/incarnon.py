"""Incarnon perks joined to guns by name (melee and unknown names drop out)."""

from collections import defaultdict

from app.gamedata.models import Incarnon, Perk, Weapon
from app.parse.incarnon import parse_perk
from app.pipeline.build.effects import Overrides
from app.pipeline.sources.wiki_incarnon import RawPerk


def build(raw: list[RawPerk], guns: list[Weapon], overrides: Overrides) -> list[Incarnon]:
    by_name = {w.name.casefold(): w for w in guns}
    perks: dict[str, list[Perk]] = defaultdict(list)
    for r in raw:
        gun = by_name.get(r.weapon.casefold())
        if gun is None:
            continue
        parsed, form = parse_perk(r.lines, r.notes)
        effects = overrides.apply(f"{gun.unique_name}#{r.name}", parsed)
        perks[gun.unique_name].append(Perk(tier=r.tier, name=r.name, form=form, effects=effects))
    names = {w.unique_name: w.name for w in guns}
    return [Incarnon(unique_name=u, name=names[u], perks=p) for u, p in sorted(perks.items())]
