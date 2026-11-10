"""Pydantic schema for extracted documents. Anything that does not conform raises
instead of being silently emitted."""
from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    confidence: float = Field(0.0, ge=0, le=1)


class FieldResult(BaseModel):
    """A scalar field plus how much we trust it."""
    value: Optional[str | float] = None
    confidence: float = Field(0.0, ge=0, le=1)
    needs_review: bool = True
    reasons: list[str] = Field(default_factory=list)


class Extraction(BaseModel):
    invoice_number: FieldResult
    date: FieldResult            # ISO-8601 string
    vendor: FieldResult
    currency: FieldResult
    subtotal: FieldResult
    tax: FieldResult
    total: FieldResult
    line_items: list[LineItem] = Field(default_factory=list)
    line_items_needs_review: bool = True
    line_items_reasons: list[str] = Field(default_factory=list)
    needs_review: bool = True
    source_file: str = ""
    extractor: str = ""

    @field_validator("date", mode="after")
    @classmethod
    def _iso_date(cls, v: FieldResult):
        if v.value is not None:
            Date.fromisoformat(str(v.value))  # raises ValueError if malformed
        return v


SCALAR_FIELDS = ["invoice_number", "date", "vendor", "currency", "subtotal", "tax", "total"]
MONEY_FIELDS = {"subtotal", "tax", "total"}
