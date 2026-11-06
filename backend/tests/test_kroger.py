"""Kroger client tests against a fake HTTP transport (no network, no credentials)."""

from datetime import date

import httpx
import pytest

from aislescout.sources.kroger import KrogerClient, KrogerError, KrogerRateLimited

LOCATIONS = {
    "data": [
        {
            "locationId": "70300022",
            "chain": "RALPHS",
            "name": "Ralphs - Palms",
            "address": {"addressLine1": "10309 W National Blvd", "city": "Los Angeles", "state": "CA", "zipCode": "90034"},
            "geolocation": {"latitude": 34.03, "longitude": -118.41, "latLng": "34.03,-118.41"},
        }
    ]
}

PRODUCTS = {
    "data": [
        {
            "productId": "0003338322201",
            "productPageURI": "/p/honeycrisp-apples/0003338322201",
            "brand": "Fresh",
            "description": "Honeycrisp Apples 3 lb Bag",
            "images": [
                {"perspective": "back", "sizes": [{"size": "medium", "url": "https://img/back.jpg"}]},
                {"perspective": "front", "featured": True, "sizes": [{"size": "large", "url": "https://img/front-l.jpg"}, {"size": "medium", "url": "https://img/front-m.jpg"}]},
            ],
            "items": [
                {
                    "itemId": "0003338322201",
                    "size": "3 lb",
                    "soldBy": "UNIT",
                    "price": {
                        "regular": 5.99,
                        "promo": 4.49,
                        "effectiveDate": {"value": "2026-11-04T00:00:00Z", "timezone": "UTC"},
                        "expirationDate": {"value": "2026-11-10T00:00:00Z", "timezone": "UTC"},
                    },
                }
            ],
        },
        {
            "productId": "0000000004017",
            "description": "Granny Smith Apple",
            "items": [{"size": "1 ct", "soldBy": "WEIGHT", "price": {"regular": 1.99, "promo": 0}}],
        },
        {
            "productId": "0001111000001",
            "description": "Apple Juice",
            "items": [{"size": "64 fl oz", "soldBy": "UNIT"}],  # no price at this store
        },
    ]
}


class FakeKroger:
    """Records requests and serves canned responses."""

    def __init__(self, *, cache_control: str = "no-cache", product_status: int = 200):
        self.requests: list[httpx.Request] = []
        self.token_calls = 0
        self.cache_control = cache_control
        self.product_status = product_status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/connect/oauth2/token":
            self.token_calls += 1
            assert request.headers["authorization"].startswith("Basic ")
            assert b"grant_type=client_credentials" in request.content
            assert b"scope=product.compact" in request.content
            return httpx.Response(200, json={"access_token": f"tok{self.token_calls}", "expires_in": 1800})
        assert request.headers["authorization"] == f"Bearer tok{self.token_calls}"
        if path == "/v1/locations":
            return httpx.Response(200, json=LOCATIONS)
        if path == "/v1/products":
            if self.product_status != 200:
                return httpx.Response(self.product_status, text="nope")
            return httpx.Response(200, json=PRODUCTS, headers={"Cache-Control": self.cache_control})
        return httpx.Response(404)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_client(fake: FakeKroger, clock: Clock | None = None) -> KrogerClient:
    http = httpx.Client(transport=httpx.MockTransport(fake))
    return KrogerClient("id", "secret", base_url="https://api.test", http=http, clock=clock or Clock())


def test_find_stores_maps_fields_and_params():
    fake = FakeKroger()
    stores = make_client(fake).find_stores("90034", radius_miles=5, chain="RALPHS")
    assert len(stores) == 1
    s = stores[0]
    assert (s.store_id, s.chain, s.city, s.zip_code) == ("70300022", "RALPHS", "Los Angeles", "90034")
    assert s.latitude == 34.03
    params = fake.requests[-1].url.params
    assert params["filter.zipCode.near"] == "90034"
    assert params["filter.radiusInMiles"] == "5"
    assert params["filter.chain"] == "RALPHS"


def test_search_maps_sale_regular_and_skips_unpriced():
    deals = make_client(FakeKroger()).search("apples", "70300022")
    assert [d.name for d in deals] == ["Honeycrisp Apples 3 lb Bag", "Granny Smith Apple"]

    honeycrisp, granny = deals
    assert honeycrisp.on_sale
    assert (honeycrisp.regular_price, honeycrisp.sale_price, honeycrisp.price) == (5.99, 4.49, 4.49)
    assert honeycrisp.savings_pct == 25.0
    assert honeycrisp.unit_basis == "lb"
    assert honeycrisp.unit_price == pytest.approx(4.49 / 3, abs=1e-4)
    assert honeycrisp.valid_from == date(2026, 11, 4)
    assert honeycrisp.valid_to == date(2026, 11, 10)
    assert honeycrisp.image_url == "https://img/front-m.jpg"
    assert honeycrisp.product_url == "https://www.kroger.com/p/honeycrisp-apples/0003338322201"

    assert not granny.on_sale  # promo 0 means no promo
    assert granny.sold_by == "weight"
    assert (granny.unit_price, granny.unit_basis) == (1.99, "lb")
    assert granny.valid_to is None


def test_search_caps_limit_and_requires_location():
    fake = FakeKroger()
    make_client(fake).search("apples", "70300022", limit=500)
    params = fake.requests[-1].url.params
    assert params["filter.limit"] == "50"
    assert params["filter.locationId"] == "70300022"


def test_short_term_rejected():
    with pytest.raises(ValueError):
        make_client(FakeKroger()).search("ap", "70300022")


def test_token_reused_until_expiry():
    fake, clock = FakeKroger(), Clock()
    client = make_client(fake, clock)
    client.search("apples", "1")
    client.search("pears", "1")
    assert fake.token_calls == 1
    clock.now += 1800  # past expiry (minus safety margin)
    client.search("plums", "1")
    assert fake.token_calls == 2


def test_no_cache_by_default():
    fake = FakeKroger(cache_control="no-cache")
    client = make_client(fake)
    client.search("apples", "1")
    client.search("apples", "1")
    assert sum(r.url.path == "/v1/products" for r in fake.requests) == 2


def test_cache_respects_max_age():
    fake, clock = FakeKroger(cache_control="public, max-age=60"), Clock()
    client = make_client(fake, clock)
    client.search("apples", "1")
    client.search("apples", "1")
    assert sum(r.url.path == "/v1/products" for r in fake.requests) == 1
    clock.now += 61
    client.search("apples", "1")
    assert sum(r.url.path == "/v1/products" for r in fake.requests) == 2


def test_rate_limit_raises():
    with pytest.raises(KrogerRateLimited):
        make_client(FakeKroger(product_status=429)).search("apples", "1")


def test_server_error_raises():
    with pytest.raises(KrogerError) as exc:
        make_client(FakeKroger(product_status=500)).search("apples", "1")
    assert exc.value.status_code == 500


def test_missing_credentials():
    with pytest.raises(ValueError):
        KrogerClient("", "")
