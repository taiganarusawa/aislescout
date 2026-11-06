from fastapi.testclient import TestClient

from aislescout.api import create_app
from aislescout.search import SearchService
from aislescout.sources.demo import DemoSource


def make_client() -> TestClient:
    return TestClient(create_app(lambda: SearchService([DemoSource()], demo=True)))


def test_health():
    with make_client() as client:
        body = client.get("/api/health").json()
    assert body == {"status": "ok", "sources": ["demo"], "demo": True}


def test_search_returns_ranked_results_with_computed_fields():
    with make_client() as client:
        resp = client.get("/api/search", params={"q": "apples", "zip": "90034"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "apples" and body["zip_code"] == "90034" and body["demo"] is True
    first = body["results"][0]
    assert set(first) == {"deal", "store"}
    # computed fields are serialized for the frontend
    assert "on_sale" in first["deal"] and "savings_pct" in first["deal"]
    assert body["sources"] == [{"source": "demo", "status": "ok", "message": "", "result_count": len(body["results"])}]


def test_sale_only():
    with make_client() as client:
        body = client.get("/api/search", params={"q": "apples", "zip": "90034", "sale_only": "true"}).json()
    assert body["results"] and all(r["deal"]["on_sale"] for r in body["results"])


def test_validation_errors():
    with make_client() as client:
        assert client.get("/api/search", params={"q": "ap", "zip": "90034"}).status_code == 422
        assert client.get("/api/search", params={"q": "apples", "zip": "9003"}).status_code == 422
        assert client.get("/api/search", params={"q": "apples", "zip": "abcde"}).status_code == 422
        assert client.get("/api/search", params={"q": "apples"}).status_code == 422
        assert client.get("/api/search", params={"q": "apples", "zip": "90034", "limit": 0}).status_code == 422


def test_cors_allows_local_frontend():
    with make_client() as client:
        resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
