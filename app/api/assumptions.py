"""The `assumptions[]` of a /calc build: what the numbers take for granted, with sources."""

from app.api.schemas.build import Assumption, Combat, Source
from app.gamedata.models import Weapon
from app.optimize.conditions import Resolved
from app.optimize.evaluate import Evaluation

WIKI = "https://wiki.warframe.com/w/"

MAIN_ATTACK = {
    "normal": "Charge and burst from the first listed attack",
    "incarnon": "Incarnon Form; magazine and reload of the normal form",
}


def assumptions(
    weapon: Weapon, e: Evaluation, fights: Combat, conditions: Resolved
) -> list[Assumption]:
    out = [
        Assumption(id="max_rank", text="Mods at max rank"),
        Assumption(
            id="unconditional",
            text="Arsenal and DPS figures: only unconditional mod effects (as in the arsenal)",
        ),
        Assumption(
            id="conditions",
            text=(
                "Combat counts conditional effects as mid-mission: kill stacks at max; buffs "
                "from hits, crits, status procs and reloads at the stacks the build's own "
                "trigger rate holds (a stack is lost when the buff times out), rates taken "
                "before those buffs; first-shot bonuses by their share of the magazine; "
                "Galvanized bonuses per status type on the target (not Knockdown or Lifted)"
            ),
            source=Source(kind="wiki", url=WIKI + "Galvanized_Aptitude"),
        ),
        Assumption(id="main_attack", text=MAIN_ATTACK[e.form]),
        Assumption(id="direct_only", text="DPS figures: direct hits on the body; no DoT or Blast"),
        Assumption(
            id="combat",
            text=(
                f"Combat: representative Steel Path enemies at level {fights.level}, expected "
                f"values (average crits and procs), {fights.cap_s:g} s cap; DoT, Blast, armor "
                "strip, Viral, Magnetic, Puncture and Cold count; Cold freeze, Magnetic "
                "shield-break burst, Sentient adaptation and Overguard not modelled"
            ),
            value=fights.level,
            source=Source(kind="wiki", url=WIKI + "Enemy_Level_Scaling"),
        ),
        Assumption(
            id="combat_simplified",
            text=(
                "Combat simplifications: all parts of a shot land with it; Electricity and Gas "
                "procs tick with their own +1; Heat keeps burning while procs come faster than "
                "its duration; the sniper combo never decays (no misses, reload gaps ignored); "
                "beams ramp from their start value to full over 0.6 s and decay 0.8 s after a "
                "stop over 2 s (linear)"
            ),
        ),
        Assumption(
            id="bane",
            text=(
                "Faction damage mods hit Corpus, Grineer, Infested, Orokin and The Murmur; "
                "none for Sentient, Scaldra and Techrot (not listed)"
            ),
            source=Source(kind="wiki", url=WIKI + "Faction_Damage_Mods"),
        ),
        Assumption(
            id="armor",
            text=(
                "Armor per the wiki formula; a Simulacrum check at level 1 saw less armor "
                "than it predicts (open)"
            ),
            source=Source(kind="wiki", url=WIKI + "Armor"),
        ),
    ]
    if e.headshot:
        text = (
            f"Aimed at heads ({e.headshot.reason}): head DPS while aiming, at the highest zoom, "
            "on the reference head; body DPS is hip-fire"
        )
        out.append(Assumption(id="headshot", text=text, source=source(e.headshot.source)))
        if e.head_triggered:
            text = (
                "Needs headshots, shown at 0 and max hit stacks (kill stacks not counted): "
                + ", ".join(e.head_triggered)
            )
            out.append(Assumption(id="head_stacks", text=text))
    c = conditions
    if c.needs_kills:
        text = "Needs kills, at max stacks in combat: " + ", ".join(c.needs_kills)
        out.append(Assumption(id="needs_kills", text=text))
    if c.held:
        text = "Conditional buffs in combat (stacks held, or share of shots or time): " + ", ".join(
            f"{name} {stacks:.3g}/{top}" for name, stacks, top in c.held
        )
        out.append(Assumption(id="held_stacks", text=text))
    if c.inactive:
        text = "Never active in combat (needs melee kills, ability casts or headshots): "
        out.append(Assumption(id="inactive_conditions", text=text + ", ".join(c.inactive)))
    if e.not_modelled:
        text = "Effects not modelled yet: " + ", ".join(e.not_modelled)
        out.append(Assumption(id="not_modelled", text=text))
    if e.aoe_parts:
        out.append(Assumption(id="aoe_full", text="AoE parts at full damage, no falloff"))
    if e.note:
        out.append(Assumption(id="incarnon_note", text=e.note))
    if e.inactive_perks:
        text = f"No effect in {e.form} form: " + ", ".join(e.inactive_perks)
        out.append(Assumption(id="inactive_perks", text=text))
    if e.sets:
        text = "Mod set bonuses count only the set mods on this gun: " + ", ".join(e.sets)
        out.append(Assumption(id="set_pieces", text=text))
    if e.ammo_cost_assumed:
        out.append(Assumption(id="ammo_cost", text="1 ammo per shot", value=1))
    if e.bonus_element and weapon.bonus_element:
        out.append(
            Assumption(
                id="bonus_element_share",
                text="Bonus element at its maximum share of base damage",
                value=e.bonus_element[1],
                source=Source(kind="wiki", url=WIKI + weapon.bonus_element.page),
            )
        )
    return out


def source(title: str | None) -> Source | None:
    return Source(kind="wiki", url=WIKI + title) if title else None
