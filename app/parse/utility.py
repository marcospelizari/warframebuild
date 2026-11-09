"""Utility text: lines known to change no damage, which the parser may drop."""

import re

# Utility: lines known to change no damage, sustained DPS or enemy defences. Only these
# are dropped; any other line the parser cannot model stays in `unparsed` (R6), so an
# unknown combat rule can never pass as fully supported.
_UTILITY_STATS = (
    r"Punch Through|Blast (?:Radius|Range)|Projectile Speed|(?:Weapon )?Recoil|Accuracy|Zoom"
    r"|Beam Range|Movement Speed|Sprint Speed|Dodge Speed|Mobility|Ammo Maximum|Life Steal"
    r"|Heal Rate|Revive Speed|Combo Duration|Shield Recharge Delay|from Health Orbs"
    r"|Magazine Reloaded/s when Holstered|Aim Glide/Wall Latch Duration|Arcane Revive"
    r"|Energy Regen/s|Energy"
)
_UTILITY = re.compile(
    r"(?:and )?[+-]?\d{1,4}(?:\.\d{1,3})?(?:%|m|s)? (?:to )?(?:" + _UTILITY_STATS + r")"
    r"(?: (?:when|while) (?:Aiming|Aim Gliding|Airborne|Sliding|Crouching))?"
    r"(?: and [+-]?\d{1,4}%? (?:" + _UTILITY_STATS + r"))?(?: for \d{1,3}s)?\.?"
    r"(?: Stacks up to \d{1,3}x\.?)?"
    r"|Increase (?:Accuracy|(?:Weapon )?Recoil) by [+-]?\d{1,3}%\.?"
    r"|Improves the Blast Radius of weapons with Radial Attacks\.?"
    r"|Reveals target on Minimap for \+?\d{1,3}s\.?"
    r"|Reduces the chance an enemy will hear gunfire by \d{1,3}%\.?"
    r"|Converts (?:Primary|Secondary) ammo pickups to \d{1,3}% of Ammo Pick Up\.?",
    re.IGNORECASE,
)


def unmodelled(line: str) -> bool:
    return not _UTILITY.fullmatch(line)
