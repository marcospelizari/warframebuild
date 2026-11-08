"""gamedata/ schema (E12): one set of models for refresh validation and the app loader."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Order of DE `damagePerShot` (20 entries). 0-14 confirmed against WFCD attack data;
# 15-19 never set on a gun, refresh rejects a gun that uses them.
DAMAGE_TYPES = (
    "impact",
    "puncture",
    "slash",
    "heat",
    "cold",
    "electricity",
    "toxin",
    "blast",
    "radiation",
    "gas",
    "magnetic",
    "viral",
    "corrosive",
    "void",
    "tau",
)
UNVERIFIED_DAMAGE_SLOTS = range(15, 20)

DamageType = Literal[
    "impact",
    "puncture",
    "slash",
    "heat",
    "cold",
    "electricity",
    "toxin",
    "blast",
    "radiation",
    "gas",
    "magnetic",
    "viral",
    "corrosive",
    "void",
    "tau",
]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Falloff(Model):
    start: float | None = None
    end: float | None = None
    reduction: float | None = None


class Attack(Model):
    """One WFCD attack; chances as fractions (WFCD gives percent)."""

    name: str
    fire_rate: float | None
    critical_chance: float
    critical_multiplier: float
    status_chance: float
    shot_type: str | None
    damage: dict[DamageType, float]
    falloff: Falloff | None = None
    charge_time: float | None = None
    shot_speed: float | None = None


class Weapon(Model):
    unique_name: str
    slug: str
    name: str
    category: Literal["primary", "secondary"]
    weapon_type: str  # WFCD type: Rifle, Shotgun, Sniper, Bow, Pistol, ...
    trigger: str  # DE trigger
    damage: dict[DamageType, float]
    critical_chance: float
    critical_multiplier: float
    status_chance: float
    fire_rate: float
    multishot: float
    magazine_size: int | None
    reload_time: float
    mastery_req: int
    riven_disposition: float  # DE omegaAttenuation
    polarities: list[str]
    exilus_polarity: str | None
    attacks: list[Attack]
    texture_location: str | None


class ModSet(Model):
    unique_name: str
    num_upgrades: int
    stats: list[str]


class Mod(Model):
    unique_name: str
    name: str
    type: Literal["PRIMARY", "SECONDARY"]
    compat_name: str
    polarity: str
    rarity: str
    base_drain: int
    fusion_limit: int
    is_utility: bool
    mod_set: str | None
    level_stats: list[list[str]]  # per rank; cleaned free text, parsed in step 3


class Arcane(Model):
    unique_name: str
    name: str
    rarity: str | None
    level_stats: list[list[str]]


class Exclusion(Model):
    unique_name: str
    name: str
    reason: str


class SourceRecord(Model):
    path: str
    url: str
    retrieved: str
    sha256_16: str


class Meta(Model):
    schema_version: Literal[1] = 1
    dataset_hash: str
    game_update: str | None
    fetched: str  # newest download date of the DE/WFCD sources
    sources: list[SourceRecord]
    counts: dict[str, int]
    excluded_weapons: list[Exclusion]
    denied_mods: dict[str, int] = Field(description="denied gun mods per mod_filter rule")


class Join(Model):
    unique_name: str
    de_name: str
    wfcd_name: str


class ModsFile(Model):
    mods: list[Mod]
    sets: list[ModSet]
