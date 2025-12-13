from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, validator


class BaseItem(BaseModel):
    user_id: str
    category: str
    title: str | None = None
    condition: str | None = None
    grade: str | None = None
    graded_by: str | None = None
    sealed: bool | None = None
    attributes_json: dict[str, Any] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list)

    @validator("category")
    def _cat_lower(cls, v):
        return v.lower()


class TCGItem(BaseItem):
    set: str | None = None
    card_no: str | None = None
    rarity: str | None = None
    print_variant: str | None = None
    edition: str | None = None
    psa_cert: str | None = None


class WarhammerItem(BaseItem):
    faction: str | None = None
    unit: str | None = None
    edition: str | None = None
    sealed_sprue: bool | None = None
    assembled: bool | None = None
    paint_quality: int | None = Field(default=None, ge=0, le=5)


class GunplaItem(BaseItem):
    grade_code: str | None = None  # HG/RG/MG/PG
    scale: str | None = None  # 1/144, 1/100
    edition: str | None = None
    limited: bool | None = None


class LegoItem(BaseItem):
    set_no: str | None = None
    theme: str | None = None
    piece_count: int | None = None
    retired: bool | None = None


class DiecastItem(BaseItem):
    scale: str | None = None
    casting: str | None = None
    series: str | None = None
    release_year: int | None = None
    chase_variant: bool | None = None


class DesignerToyItem(BaseItem):
    artist: str | None = None
    edition_size: int | None = None
    drop_date: str | None = None
    blind_box_variant: bool | None = None
    chase_ratio: str | None = None
