"""Client for Kroger's official public APIs (Kroger, Ralphs, Fred Meyer, King Soopers, ...).

Docs: https://developer.kroger.com (Products API, Locations API, Authorization).

Terms that shape this module (developer.kroger.com/terms):
- No permanent copies or databases of API content: we fetch live and only keep an
  in-memory cache for as long as the response's Cache-Control header allows.
- Public Products API limit: 10,000 calls/day across all /products operations.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx

from aislescout.models import Deal, Store
from aislescout.parsing import parse_quantity, unit_price

SOURCE = "kroger"
BASE_URL = "https://api.kroger.com"
PRODUCT_SCOPE = "product.compact"
MAX_PRODUCTS_PER_PAGE = 50  # documented maximum for filter.limit
_TOKEN_SAFETY_MARGIN_S = 60
_FAR_FUTURE_YEAR = 9999  # Kroger uses 9999-12-31 for "no end date"


class KrogerError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class KrogerRateLimited(KrogerError):
    """HTTP 429: the daily call quota is used up."""


class KrogerClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = BASE_URL,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Kroger client_id and client_secret are required (see backend/.env.example)")
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=15.0)
        self._owns_http = http is None
        self._clock = clock
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], tuple[float, Any]] = {}

    # -- lifecycle -------------------------------------------------------------

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> KrogerClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- public API ------------------------------------------------------------

    def find_stores(
        self,
        zip_code: str,
        *,
        radius_miles: int = 10,
        limit: int = 10,
        chain: str | None = None,
    ) -> list[Store]:
        params: dict[str, Any] = {
            "filter.zipCode.near": zip_code,
            "filter.radiusInMiles": radius_miles,
            "filter.limit": limit,
        }
        if chain:
            params["filter.chain"] = chain
        body = self._get("/v1/locations", params)
        return [_to_store(loc) for loc in body.get("data", [])]

    def search(self, term: str, location_id: str, *, limit: int = MAX_PRODUCTS_PER_PAGE, start: int = 0) -> list[Deal]:
        """Search products at one store. Items without a price at that store are skipped."""
        if len(term.strip()) < 3:
            raise ValueError("Kroger search terms must be at least 3 characters")
        params = {
            "filter.term": term.strip(),
            "filter.locationId": location_id,
            "filter.limit": min(limit, MAX_PRODUCTS_PER_PAGE),
            "filter.start": start,
        }
        body = self._get("/v1/products", params)
        deals: list[Deal] = []
        for product in body.get("data", []):
            deals.extend(_to_deals(product, location_id))
        return deals

    # -- HTTP plumbing -----------------------------------------------------------

    def _access_token(self) -> str:
        if self._token and self._clock() < self._token_expires_at:
            return self._token
        resp = self._http.post(
            f"{self._base_url}/v1/connect/oauth2/token",
            data={"grant_type": "client_credentials", "scope": PRODUCT_SCOPE},
            auth=(self._client_id, self._client_secret),
        )
        if resp.status_code != 200:
            raise KrogerError(f"Kroger token request failed: {resp.status_code} {resp.text[:200]}", resp.status_code)
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = self._clock() + float(payload.get("expires_in", 1800)) - _TOKEN_SAFETY_MARGIN_S
        return self._token

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        key = (path, tuple(sorted((k, str(v)) for k, v in params.items())))
        cached = self._cache.get(key)
        if cached and self._clock() < cached[0]:
            return cached[1]

        resp = self._request(path, params)
        if resp.status_code == 401:  # token revoked or expired early: refresh once
            self._token = None
            resp = self._request(path, params)
        if resp.status_code == 429:
            raise KrogerRateLimited("Kroger API daily quota exceeded", 429)
        if resp.status_code >= 400:
            raise KrogerError(f"Kroger GET {path} failed: {resp.status_code} {resp.text[:200]}", resp.status_code)

        body = resp.json()
        max_age = _cache_max_age(resp.headers.get("cache-control", ""))
        if max_age > 0:
            self._cache[key] = (self._clock() + max_age, body)
        return body

    def _request(self, path: str, params: dict[str, Any]) -> httpx.Response:
        return self._http.get(
            f"{self._base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self._access_token()}", "Accept": "application/json"},
        )


# -- mapping helpers ---------------------------------------------------------------


def _cache_max_age(cache_control: str) -> int:
    directives = cache_control.lower()
    if "no-store" in directives or "no-cache" in directives or "private" in directives:
        return 0
    m = re.search(r"max-age=(\d+)", directives)
    return int(m.group(1)) if m else 0


def _to_store(loc: dict[str, Any]) -> Store:
    address = loc.get("address") or {}
    geo = loc.get("geolocation") or {}
    chain = loc.get("chain") or ""
    if isinstance(chain, dict):  # the /chains model uses an object; locations use a string
        chain = chain.get("name", "")
    return Store(
        source=SOURCE,
        store_id=str(loc["locationId"]),
        chain=str(chain).upper(),
        name=loc.get("name", ""),
        address=address.get("addressLine1", ""),
        city=address.get("city", ""),
        state=address.get("state", ""),
        zip_code=address.get("zipCode", ""),
        latitude=geo.get("latitude"),
        longitude=geo.get("longitude"),
    )


def _parse_date(value: Any) -> date | None:
    raw = value.get("value") if isinstance(value, dict) else value
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
    return None if parsed.year >= _FAR_FUTURE_YEAR else parsed


def _image_url(product: dict[str, Any]) -> str | None:
    images = product.get("images") or []
    ranked = sorted(images, key=lambda im: (not im.get("featured"), im.get("perspective") != "front"))
    for image in ranked:
        sizes = {s.get("size"): s.get("url") for s in image.get("sizes", [])}
        for wanted in ("medium", "large", "small", "xlarge", "thumbnail"):
            if sizes.get(wanted):
                return sizes[wanted]
    return None


def _to_deals(product: dict[str, Any], location_id: str) -> list[Deal]:
    deals: list[Deal] = []
    page = product.get("productPageURI")
    for item in product.get("items", []):
        price = item.get("price") or {}
        regular = price.get("regular") or None
        promo = price.get("promo") or None  # Kroger sends 0 when there's no promo
        sale = promo if promo and (regular is None or promo < regular) else None
        current = sale if sale is not None else regular
        if not current or current <= 0:
            continue  # not priced at this store

        # Assumption to verify with live data: for soldBy == "weight", Kroger's
        # price is per lb (and *PerUnitEstimate is the price of one typical item).
        sold_by = "weight" if str(item.get("soldBy", "")).lower() == "weight" else "unit"
        size = item.get("size", "") or ""
        normalized = unit_price(current, parse_quantity(size), per_lb=sold_by == "weight")

        deals.append(
            Deal(
                source=SOURCE,
                store_id=location_id,
                product_id=str(product.get("productId") or item.get("itemId")),
                name=product.get("description", ""),
                brand=product.get("brand", "") or "",
                size_text=size,
                sold_by=sold_by,
                regular_price=regular,
                sale_price=sale,
                price=current,
                unit_price=normalized[0] if normalized else None,
                unit_basis=normalized[1] if normalized else None,
                valid_from=_parse_date(price.get("effectiveDate")) if sale is not None else None,
                valid_to=_parse_date(price.get("expirationDate")) if sale is not None else None,
                image_url=_image_url(product),
                product_url=f"https://www.kroger.com{page}" if page else None,
            )
        )
    return deals
