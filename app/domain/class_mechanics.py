"""Damage multipliers tied to a weapon class: sniper shot combo (saved Sniper_Rifle) and
beam ramp-up (saved Continuous_Weapon)."""

BEAM_RAMP_S = 0.6  # seconds from the start value to 100% (Continuous_Weapon:19)
BEAM_DECAY_DELAY_S = 0.8  # off target this long before the damage decays (:19)
BEAM_DECAY_S = 2.0  # from 100% back to the start value (:19)


def sniper_combo_multiplier(combo: int, minimum: int) -> float:
    """`1.5 + 0.5 x floor(log3(combo / minimum))` once combo >= minimum, else 1.

    Only while scoped; AoE and DoT neither build nor use it (Sniper_Rifle).
    """
    if minimum < 1 or combo < 0:
        raise ValueError("minimum combo >= 1, combo >= 0")
    if combo < minimum:
        return 1.0
    # Integer loop instead of log3 so exact powers of 3 never round down.
    steps, reach = 0, minimum * 3
    while combo >= reach:
        steps += 1
        reach *= 3
    return 1.5 + 0.5 * steps


def beam_ramp(start: float, seconds_on_target: float) -> float:
    """Damage share after `seconds_on_target` of hitting one target.

    The page gives the start value and 0.6 s to 100%, not the shape: linear is an
    assumption (stated in the build's assumptions).
    """
    if not 0 <= start <= 1 or seconds_on_target < 0:
        raise ValueError("start within 0..1, time >= 0")
    return start + (1 - start) * min(1.0, seconds_on_target / BEAM_RAMP_S)


def beam_level(start: float, level: float, on_target: float, off_target: float = 0.0) -> float:
    """Damage share after `off_target` seconds off the target, then `on_target` seconds on
    it, from `level`: it falls after 0.8 s off at the 2 s decay rate, then rises at the 0.6 s
    ramp rate (linear, as `beam_ramp`)."""
    span = 1 - start
    if span <= 0:
        return 1.0
    idle = max(0.0, off_target - BEAM_DECAY_DELAY_S)
    level = max(start, level - span * idle / BEAM_DECAY_S)
    return min(1.0, level + span * on_target / BEAM_RAMP_S)
