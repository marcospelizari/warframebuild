"""gamedata/ schema: the representative enemies and their faction damage modifiers."""

from typing import Annotated

from pydantic import Field

from app.domain.effects import DamageType, Faction
from app.gamedata.models import Model, NonNegative, Positive


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
