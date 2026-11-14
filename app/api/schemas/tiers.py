"""`GET /api/tiers/{category}`: the tier list of one weapon class (PLAN G92)."""

from app.api.schemas.base import ApiModel
from app.gamedata.models import Category


class TierGun(ApiModel):
    slug: str  # name and picture come from /api/weapons
    kill_time: float  # s: the Recommended build's average kill (1 / its score)
    capped: bool  # an enemy outlived the 10 s cap: the rank is less certain
    partial: bool  # one of its Incarnon evolutions is not fully calculated: may rank higher


class Tier(ApiModel):
    name: str  # S, A, … F
    up_to: float | None  # highest kill-time ratio to the fastest gun; None: no limit (F)
    guns: list[TierGun]  # fastest first; may be empty


class TierList(ApiModel):
    release: str
    category: Category
    fastest: float  # s: the class's fastest Recommended kill
    level: int  # the scored enemies' level
    factions: int  # factions the scored enemies come from
    tiers: list[Tier]  # S first
