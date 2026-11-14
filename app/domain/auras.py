"""Aura mods that change a gun or its target (G91): one aura, the player's own."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.effects import Effect

Kept = Annotated[float, Field(gt=0, le=1)]


class Aura(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    unique_name: str  # DE uniqueName
    name: str
    weapon_types: list[str] | None  # WFCD types it applies to; None = every gun
    effect: Effect | None = None  # on the gun, after its mods
    armor_kept: Kept = 1.0  # enemy armor left; multiplies with status strips
    shield_kept: Kept = 1.0  # enemy shields left
    source: list[str]  # saved page and line

    @model_validator(mode="after")
    def _one_change(self) -> "Aura":
        enemy = self.armor_kept < 1 or self.shield_kept < 1
        if (self.effect is not None) == enemy:
            raise ValueError(f"{self.name}: a gun effect or an enemy change, exactly one")
        return self

    def fits(self, weapon_type: str) -> bool:
        return self.weapon_types is None or weapon_type in self.weapon_types


class Auras(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    auras: list[Aura]

    def for_weapon(self, weapon_type: str) -> list[Aura]:
        return [a for a in self.auras if a.fits(weapon_type)]
