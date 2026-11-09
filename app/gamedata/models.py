"""gamedata/ schema (E12): one set of models for refresh validation and the app loader."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.direct_bonus import DirectBonus
from app.domain.effects import DamageType, Effect, Support
from app.domain.status import ForcedProc


class Category(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


NonNegative = Annotated[float, Field(ge=0)]
Fraction = Annotated[float, Field(ge=0, le=1)]
Positive = Annotated[float, Field(gt=0)]
Damage = dict[DamageType, NonNegative]
# ISO date (YYYY-MM-DD); compared as text.
IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class Model(BaseModel):
    # No NaN/inf anywhere: they would poison every later calculation and ranking.
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Falloff(Model):
    start: NonNegative | None = None
    end: NonNegative | None = None
    reduction: NonNegative | None = None


class Attack(Model):
    """One WFCD attack; chances as fractions (WFCD gives percent). Chances may exceed 1."""

    name: str
    fire_rate: Positive | None
    critical_chance: NonNegative
    critical_multiplier: NonNegative
    status_chance: NonNegative
    shot_type: str | None
    damage: Damage
    falloff: Falloff | None = None
    charge_time: NonNegative | None = None
    shot_speed: NonNegative | None = None
    # From the wiki weapon data modules; None = weapon not in the saved modules.
    forced_procs: list[ForcedProc] | None = None
    burst_count: Annotated[int, Field(ge=1)] | None = None
    burst_delay: NonNegative | None = None
    ammo_cost: NonNegative | None = None  # ammo per shot, 0 = none; None = not in the module
    multishot: Positive | None = None  # wiki module; None = not listed
    # How a Galvanized-style bonus joins this attack's damage (G56): default from the shot
    # type, exceptions from reference/galvanized_behaviour.json.
    direct_bonus: DirectBonus = DirectBonus.ADDING


class BonusElement(Model):
    """Kuva/Tenet/Coda progenitor bonus: one of `elements`, up to `max_share` of base damage."""

    elements: list[DamageType]
    max_share: Fraction
    page: str  # saved wiki page title


class Weapon(Model):
    unique_name: str
    slug: str
    name: str
    category: Category
    weapon_type: str  # WFCD type: Rifle, Shotgun, Sniper, Bow, Pistol, ...
    trigger: str  # DE trigger
    damage: Damage
    critical_chance: NonNegative
    critical_multiplier: Annotated[float, Field(ge=1)]
    status_chance: NonNegative
    # None = no delay between shots: the charge time alone sets the rate (Lanka; wiki
    # module FireRate = math.huge, saved Fire_Rate). Only on charge weapons.
    fire_rate: Positive | None
    multishot: Positive
    magazine_size: Annotated[int, Field(ge=0)] | None  # None = no magazine (verified)
    reload_time: NonNegative
    mastery_req: Annotated[int, Field(ge=0)]
    riven_disposition: NonNegative  # DE omegaAttenuation
    polarities: list[str]
    exilus_polarity: str | None
    attacks: list[Attack]
    texture_location: str | None
    # export-plus compatibilityTags (e.g. PROJECTILE, AOE), stored as given; their meaning
    # for mod eligibility is decided in step 8. None = weapon not in the saved export-plus.
    compatibility_tags: list[str] | None
    sniper_combo_min: Annotated[int, Field(ge=1)] | None  # saved Sniper_Rifle, wiki module
    no_reload: bool  # shots come straight from the ammo pool (Epitaph), fire_overrides.json
    # Reload replaces one shot interval (Vectis; saved Calculation, Average Sustained DPS).
    reload_replaces_shot: bool
    # Beam damage at the start of the ramp-up (saved Continuous_Weapon); HELD trigger only.
    beam_ramp_start: Fraction | None
    bonus_element: BonusElement | None  # saved <Family>_Weapons pages


class Effects(Model):
    """Parsed max-rank effects (step 3) and how far the calculator supports them (R6)."""

    support: Support
    effects: list[Effect]
    unparsed: list[str]  # damage-related text not modelled; empty when support is full
    requires_trigger: str | None = None  # DE trigger the entry is limited to (SEMI)
    note: str | None = None  # from reference/overrides.json


class ModSet(Model):
    unique_name: str
    num_upgrades: Annotated[int, Field(ge=1)]
    stats: list[str]
    bonuses: list[Effects]  # index = equipped pieces - 1


class Mod(Model):
    unique_name: str
    name: str
    category: Category
    compat_name: str
    polarity: str
    rarity: str
    base_drain: int  # negative for some mods that add capacity
    fusion_limit: Annotated[int, Field(ge=0)]
    is_utility: bool  # DE flag
    exilus: bool  # fits the exilus slot: DE flag or reference/exilus.json (Q30)
    mod_set: str | None
    family: str | None  # V4: mods sharing a family cannot be equipped together
    description: str  # DE rules text not in the stats ("Fire Rate cannot be modified."), or ""
    level_stats: list[list[str]]  # per rank; cleaned free text
    effects: Effects  # max rank
    # export-plus tags a weapon must / must not carry (Sinister Reach needs BEAM), stored as
    # given for step 8. None = mod not in the saved export-plus.
    compatibility_tags: list[str] | None
    incompatibility_tags: list[str] | None


class Arcane(Model):
    unique_name: str
    name: str
    category: Category
    weapon_type: str | None  # slot limited to this WFCD weapon_type (Shotgun, Bow)
    rarity: str | None
    level_stats: list[list[str]]
    effects: Effects  # max rank


class Perk(Model):
    tier: Annotated[int, Field(ge=2, le=5)]
    name: str
    form: Literal["both", "normal", "incarnon"]
    effects: Effects


class Incarnon(Model):
    """Evolution perks of one gun (saved Incarnon_Evolutions / native weapon pages)."""

    unique_name: str
    name: str
    attacks: list[str]  # Incarnon Form shot parts (reference/main_attack.json)
    no_multishot: list[str] = []  # parts that ignore Multishot bonuses
    note: str | None = None  # modelling limit shown in /calc assumptions
    perks: list[Perk]


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
    schema_version: Literal[14] = 14
    dataset_hash: str
    # Newest content update named in the data (WFCD `introduced`); a label only:
    # DE publishes no update name, and hotfixes without new items do not change it.
    game_update: str | None
    fetched: IsoDate  # newest download date of the DE/WFCD sources
    changed_on: IsoDate  # first refresh that produced this dataset_hash; staleness reference
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
