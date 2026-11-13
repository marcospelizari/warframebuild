from app.pipeline.build.attacks import attack


def test_wfcd_speed_zero_means_no_own_fire_rate() -> None:
    dot = {
        "name": "Corrosive DoT",
        "speed": 0,
        "crit_chance": 0,
        "crit_mult": 1,
        "status_chance": 0,
        "damage": {"corrosive": 10},
    }
    assert attack(dot, "Tysis", None).fire_rate is None
