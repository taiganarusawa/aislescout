"""Source-independent data models shared by every store integration."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

UnitBasis = Literal["lb", "fl oz", "each"]


class Store(BaseModel):
    """A physical store location from any source."""

    source: str  # e.g. "kroger"
    store_id: str  # the source's own location id
    chain: str  # e.g. "RALPHS"
    name: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    latitude: float | None = None
    longitude: float | None = None


class Deal(BaseModel):
    """One purchasable item at one store, with its current price.

    `price` is what the shopper pays right now for one purchase unit (one item, or
    one lb when `sold_by == "weight"`), already reduced for multi-buy and BOGO
    offers. `unit_price` normalizes that to `unit_basis` so items with different
    package sizes can be compared.
    """

    source: str
    store_id: str
    product_id: str
    name: str
    brand: str = ""
    size_text: str = ""
    sold_by: Literal["unit", "weight"] = "unit"

    regular_price: float | None = None
    sale_price: float | None = None
    price: float
    min_quantity: int = Field(default=1, ge=1)
    member_only: bool = False

    unit_price: float | None = None
    unit_basis: UnitBasis | None = None

    valid_from: date | None = None
    valid_to: date | None = None
    image_url: str | None = None
    product_url: str | None = None

    @property
    def on_sale(self) -> bool:
        return self.sale_price is not None

    @property
    def savings_pct(self) -> float | None:
        if self.regular_price and self.sale_price is not None and self.regular_price > 0:
            return round(100 * (1 - self.sale_price / self.regular_price), 1)
        return None
