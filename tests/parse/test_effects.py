"""Stat text -> effects (step 3). Text is real DE max-rank text, already plain."""

from app.domain.effects import (
    DamageType,
    Effect,
    Faction,
    FireRateBoost,
    Operation,
    Stat,
    Support,
    Trigger,
)
from app.parse.effects import parse


def _one(stats: list[str], description: str = "") -> Effect:
    parsed = parse(stats, description)
    assert parsed.support == Support.FULL and len(parsed.effects) == 1, parsed
    return parsed.effects[0]


def test_serration() -> None:
    assert _one(["+165% Damage"]) == Effect(stat=Stat.DAMAGE, value=1.65)


def test_negative_value_keeps_its_sign() -> None:
    parsed = parse(["+60% Critical Damage", "-15% Damage"])
    assert [e.value for e in parsed.effects] == [0.6, -0.15]


def test_element_mod() -> None:
    effect = _one(["+90% Heat"])
    assert (effect.stat, effect.damage_type) == (Stat.ELEMENT, DamageType.HEAT)


def test_physical_mod_is_not_an_element() -> None:
    """Review: Bore scales the base's own Puncture only (saved Calculating_Bonuses)."""
    effect = _one(["+120% Puncture"])
    assert (effect.stat, effect.damage_type) == (Stat.PHYSICAL, DamageType.PUNCTURE)


def test_physical_and_element_types_cannot_be_swapped() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="physical"):
        Effect(stat=Stat.ELEMENT, value=1, damage_type=DamageType.SLASH)
    with pytest.raises(ValidationError, match="physical"):
        Effect(stat=Stat.PHYSICAL, value=1, damage_type=DamageType.HEAT)


def test_unknown_faction_is_unparsed() -> None:
    """Review: a new faction name never passes as full support."""
    parsed = parse(["x1.55 Damage to Scaldra"])
    assert parsed.support == Support.UNSUPPORTED


def test_galvanized_chamber_has_a_kill_stack() -> None:
    parsed = parse(["+80% Multishot", "On Kill:\n+30% Multishot for 20s. Stacks up to 5x."])
    assert parsed.support == Support.FULL
    passive, stack = parsed.effects
    assert passive == Effect(stat=Stat.MULTISHOT, value=0.8)
    assert (stack.trigger, stack.value, stack.duration_s, stack.max_stacks) == (
        Trigger.ON_KILL,
        0.3,
        20.0,
        5,
    )


def test_primary_merciless_passive_reload_counted_once() -> None:
    """Arcanes repeat passive lines: inside the first string and alone after it."""
    parsed = parse(
        [
            "On Kill:\n+30% Damage for 4s. Stacks up to 12x.\n+30% Reload Speed",
            "+30% Reload Speed",
        ]
    )
    damage, reload = parsed.effects
    assert (damage.trigger, damage.max_stacks) == (Trigger.ON_KILL, 12)
    assert reload == Effect(stat=Stat.RELOAD_SPEED, value=0.3)


def test_stack_cap_in_percent_becomes_a_count() -> None:
    """Cascadia Flare: "Stacks up to 480%" at 12% per stack = 40 stacks."""
    effect = _one(["On Heat Status Effect:\n+12% Damage for 10s. Stacks up to 480%."])
    assert (effect.trigger, effect.trigger_damage_type, effect.max_stacks) == (
        Trigger.ON_STATUS,
        DamageType.HEAT,
        40,
    )


def test_percent_stack_cap_is_per_effect() -> None:
    """Review 3d: "Stacks up to 480%" on a group gives each effect its own count."""
    parsed = parse(
        ["On Kill:\n+12% Damage and +24% Multishot for 10s.\n+1% Fire Rate. Stacks up to 480%."]
    )
    assert {e.stat: e.max_stacks for e in parsed.effects} == {
        Stat.DAMAGE: 40,
        Stat.MULTISHOT: 20,
        Stat.FIRE_RATE: 480,
    }


def test_one_value_for_several_stats() -> None:
    parsed = parse(
        ["On Weak Point Kill:\n+150% Viral and Magnetic Damage and Status Chance for 15s"]
    )
    assert [(e.stat, e.damage_type) for e in parsed.effects] == [
        (Stat.ELEMENT, DamageType.VIRAL),
        (Stat.ELEMENT, DamageType.MAGNETIC),
        (Stat.STATUS_CHANCE, None),
    ]
    assert {e.value for e in parsed.effects} == {1.5}


def test_two_values_share_duration_and_stacks() -> None:
    parsed = parse(
        [
            "On Cold Status Effect:\n+3% Critical Damage and +2.25% Multishot for 12s. "
            "Stacks up to 40x."
        ]
    )
    assert [(e.stat, e.value, e.duration_s, e.max_stacks) for e in parsed.effects] == [
        (Stat.CRITICAL_DAMAGE, 0.03, 12.0, 40),
        (Stat.MULTISHOT, 0.0225, 12.0, 40),
    ]


def test_bow_value_doubles() -> None:
    effect = _one(["+90% Fire Rate (x2 for Bows)"])
    assert (effect.value, effect.class_values) == (0.9, {"Bow": 1.8})


def test_aiming_buff() -> None:
    effect = _one(["On Weak Point Hit:\n+135% Critical Chance when Aiming for 9s"])
    assert (effect.trigger, effect.while_aiming, effect.duration_s) == (
        Trigger.ON_WEAK_POINT_HIT,
        True,
        9.0,
    )


def test_faction_mod_multiplies() -> None:
    effect = _one(["x1.55 Damage to The Murmur"])
    assert (effect.stat, effect.operation, effect.value, effect.faction) == (
        Stat.FACTION_DAMAGE,
        Operation.MULTIPLY,
        1.55,
        Faction.MURMUR,
    )


def test_hunter_munitions_forced_slash_on_crit() -> None:
    effect = _one(["+30% chance to apply Slash on Critical"])
    assert (effect.stat, effect.damage_type, effect.trigger, effect.operation) == (
        Stat.FORCED_PROC,
        DamageType.SLASH,
        Trigger.ON_CRIT,
        Operation.ADD,
    )


def test_pistol_acuity_locks_multishot() -> None:
    parsed = parse(
        [
            "+350% Weak Point Damage",
            "+350% Weak Point Critical Chance. Multishot cannot be modified.",
        ]
    )
    assert [(e.stat, e.operation) for e in parsed.effects] == [
        (Stat.WEAK_POINT_DAMAGE, Operation.STACKING_MULTIPLY),
        (Stat.WEAK_POINT_CRITICAL_CHANCE, Operation.STACKING_MULTIPLY),
        (Stat.MULTISHOT, Operation.LOCK),
    ]


def test_semi_cannonade_rules_from_description() -> None:
    parsed = parse(
        ["+240% Damage", "+1.5 Punch Through"],
        "Only compatible with Semi-Auto Trigger. Fire Rate cannot be modified.",
    )
    assert parsed.support == Support.FULL
    assert parsed.requires_trigger == "SEMI"
    assert [(e.stat, e.operation) for e in parsed.effects] == [
        (Stat.DAMAGE, Operation.STACKING_MULTIPLY),
        (Stat.FIRE_RATE, Operation.LOCK),
    ]


def test_first_shot_damage_is_a_separate_multiplier() -> None:
    """Review R13: saved Calculating_Bonuses lists Primed Chamber as "2x damage on first
    shot" among multiplicative bonuses, so it never adds to Serration."""
    effect = _one(["+100% Damage on first shot in Magazine"])
    assert (effect.stat, effect.value, effect.operation, effect.trigger) == (
        Stat.DAMAGE,
        2.0,
        Operation.MULTIPLY,
        Trigger.FIRST_SHOT,
    )


def test_damage_while_aiming_is_a_separate_multiplier() -> None:
    """Same page: Lasting Purity "1.6x damage on aiming"."""
    parsed = parse(["+60% Damage when Aiming", "+1 'Purity'"])
    assert [(e.value, e.operation, e.while_aiming) for e in parsed.effects] == [
        (1.6, Operation.MULTIPLY, True)
    ]
    assert parsed.support == Support.PARTIAL  # syndicate proc not modelled


def test_vigilante_set_bonus() -> None:
    effect = _one(["30% chance to enhance Critical Hits from Primary Weapons."])
    assert (effect.stat, effect.value) == (Stat.CRIT_TIER_UPGRADE, 0.3)


def test_utility_lines_are_ignored() -> None:
    parsed = parse(
        [
            "-60% Weapon Recoil",
            "+44% Blast Range",
            "+2.1 Punch Through",
            "On Kill:\n+30% Projectile Speed and +30% Beam Range for 10s. Stacks up to 2x.",
        ]
    )
    assert parsed.support == Support.FULL and parsed.effects == [] and not parsed.damage_related


def test_unknown_rule_without_damage_words_is_kept() -> None:
    """Review R14: Jahu Canticle strips armor; only known utility text is dropped."""
    parsed = parse(
        [
            "Killing enemies reduces the Armor and Shields of other enemies within Affinity "
            "Range by 5%."
        ]
    )
    assert parsed.support == Support.UNSUPPORTED and parsed.damage_related


def test_restriction_text_is_kept() -> None:
    """Review R14: Split Flights' "(Non-AOE Bows)" must not vanish."""
    parsed = parse(
        ["On Hit:\n+100% Multishot\n-180% Accuracy for 2s. Stacks up to 4x.\n(Non-AOE Bows)"]
    )
    assert parsed.support == Support.PARTIAL
    assert parsed.unparsed == ["(Non-AOE Bows)"]
    assert parsed.effects[0].max_stacks == 4


def test_unmodelled_condition_is_never_always_on() -> None:
    """Shotgun Vendetta: an unknown header keeps its lines out of the effects."""
    parsed = parse(
        ["On shotgun kill within 5m of target:\n+180% Multishot and +75% Reload Speed for 15s."]
    )
    assert parsed.support == Support.UNSUPPORTED and parsed.effects == []
    assert parsed.unparsed == [
        "On shotgun kill within 5m of target: +180% Multishot and +75% Reload Speed for 15s."
    ]


def test_free_text_damage_effect_is_unsupported() -> None:
    parsed = parse(["Enemies hit are pulled toward the impact point and take 20% more damage"])
    assert parsed.support == Support.UNSUPPORTED and parsed.damage_related


def test_internal_bleeding_forced_slash_on_impact_proc() -> None:
    """Saved Internal_Bleeding: 35% Slash on an Impact proc, x2 below 2.5 fire rate."""
    parsed = parse(
        [
            "Impact Status Effects have 35% chance to apply a Slash Status Effect "
            "(x2 when Fire Rate is below 2.5)"
        ]
    )
    assert parsed.support == Support.FULL
    (effect,) = parsed.effects
    assert effect.stat == Stat.FORCED_PROC and effect.damage_type == DamageType.SLASH
    assert effect.trigger == Trigger.ON_STATUS
    assert effect.trigger_damage_type == DamageType.IMPACT
    assert effect.value == 0.35
    assert effect.fire_rate_boost == FireRateBoost(below=2.5, factor=2)


def test_long_input_stays_fast() -> None:
    """S5: bounded regexes, no catastrophic backtracking on hostile text."""
    import time

    start = time.perf_counter()
    parse(["+" + "9" * 5000 + "% " + "and " * 2000 + "Damage", "On " + "a" * 5000 + ":"])
    assert time.perf_counter() - start < 1.0


def test_galvanized_direct_damage_per_status_type() -> None:
    """Saved Galvanized_Shot: on kill, +40% Direct Damage per status type, 14 s, 3 stacks."""
    parsed = parse(
        [
            "On Kill:\n+40% Direct Damage per Status Type affecting the target for 14s. "
            "Stacks up to 3x."
        ]
    )
    assert parsed.support == Support.FULL
    (effect,) = parsed.effects
    assert effect.stat == Stat.DIRECT_DAMAGE and effect.per_status_type
    assert effect.trigger == Trigger.ON_KILL
    assert (effect.value, effect.duration_s, effect.max_stacks) == (0.4, 14.0, 3)
