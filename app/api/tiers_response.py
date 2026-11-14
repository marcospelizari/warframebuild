"""A weapon class's stored Recommended builds -> its tier list (PLAN G92); no search."""

import math

from app.api.schemas.tiers import Tier, TierGun, TierList
from app.domain.combat import CAP_S
from app.gamedata.builds import Build
from app.gamedata.models import Category
from app.gamedata.release import Release
from app.gamedata.store import GameData
from app.optimize.candidates import unmodelled
from app.optimize.tiers import TIERS, tier


def tier_list(data: GameData, release: Release, category: Category) -> bytes:
    guns = sorted(
        (
            _gun(data, release.builds(w.slug).variants[0].recommended, w.slug)
            for w in data.weapons
            if w.category == category
        ),
        key=lambda g: (g.kill_time, g.slug),
    )
    fastest = guns[0].kill_time if guns else 0.0
    by_tier: dict[str, list[TierGun]] = {name: [] for name, _ in TIERS}
    for g in guns:
        by_tier[tier(g.kill_time / fastest)].append(g)
    out = TierList(
        release=release.id,
        category=category,
        fastest=fastest,
        level=max(e.level for e in data.enemies),
        factions=len({e.faction for e in data.enemies}),
        tiers=[
            Tier(name=name, up_to=None if math.isinf(top) else top, guns=by_tier[name])
            for name, top in TIERS
        ],
    )
    return out.model_dump_json().encode()


def _gun(data: GameData, rec: Build, slug: str) -> TierGun:
    weapon = data.weapon_by_slug[slug]
    return TierGun(
        slug=slug,
        kill_time=1 / rec.score,
        capped=any(cost > CAP_S for cost in rec.costs.values()),
        partial=any(u.kind == "perk" for u in unmodelled(data, weapon)),
    )
