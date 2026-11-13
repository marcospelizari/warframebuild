from app.domain.archon_shards import SLOTS, Shard
from app.domain.effects import DamageType
from app.gamedata.models import Mod
from app.gamedata.store import GameData
from app.optimize import shards
from app.optimize.loadout import Loadout, loadout
from app.optimize.scoring import combat_objective, max_objective


def _gun(data: GameData, name: str, *mods: str) -> Loadout:
    by_name: dict[str, Mod] = {m.name: m for m in data.mods.mods}
    weapon = next(w for w in data.weapons if w.name == name)
    return loadout(weapon, [by_name[n] for n in mods])


def test_each_slot_adds_the_best_next_shard(gamedata: GameData) -> None:
    lo = _gun(gamedata, "Soma Prime", "Serration", "Split Chamber", "Point Strike")
    objective = combat_objective(gamedata)
    a = shards.advice(lo, gamedata.archon_shards, gamedata.status_rules, objective)
    scores = [s.score for s in a.normal]
    assert 0 < len(scores) <= SLOTS and scores == sorted(scores)
    assert scores[0] > objective(lo)
    assert a.tauforged[0].score > a.normal[0].score  # x1.5 values


def test_violet_electricity_combines_after_the_mods(gamedata: GameData) -> None:
    """Saved Archon_Shard:388: the shard's Electricity combines with the mods' elements."""
    lo = _gun(gamedata, "Soma Prime", "Cryo Rounds")
    shot = shards.with_shards(lo, gamedata.archon_shards, [Shard.VIOLET], False)
    damage = shot.shot(shot.body_bonuses()).hits[0].damage
    assert DamageType.MAGNETIC in damage and DamageType.COLD not in damage


def test_topaz_counts_only_on_a_build_that_applies_heat(gamedata: GameData) -> None:
    """PLAN G91: Topaz needs kills on enemies with Heat."""
    base = ("Hornet Strike", "Barrel Diffusion", "Pistol Gambit", "Target Cracker")
    rules, table, objective = gamedata.status_rules, gamedata.archon_shards, max_objective(gamedata)
    heat = shards.advice(
        _gun(gamedata, "Lex Prime", *base, "Heated Charge"), table, rules, objective
    )
    gas = _gun(gamedata, "Lex Prime", *base, "Heated Charge", "Pistol Pestilence")
    no_heat = shards.advice(gas, table, rules, objective)
    assert heat.normal[0].shard == Shard.TOPAZ and heat.conditions
    assert Shard.TOPAZ not in {s.shard for s in no_heat.normal} and not no_heat.conditions


def test_no_step_when_no_shard_gains(gamedata: GameData) -> None:
    """A slot no shard improves is left to the frame."""
    lo = _gun(gamedata, "Lex Prime", "Hornet Strike")
    a = shards.advice(lo, gamedata.archon_shards, gamedata.status_rules, lambda _: 1.0)
    assert a.normal == a.tauforged == []
