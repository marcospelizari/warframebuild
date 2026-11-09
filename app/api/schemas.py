"""Request and response models of the JSON API (G18-G21). Fields are added, never renamed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.effects import DamageType
from app.gamedata.models import Category


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiError(ApiModel):
    code: str
    message: str
    field: str | None = None


class CalcRequest(ApiModel):
    weapon: str = Field(max_length=100, description="weapon slug")
    mods: list[str] = Field(
        default_factory=list, max_length=8, description="mod uniqueNames in slot order"
    )
    bonus_element: DamageType | None = None


class Source(ApiModel):
    kind: Literal["wiki", "reference", "de", "wfcd"]
    url: str


class Assumption(ApiModel):
    id: str
    text: str
    value: float | None = None
    source: Source | None = None


class WeaponRef(ApiModel):
    slug: str
    name: str
    category: Category
    weapon_type: str


class Slot(ApiModel):
    index: int
    mod: str | None  # uniqueName
    name: str | None
    rank: int | None
    polarity: str | None


class BonusElement(ApiModel):
    damage_type: DamageType
    share: float


class Arsenal(ApiModel):
    damage: dict[DamageType, float]  # per projectile
    total_damage: float
    critical_chance: float
    critical_multiplier: float
    status_chance: float
    multishot: float
    fire_rate: float
    magazine: float | None
    reload_time: float
    beam_ramp_start: float | None


class Dps(ApiModel):
    direct_burst: float
    direct_sustained: float


class Build(ApiModel):
    dataset_hash: str
    weapon: WeaponRef
    slots: list[Slot]
    bonus_element: BonusElement | None
    arsenal: Arsenal
    dps: Dps
    assumptions: list[Assumption]
