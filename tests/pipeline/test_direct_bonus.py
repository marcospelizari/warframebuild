"""reference/galvanized_behaviour.json against the committed gamedata/: the fixtures hold
only a few guns, so the rows for the other guns are checked here."""

import json
from pathlib import Path

from app.gamedata import store

ROOT = Path(__file__).resolve().parents[2]


def test_galvanized_rows_name_real_guns_and_attacks() -> None:
    data = store.load(ROOT / "gamedata")
    attacks = {w.unique_name: {a.name: a.direct_bonus for a in w.attacks} for w in data.weapons}
    table = json.loads((ROOT / "reference/galvanized_behaviour.json").read_text())
    for uid, row in table["weapons"].items():
        assert uid in attacks, row["name"]
        for attack, behaviour in row["attacks"].items():
            assert attacks[uid].get(attack) == behaviour, (row["name"], attack)
