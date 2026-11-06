"""Walmart client tests against a fake HTTP transport (no network, no credentials)."""

import base64

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from aislescout.sources.walmart import (
    GROCERY_CATEGORY_ID,
    WalmartClient,
    WalmartError,
    WalmartRateLimited,
    generate_key_pair,
    load_private_key,
)

CONSUMER_ID = "1de0df0a-9de1-47b5-bb45-2dc8f26c5ab2"
NOW_MS = 1_793_900_000_000


@pytest.fixture(scope="module")
def key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SEARCH = {
    "query": "milk",
    "totalResults": 4,
    "items": [
        {
            "itemId": 10450114,
            "name": "Great Value Whole Vitamin D Milk, 1 Gallon",
            "salePrice": 3.48,
            "brandName": "Great Value",
            "mediumImage": "https://i5.walmartimages.com/milk-180.jpg",
            "productTrackingUrl": "https://goto.walmart.com/c/|PUBID|/568844/9383?prodsku=10450114",
            "customerRating": "4.6",
            "numReviews": 1234,
            "stock": "Available",
            "marketplace": False,
        },
        {
            "itemId": 222,
            "name": "Fairlife Whole Milk",
            "size": "52 fl oz",
            "msrp": 5.98,
            "salePrice": 4.98,
            "stock": "Limited Supply",
            "customerRating": "not rated",
        },
        {"itemId": 333, "name": "Milk 12-pack (third-party seller)", "salePrice": 40.0, "marketplace": True},
        {"itemId": 444, "name": "Out of stock milk, 1 gal", "salePrice": 2.0, "stock": "Not available"},
        {"itemId": 555, "name": "Installment-only fridge"},
    ],
}

STORES = [
    {
        "no": 2066,
        "name": "WM Supercenter",
        "country": "US",
        "coordinates": [-95.511747, 29.735577],
        "streetAddress": "2727 DUNVALE RD",
        "city": "HOUSTON",
        "stateProvCode": "TX",
        "zip": "77063",
    }
]


class FakeWalmart:
    def __init__(self, key: rsa.RSAPrivateKey, *, status: int = 200, body=None):
        self.public_key = key.public_key()
        self.requests: list[httpx.Request] = []
        self.status = status
        self.body = body

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self._verify_signature(request)
        if self.status != 200:
            return httpx.Response(self.status, json=self.body)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=SEARCH)
        if request.url.path.endswith("/stores"):
            return httpx.Response(200, json=STORES)
        return httpx.Response(404)

    def _verify_signature(self, request: httpx.Request) -> None:
        h = request.headers
        expected = f"{h['WM_CONSUMER.ID']}\n{h['WM_CONSUMER.INTIMESTAMP']}\n{h['WM_SEC.KEY_VERSION']}\n"
        # Raises InvalidSignature if the client signed the wrong string or with the wrong key
        self.public_key.verify(
            base64.b64decode(h["WM_SEC.AUTH_SIGNATURE"]), expected.encode(), padding.PKCS1v15(), hashes.SHA256()
        )


def make_client(key, fake, **kwargs) -> WalmartClient:
    http = httpx.Client(transport=httpx.MockTransport(fake))
    return WalmartClient(CONSUMER_ID, key, base_url="https://api.test/v2", http=http, clock_ms=lambda: NOW_MS, **kwargs)


def test_signed_headers_verify_with_public_key(key):
    fake = FakeWalmart(key)
    make_client(key, fake).search("milk")
    h = fake.requests[0].headers
    assert h["WM_CONSUMER.ID"] == CONSUMER_ID
    assert h["WM_CONSUMER.INTIMESTAMP"] == str(NOW_MS)
    assert h["WM_SEC.KEY_VERSION"] == "1"


def test_search_params_default_to_grocery(key):
    fake = FakeWalmart(key)
    make_client(key, fake).search("  milk ", num_items=100)
    params = fake.requests[0].url.params
    assert params["query"] == "milk"
    assert params["numItems"] == "25"
    assert params["categoryId"] == GROCERY_CATEGORY_ID
    assert "publisherId" not in params


def test_search_maps_items_and_skips_unusable(key):
    deals = make_client(key, FakeWalmart(key)).search("milk")
    assert [d.product_id for d in deals] == ["10450114", "222"]  # marketplace, out of stock, unpriced skipped

    milk, fairlife = deals
    assert milk.source == "walmart" and milk.store_id == "online"
    assert milk.price == 3.48 and not milk.on_sale
    # size comes from the name when there's no size field: 1 gallon = 128 fl oz
    assert milk.unit_basis == "fl oz"
    assert milk.unit_price == pytest.approx(3.48 / 128, abs=1e-4)
    assert milk.product_rating == 4.6 and milk.review_count == 1234
    assert milk.product_url == "https://www.walmart.com/ip/10450114"  # no publisher id -> plain link
    assert milk.image_url == "https://i5.walmartimages.com/milk-180.jpg"

    assert fairlife.on_sale  # msrp above selling price
    assert (fairlife.regular_price, fairlife.sale_price) == (5.98, 4.98)
    assert fairlife.unit_price == pytest.approx(4.98 / 52, abs=1e-4)
    assert fairlife.product_rating is None  # "not rated" isn't a number


def test_publisher_id_fills_tracking_link(key):
    fake = FakeWalmart(key)
    deals = make_client(key, fake, publisher_id="PUB123").search("milk")
    assert fake.requests[0].url.params["publisherId"] == "PUB123"
    assert deals[0].product_url == "https://goto.walmart.com/c/PUB123/568844/9383?prodsku=10450114"


def test_marketplace_can_be_included(key):
    deals = make_client(key, FakeWalmart(key)).search("milk", include_marketplace=True)
    assert "333" in [d.product_id for d in deals]


def test_find_stores(key):
    fake = FakeWalmart(key)
    stores = make_client(key, fake).find_stores("77063")
    assert fake.requests[0].url.params["zip"] == "77063"
    s = stores[0]
    assert (s.store_id, s.chain, s.city, s.state) == ("2066", "WALMART", "HOUSTON", "TX")
    assert (s.latitude, s.longitude) == (29.735577, -95.511747)


def test_api_error_includes_walmart_code(key):
    body = {"errors": [{"message": "Missing search query", "code": 4009}]}
    with pytest.raises(WalmartError) as exc:
        make_client(key, FakeWalmart(key, status=400, body=body)).search("milk")
    assert exc.value.status_code == 400
    assert exc.value.error_code == 4009
    assert "Missing search query" in str(exc.value)


def test_rate_limited(key):
    with pytest.raises(WalmartRateLimited):
        make_client(key, FakeWalmart(key, status=429, body={})).search("milk")


def test_empty_term_rejected(key):
    with pytest.raises(ValueError):
        make_client(key, FakeWalmart(key)).search("   ")


def test_load_private_key_from_pem_and_bare_base64(key):
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    der_b64 = base64.b64encode(
        key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    ).decode()
    for text in (pem, der_b64):
        loaded = load_private_key(text)
        assert loaded.private_numbers() == key.private_numbers()


def test_generate_key_pair(tmp_path):
    path, public_pem = generate_key_pair(tmp_path)
    assert path.read_text().startswith("-----BEGIN PRIVATE KEY-----")
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    with pytest.raises(FileExistsError):  # never silently overwrite a key
        generate_key_pair(tmp_path)


def test_missing_credentials(key):
    with pytest.raises(ValueError):
        WalmartClient("", key)
