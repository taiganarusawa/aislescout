"""Client for Walmart's official Affiliate API (walmart.io).

Docs: https://walmart.io/docs/affiliates/v1/introduction

- Every request is signed: SHA256-with-RSA over the sorted header values
  (WM_CONSUMER.ID, WM_CONSUMER.INTIMESTAMP, WM_SEC.KEY_VERSION), each followed by
  a newline. A signature is valid for 180 seconds.
- Search returns walmart.com *online* prices. There's no per-store pricing, so
  every Walmart deal uses the store id "online".
- Terms: 5,000 calls/day. No scraping walmart.com; use this API instead.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from aislescout.models import Deal, Store
from aislescout.parsing import parse_quantity, unit_price

SOURCE = "walmart"
ONLINE_STORE_ID = "online"
BASE_URL = "https://developer.api.walmart.com/api-proxy/service/affil/product/v2"
MAX_ITEMS_PER_PAGE = 25  # documented maximum for numItems
# "Food" in Walmart's taxonomy. Narrows "apples" to groceries instead of iPhones.
# Check against the /taxonomy endpoint on the first live run.
GROCERY_CATEGORY_ID = "976759"


class WalmartError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, error_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class WalmartRateLimited(WalmartError):
    """HTTP 429: the daily call quota is used up."""


def load_private_key(key_text: str) -> rsa.RSAPrivateKey:
    """Load an RSA private key from PEM text, or from bare base64 PKCS#8 DER
    (the format Walmart's Java sample uses)."""
    data = key_text.strip()
    if data.startswith("-----BEGIN"):
        key = serialization.load_pem_private_key(data.encode(), password=None)
    else:
        key = serialization.load_der_private_key(base64.b64decode("".join(data.split())), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("Walmart requires an RSA private key")
    return key


def generate_key_pair(directory: Path, filename: str = "walmart_private_key.pem") -> tuple[Path, str]:
    """Create a 2048-bit RSA key pair for walmart.io.

    Writes the private key (PKCS#8 PEM) to `directory/filename` and returns
    (path, public key PEM). The public key is what you upload to walmart.io.
    """
    if Path(filename).name != filename:
        raise ValueError("filename must be a plain file name, not a path")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    if path.exists():
        raise FileExistsError(f"{path} already exists; delete it first if you really want a new key")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return path, public_pem.decode()


class WalmartClient:
    def __init__(
        self,
        consumer_id: str,
        private_key: rsa.RSAPrivateKey | str,
        *,
        key_version: str = "1",
        publisher_id: str | None = None,
        base_url: str = BASE_URL,
        http: httpx.Client | None = None,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    ) -> None:
        if not consumer_id or not private_key:
            raise ValueError("Walmart consumer id and private key are required (see backend/.env.example)")
        self._consumer_id = consumer_id.strip()
        self._key = load_private_key(private_key) if isinstance(private_key, str) else private_key
        self._key_version = str(key_version).strip()
        self._publisher_id = publisher_id or None
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=15.0)
        self._owns_http = http is None
        self._clock_ms = clock_ms

    # -- lifecycle -------------------------------------------------------------

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> WalmartClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- public API ------------------------------------------------------------

    def search(
        self,
        term: str,
        *,
        category_id: str | None = GROCERY_CATEGORY_ID,
        num_items: int = MAX_ITEMS_PER_PAGE,
        start: int = 1,
        include_marketplace: bool = False,
    ) -> list[Deal]:
        """Search walmart.com. Marketplace (third-party seller) items are skipped
        by default because their prices aren't Walmart's own."""
        if not term.strip():
            raise ValueError("search term is required")
        params: dict[str, Any] = {
            "query": term.strip(),
            "numItems": max(1, min(num_items, MAX_ITEMS_PER_PAGE)),
            "start": start,
        }
        if category_id:
            params["categoryId"] = category_id
        if self._publisher_id:
            params["publisherId"] = self._publisher_id
        body = self._get("/search", params)
        deals = []
        for item in body.get("items", []) or []:
            if item.get("marketplace") and not include_marketplace:
                continue
            deal = self._to_deal(item)
            if deal is not None:
                deals.append(deal)
        return deals

    def find_stores(self, zip_code: str) -> list[Store]:
        body = self._get("/stores", {"zip": zip_code})
        rows = body if isinstance(body, list) else body.get("stores", []) or []
        return [_to_store(row) for row in rows]

    # -- signing and HTTP --------------------------------------------------------

    def signed_headers(self) -> dict[str, str]:
        timestamp = str(self._clock_ms())
        headers = {
            "WM_CONSUMER.ID": self._consumer_id,
            "WM_CONSUMER.INTIMESTAMP": timestamp,
            "WM_SEC.KEY_VERSION": self._key_version,
        }
        # Walmart's canonical form: values of the header names in sorted order, each + "\n"
        to_sign = "".join(f"{headers[name].strip()}\n" for name in sorted(headers))
        signature = self._key.sign(to_sign.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        headers["WM_SEC.AUTH_SIGNATURE"] = base64.b64encode(signature).decode()
        headers["Accept"] = "application/json"
        return headers

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        resp = self._http.get(f"{self._base_url}{path}", params=params, headers=self.signed_headers())
        if resp.status_code == 429:
            raise WalmartRateLimited("Walmart API daily quota exceeded", 429)
        if resp.status_code >= 400:
            message, code = _error_details(resp)
            raise WalmartError(f"Walmart GET {path} failed: {resp.status_code} {message}", resp.status_code, code)
        return resp.json()

    # -- mapping -----------------------------------------------------------------

    def _to_deal(self, item: dict[str, Any]) -> Deal | None:
        price = item.get("salePrice")
        if not price or price <= 0:
            return None  # e.g. installment-only items have no salePrice
        if item.get("stock") == "Not available" or item.get("availableOnline") is False:
            return None

        name = item.get("name", "") or ""
        size = item.get("size", "") or ""
        # Walmart grocery names usually carry the size ("Great Value Whole Milk, 1 Gallon")
        quantity = parse_quantity(size) or parse_quantity(name)
        normalized = unit_price(price, quantity)

        # Walmart has no separate promo field. MSRP above the selling price is the
        # closest thing to a "was" price (rollbacks, clearance).
        msrp = item.get("msrp")
        on_sale = bool(msrp and msrp > price)

        rating = _to_float(item.get("customerRating"))
        return Deal(
            source=SOURCE,
            store_id=ONLINE_STORE_ID,
            product_id=str(item.get("itemId")),
            name=name,
            brand=item.get("brandName", "") or "",
            size_text=size,
            regular_price=msrp if on_sale else price,
            sale_price=price if on_sale else None,
            price=price,
            unit_price=normalized[0] if normalized else None,
            unit_basis=normalized[1] if normalized else None,
            image_url=item.get("mediumImage") or item.get("thumbnailImage"),
            product_url=self._product_url(item),
            product_rating=rating if rating is not None and 0 <= rating <= 5 else None,
            review_count=item.get("numReviews"),
        )

    def _product_url(self, item: dict[str, Any]) -> str | None:
        tracking = item.get("productTrackingUrl")
        if tracking and self._publisher_id:
            return tracking.replace("|PUBID|", self._publisher_id)
        item_id = item.get("itemId")
        return f"https://www.walmart.com/ip/{item_id}" if item_id else None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _error_details(resp: httpx.Response) -> tuple[str, int | None]:
    try:
        errors = resp.json().get("errors") or []
        if errors:
            return str(errors[0].get("message", "")), errors[0].get("code")
    except (ValueError, AttributeError):
        pass
    return resp.text[:200], None


def _to_store(row: dict[str, Any]) -> Store:
    coords = row.get("coordinates") or [None, None]  # [longitude, latitude]
    return Store(
        source=SOURCE,
        store_id=str(row.get("no")),
        chain="WALMART",
        name=row.get("name", "") or "",
        address=row.get("streetAddress", "") or "",
        city=row.get("city", "") or "",
        state=row.get("stateProvCode", "") or "",
        zip_code=row.get("zip", "") or "",
        longitude=coords[0],
        latitude=coords[1],
    )
