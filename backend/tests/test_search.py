from dataclasses import replace

import pytest

from aislescout.config import Settings
from aislescout.models import Deal, SourceStatus, Store
from aislescout.search import SearchService
from aislescout.sources.base import SourceResult
from aislescout.sources.demo import DemoSource


def store(source: str, store_id: str = "s1") -> Store:
    return Store(source=source, store_id=store_id, chain=source.upper(), name=f"{source} store")


def deal(source: str, name: str, price: float, unit: float | None, basis: str | None, *, sale: bool = False) -> Deal:
    return Deal(
        source=source,
        store_id="s1",
        product_id=name,
        name=name,
        price=price,
        regular_price=price + 1 if sale else price,
        sale_price=price if sale else None,
        unit_price=unit,
        unit_basis=basis,
    )


class FakeSource:
    def __init__(self, name: str, deals: list[Deal] | None = None, error: Exception | None = None, message: str = ""):
        self.name = name
        self._deals = deals or []
        self._error = error
        self._message = message
        self.closed = False
        self.calls: list[tuple[str, str, int]] = []

    def search(self, term: str, zip_code: str, limit: int) -> SourceResult:
        self.calls.append((term, zip_code, limit))
        if self._error:
            raise self._error
        return SourceResult(stores=[store(self.name)], deals=self._deals, message=self._message)

    def close(self) -> None:
        self.closed = True


def test_merges_sources_and_ranks_by_basis_then_unit_price():
    a = FakeSource("alpha", [deal("alpha", "A per lb", 3.0, 3.0, "lb"), deal("alpha", "A each", 1.0, 1.0, "each")])
    b = FakeSource("beta", [deal("beta", "B per lb", 4.0, 1.5, "lb"), deal("beta", "B no size", 2.0, None, None)])
    response = SearchService([a, b]).search("apples", "90034", limit=7)

    assert [r.deal.name for r in response.results] == ["B per lb", "A per lb", "A each", "B no size"]
    assert response.results[0].store.chain == "BETA"
    assert a.calls == [("apples", "90034", 7)]
    assert [(s.source, s.status, s.result_count) for s in response.sources] == [("alpha", "ok", 2), ("beta", "ok", 2)]
    assert not response.demo


def test_one_failing_source_does_not_break_search():
    good = FakeSource("good", [deal("good", "milk", 3.0, 0.02, "fl oz")])
    bad = FakeSource("bad", error=RuntimeError("401 Public Key not found"))
    response = SearchService([good, bad]).search("milk", "90034")

    assert [r.deal.name for r in response.results] == ["milk"]
    statuses = {s.source: s for s in response.sources}
    assert statuses["bad"].status == "error"
    assert "Public Key not found" in statuses["bad"].message
    assert statuses["good"].status == "ok"


def test_sale_only_filters_and_counts():
    src = FakeSource("s", [deal("s", "on sale", 2.0, 2.0, "lb", sale=True), deal("s", "full price", 1.0, 1.0, "lb")])
    response = SearchService([src]).search("x", "90034", sale_only=True)
    assert [r.deal.name for r in response.results] == ["on sale"]
    assert response.sources[0].result_count == 1


def test_skipped_sources_are_reported_and_message_passed_through():
    src = FakeSource("kroger", message="no Kroger-family stores within 10 miles")
    skipped = [SourceStatus(source="walmart", status="skipped", message="no keys")]
    response = SearchService([src], skipped=skipped).search("x", "94086")
    assert [(s.source, s.status, s.message) for s in response.sources] == [
        ("kroger", "ok", "no Kroger-family stores within 10 miles"),
        ("walmart", "skipped", "no keys"),
    ]


def test_close_closes_every_source():
    a, b = FakeSource("a"), FakeSource("b")
    SearchService([a, b]).close()
    assert a.closed and b.closed


EMPTY_SETTINGS = Settings(
    kroger_client_id="",
    kroger_client_secret="",
    walmart_consumer_id="",
    walmart_private_key_path=__import__("pathlib").Path("does-not-exist.pem"),
    walmart_key_version="1",
    walmart_publisher_id="",
)


def test_from_settings_without_keys_skips_both_sources():
    service = SearchService.from_settings(EMPTY_SETTINGS)
    assert service.source_names == []
    response = service.search("milk", "90034")
    assert {s.source: s.status for s in response.sources} == {"kroger": "skipped", "walmart": "skipped"}
    assert response.results == []


def test_demo_mode_uses_sample_source_and_flags_response():
    service = SearchService.from_settings(replace(EMPTY_SETTINGS, demo=True))
    response = service.search("apples", "90034")
    assert response.demo
    assert service.source_names == ["demo"]
    assert response.results, "sample data should have apples"
    assert all("sample data" in r.store.name for r in response.results)
    # Ranked: every $/lb result comes before anything priced another way
    bases = [r.deal.unit_basis for r in response.results]
    assert bases == sorted(bases, key=lambda b: {"lb": 0, "fl oz": 1, "each": 2, None: 3}[b])


@pytest.mark.parametrize(("term", "expected"), [("apples", True), ("whole milk", True), ("eggs", True), ("kale", False)])
def test_demo_matching(term, expected):
    assert bool(DemoSource().search(term, "90034", 25).deals) is expected
