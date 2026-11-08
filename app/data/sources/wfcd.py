"""WFCD warframe-items JSON (MIT): polarities, class, attacks, falloff, images (G2)."""

from app.data.http import PoliteClient
from app.data.sources import Fetched

BASE_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json"
FILES = ("Primary.json", "Secondary.json")
MAX_BYTES = 32 * 1024 * 1024


def fetch(client: PoliteClient) -> list[Fetched]:
    return [
        Fetched(f"wfcd/{n}", f"{BASE_URL}/{n}", client.get(f"{BASE_URL}/{n}", max_bytes=MAX_BYTES))
        for n in FILES
    ]
