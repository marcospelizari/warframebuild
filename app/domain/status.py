"""Status effects (G8): proc types beyond the damage types.

A damage-type proc is named by its `DamageType`. Crowd-control effects deal no damage;
some still count as a status type on the target (Condition Overload-style bonuses,
saved `Condition_Overload_(Mechanic)`: Knockdown, Lifted). The rules that use them
come in step 4c.
"""

from enum import StrEnum

from app.domain.effects import DamageType


class CrowdControl(StrEnum):
    KNOCKDOWN = "knockdown"
    LIFTED = "lifted"
    RAGDOLL = "ragdoll"
    STAGGER = "stagger"
    BIG_STAGGER = "big_stagger"
    BLIND = "blind"
    STUN = "stun"


# A guaranteed proc an attack applies regardless of status chance (saved Status_Effect,
# Forced Procs).
ForcedProc = DamageType | CrowdControl
