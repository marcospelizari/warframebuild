"""Shared base of the JSON API models (G18-G21). Fields are added, never renamed."""

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiError(ApiModel):
    code: str
    message: str
    field: str | None = None
