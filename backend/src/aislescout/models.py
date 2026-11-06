"""Source-independent data models shared by every store integration."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, computed_field

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

    # Product-level customer reviews, when the source provides them (store
    # ratings come separately, from Google Places).
    product_rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)

    # computed_field: included when the model is serialized (e.g. in API responses)
    @computed_field  # type: ignore[prop-decorator]
    @property
    def on_sale(self) -> bool:
        return self.sale_price is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def savings_pct(self) -> float | None:
        if self.regular_price and self.sale_price is not None and self.regular_price > 0:
            return round(100 * (1 - self.sale_price / self.regular_price), 1)
        return None


class SearchResult(BaseModel):
    """One deal paired with the store that sells it."""

    deal: Deal
    store: Store


class SourceStatus(BaseModel):
    """How one data source did for one search."""

    source: str
    status: Literal["ok", "skipped", "error"]
    message: str = ""
    result_count: int = 0


class SearchResponse(BaseModel):
    query: str
    zip_code: str
    sale_only: bool = False
    demo: bool = False  # True when results are sample data, not real prices
    results: list[SearchResult]
    sources: list[SourceStatus]
