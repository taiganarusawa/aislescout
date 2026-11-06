"""The interface every data source implements, plus adapters for the API clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from aislescout.models import Deal, Store
from aislescout.sources.kroger import KrogerClient
from aislescout.sources.walmart import ONLINE_STORE_ID, WalmartClient


@dataclass
class SourceResult:
    stores: list[Store] = field(default_factory=list)
    deals: list[Deal] = field(default_factory=list)
    message: str = ""  # e.g. "no stores within 10 miles"


class DealSource(Protocol):
    name: str

    def search(self, term: str, zip_code: str, limit: int) -> SourceResult: ...

    def close(self) -> None: ...


class KrogerSource:
    """Searches the nearest Kroger-family store to the zip code."""

    name = "kroger"

    def __init__(self, client: KrogerClient, *, radius_miles: int = 10) -> None:
        self._client = client
        self._radius = radius_miles

    def search(self, term: str, zip_code: str, limit: int) -> SourceResult:
        nearest = self._client.find_stores(zip_code, radius_miles=self._radius, limit=1)
        if not nearest:
            return SourceResult(message=f"no Kroger-family stores within {self._radius} miles")
        store = nearest[0]
        return SourceResult(stores=[store], deals=self._client.search(term, store.store_id, limit=limit))

    def close(self) -> None:
        self._client.close()


WALMART_ONLINE = Store(source="walmart", store_id=ONLINE_STORE_ID, chain="WALMART", name="walmart.com")


class WalmartSource:
    """walmart.com online prices (the Affiliate API has no per-store pricing)."""

    name = "walmart"

    def __init__(self, client: WalmartClient) -> None:
        self._client = client

    def search(self, term: str, zip_code: str, limit: int) -> SourceResult:
        return SourceResult(stores=[WALMART_ONLINE], deals=self._client.search(term, num_items=limit))

    def close(self) -> None:
        self._client.close()
