"""gamedata/ schema: meta.json, the record of a dataset (sources, counts, exclusions)."""

from typing import Literal

from pydantic import Field

from app.gamedata.models import IsoDate, Model


class Exclusion(Model):
    unique_name: str
    name: str
    reason: str  # for us: refresh report, wfb check
    pending: bool = False  # new, waiting for source data (G90 U7/U8), not left out by hand


class SourceRecord(Model):
    path: str
    url: str
    retrieved: str
    sha256_16: str


class Meta(Model):
    schema_version: Literal[25] = 25
    dataset_hash: str
    # Newest content update named in the data (WFCD `introduced`); a label only:
    # DE publishes no update name, and hotfixes without new items do not change it.
    game_update: str | None
    fetched: IsoDate  # newest download date of the DE/WFCD sources
    changed_on: IsoDate  # first refresh that produced this dataset_hash; staleness reference
    sources: list[SourceRecord]
    counts: dict[str, int]
    excluded_weapons: list[Exclusion]
    denied_mods: dict[str, int] = Field(description="denied gun mods per mod_filter rule")


class Join(Model):
    unique_name: str
    de_name: str
    wfcd_name: str
