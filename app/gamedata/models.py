"""gamedata/ schema (E12): one set of models for refresh validation and the app loader."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.direct_bonus import DirectBonus
from app.domain.effects import DamageType, Effect, Faction, Support
from app.domain.polarity import Polarity
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
    # Wiki module ExtraHeadshotDmg: -2 = heads hit at 1x, no weak-point bonuses; > 0 = extra
    # headshot factor (Cernos Prime 0.5 -> x1.5; saved Enemy_Body_Parts, Notes).
    extra_headshot: float | None = None
    # Beam damage at the start of the ramp-up (saved Continuous_Weapon) when this attack is a
    # beam: its own Held trigger, or the gun's when the attack has none; None = not a beam.
    beam_ramp_start: Fraction | None = None
    # How a Galvanized-style bonus joins this attack's damage (G56): default from the shot
    # type, exceptions from reference/galvanized_behaviour.json.
    direct_bonus: DirectBonus = DirectBonus.ADDING


class BonusElement(Model):
    """Kuva/Tenet/Coda progenitor bonus: one of `elements`, up to `max_share` of base damage."""

    elements: list[DamageType]
    max_share: Fraction
    page: str  # saved wiki page title


class Effects(Model):
    """Parsed max-rank effects (step 3) and how far the calculator supports them (R6)."""

    support: Support
    effects: list[Effect]
    unparsed: list[str]  # damage-related text not modelled; empty when support is full
    requires_trigger: str | None = None  # DE trigger the entry is limited to (SEMI)
    note: str | None = None  # from reference/overrides.json


class Headshot(Model):
    """One form aimed at heads (reference/headshot.json, R5); other forms hit the body."""

    form: Literal["normal", "incarnon"]
    reason: str
    source: str | None  # canonical wiki page title; None = project decision, see `reason`
    flat: bool = False  # heads at 1x, no weak-point bonuses (reference/headshot.json)
    # The weapon's ExtraHeadshotDmg multiplies on top instead of joining the headshot bonuses.
    separate_extra: bool = False


class ReferenceHead(Model):
    """The head /calc scores headshot forms on until enemies exist (step 8)."""

    name: str
    multiplier: Positive
    critical: bool  # critical-headshot flag
    source: str  # canonical wiki page title


class EnemyHead(Model):
    """The headshot spot headshot forms aim at (saved Enemy_Body_Parts)."""

    part: str
    multiplier: Positive
    critical: bool  # critical-headshot flag


class Enemy(Model):
    """A representative enemy at the scored level (reference/enemies.json, R1)."""

    unique_name: str
    name: str
    faction: str  # key of FactionModifiers.faction
    level: Annotated[int, Field(ge=1)]
    health: Positive
    shield: NonNegative
    armor: NonNegative
    head: EnemyHead | None  # None: no headshot spot, the body is hit
    bane: Faction | None  # faction damage mods that apply (Bane of X); None = none
    toxin_bypasses_shield: bool = True
    source: str  # canonical wiki page title of the enemy module


class FactionModifiers(Model):
    """Damage type modifiers of one faction (saved <Type>_Damage pages); unlisted types 1."""

    faction: str
    modifiers: dict[DamageType, Positive]


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
    polarities: list[Polarity]  # built-in regular slots, positions unknown
    exilus_polarity: Polarity | None
    max_rank: int  # DE maxLevelCap or 30; capacity = 2 x max rank with a catalyst
    attacks: list[Attack]
    texture_location: str | None
    # export-plus compatibilityTags (e.g. PROJECTILE, AOE), stored as given; their meaning
    # for mod eligibility is decided in step 8. None = weapon not in the saved export-plus.
    compatibility_tags: list[str] | None
    # Weapon class paths a mod's `compat` may name: the gun, its export-plus parent chain,
    # the classes reference/weapon_classes.json gives its root (G82).
    mod_classes: list[str] = Field(default_factory=list)
    sniper_combo_min: Annotated[int, Field(ge=1)] | None  # saved Sniper_Rifle, wiki module
    no_reload: bool  # shots come straight from the ammo pool (Epitaph), fire_overrides.json
    # Reload replaces one shot interval (Vectis; saved Calculation, Average Sustained DPS).
    reload_replaces_shot: bool
    # Beam damage at the start of the ramp-up (saved Continuous_Weapon); HELD trigger only.
    beam_ramp_start: Fraction | None
    bonus_element: BonusElement | None  # saved <Family>_Weapons pages
    headshot: list[Headshot] = []  # forms aimed at heads (reference/headshot.json)
    # Highest zoom level's bonus (wiki module Zoom, saved Sniper_Rifle); applies while aiming.
    zoom: Effects | None = None


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
    polarity: Polarity
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
    compat_class: str | None  # export-plus `compat`; None = missing in export-plus


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
    schema_version: Literal[21] = 21
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
