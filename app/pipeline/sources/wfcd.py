"""WFCD warframe-items JSON (MIT): polarities, class, attacks, falloff, images, arcane slots."""

from app.gamedata.models import Category
from app.pipeline.sources import Fetched
from app.pipeline.sources.http import PoliteClient

BASE_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json"
FILES = ("Primary.json", "Secondary.json", "Arcanes.json")

# WFCD arcane `type` -> the gun slot it fits: (category, weapon_type it is limited to).
GUN_ARCANE_TYPES: dict[str, tuple[Category, str | None]] = {
    "Primary Arcane": (Category.PRIMARY, None),
    "Shotgun Arcane": (Category.PRIMARY, "Shotgun"),
    "Bow Arcane": (Category.PRIMARY, "Bow"),
    "Secondary Arcane": (Category.SECONDARY, None),
}
# Known types that never go on a gun; any other type fails the refresh.
OTHER_ARCANE_TYPES = frozenset(
    {
        "Warframe Arcane",
        "Operator Arcane",
        "Amp Arcane",
        "Melee Arcane",
        "Zaw Arcane",
        "Kitgun Arcane",
        "Arcane",
    }
)
MAX_BYTES = 32 * 1024 * 1024


def fetch(client: PoliteClient) -> list[Fetched]:
    return [
        Fetched(f"wfcd/{n}", f"{BASE_URL}/{n}", client.get(f"{BASE_URL}/{n}", max_bytes=MAX_BYTES))
        for n in FILES
    ]
