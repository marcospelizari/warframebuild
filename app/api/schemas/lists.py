"""`GET /api/weapons` and `GET /api/mods`: the home list and the editor's picker (G19, G20)."""

from typing import Literal

from app.api.schemas.base import ApiModel
from app.api.schemas.build import WeaponRef
from app.domain.effects import Support
from app.gamedata.models import Category


class WeaponItem(ApiModel):
    slug: str
    name: str
    category: Category
    weapon_type: str
    incarnon: bool
    progenitor: bool  # Kuva/Tenet/Coda bonus element
    mastery: int  # mastery rank needed
    image: str | None  # /img URL; None when the icon is not cached
    good_primer: bool = False  # G49: a top Primer score with many status types


class ExcludedWeapon(ApiModel):
    name: str
    reason: str


class WeaponList(ApiModel):
    dataset_hash: str
    weapons: list[WeaponItem]
    # Guns the tool does not build, with why (G19); filtered by `q` only (no category stored).
    excluded: list[ExcludedWeapon]


class ModItem(ApiModel):
    unique_name: str
    name: str
    polarity: str
    rarity: str
    rank: int  # max rank (builds use max rank, Q33)
    drain: int  # at max rank, before polarity
    exilus: bool  # fits the exilus slot
    family: str | None  # mods sharing a family clash (V4)
    mod_set: str | None
    support: Support  # R6: how fully its effects are modelled
    stats: list[str]  # max-rank text
    description: str
    image: str | None  # /img URL; None when the picture is not cached
    compatible: bool
    reason: str | None  # why it does not fit this gun


class ArcaneItem(ApiModel):
    unique_name: str
    name: str
    rarity: str | None
    support: Support
    stats: list[str]  # max-rank text
    image: str | None  # /img URL; None when the picture is not cached
    compatible: bool
    reason: str | None


class PerkItem(ApiModel):
    name: str
    form: Literal["both", "normal", "incarnon"]
    support: Support


class PerkTier(ApiModel):
    tier: int
    options: list[PerkItem]  # one may be chosen per tier


class ModList(ApiModel):
    """Everything the editor's picker offers for one gun (F7, G20)."""

    dataset_hash: str
    weapon: WeaponRef
    mods: list[ModItem]  # every mod of the gun's category
    arcanes: list[ArcaneItem]  # every arcane of the gun's category
    perks: list[PerkTier]  # empty for guns without Incarnon perks
