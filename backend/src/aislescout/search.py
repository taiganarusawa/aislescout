"""Search every configured source in parallel and rank the combined results."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from aislescout.config import Settings
from aislescout.models import SearchResponse, SearchResult, SourceStatus, Store
from aislescout.sources.base import DealSource, KrogerSource, SourceResult, WalmartSource

log = logging.getLogger(__name__)

# $/lb, $/fl oz and $/each can't be compared with each other, so results are
# grouped by basis (in this order) and sorted by unit price inside each group.
_BASIS_ORDER = {"lb": 0, "fl oz": 1, "each": 2, None: 3}


def rank(results: list[SearchResult]) -> list[SearchResult]:
    return sorted(
        results,
        key=lambda r: (
            _BASIS_ORDER.get(r.deal.unit_basis, 3),
            r.deal.unit_price if r.deal.unit_price is not None else r.deal.price,
            r.deal.price,
        ),
    )


class SearchService:
    def __init__(self, sources: Sequence[DealSource], *, skipped: Sequence[SourceStatus] = (), demo: bool = False):
        self._sources = list(sources)
        self._skipped = list(skipped)
        self.demo = demo

    @classmethod
    def from_settings(cls, settings: Settings) -> SearchService:
        if settings.demo:
            from aislescout.sources.demo import DemoSource

            return cls([DemoSource()], demo=True)

        sources: list[DealSource] = []
        skipped: list[SourceStatus] = []
        if settings.kroger_configured:
            from aislescout.sources.kroger import KrogerClient

            sources.append(KrogerSource(KrogerClient(settings.kroger_client_id, settings.kroger_client_secret)))
        else:
            skipped.append(SourceStatus(source="kroger", status="skipped", message="no Kroger API keys in backend/.env"))
        if settings.walmart_configured:
            from aislescout.sources.walmart import WalmartClient

            client = WalmartClient(
                settings.walmart_consumer_id,
                settings.walmart_private_key_path.read_text(),
                key_version=settings.walmart_key_version,
                publisher_id=settings.walmart_publisher_id or None,
            )
            sources.append(WalmartSource(client))
        else:
            skipped.append(SourceStatus(source="walmart", status="skipped", message="no Walmart API keys in backend/.env"))
        return cls(sources, skipped=skipped)

    @property
    def source_names(self) -> list[str]:
        return [s.name for s in self._sources]

    def search(self, term: str, zip_code: str, *, limit: int = 25, sale_only: bool = False) -> SearchResponse:
        statuses: list[SourceStatus] = list(self._skipped)
        results: list[SearchResult] = []

        with ThreadPoolExecutor(max_workers=max(1, len(self._sources))) as pool:
            futures = [(s, pool.submit(s.search, term, zip_code, limit)) for s in self._sources]
            for source, future in futures:
                try:
                    outcome: SourceResult = future.result()
                except Exception as exc:  # one broken source must not break the whole search
                    log.warning("source %s failed: %s", source.name, exc)
                    statuses.append(SourceStatus(source=source.name, status="error", message=str(exc)[:300]))
                    continue
                found = _pair_with_stores(outcome)
                if sale_only:
                    found = [r for r in found if r.deal.on_sale]
                results.extend(found)
                statuses.append(
                    SourceStatus(source=source.name, status="ok", message=outcome.message, result_count=len(found))
                )

        return SearchResponse(
            query=term,
            zip_code=zip_code,
            sale_only=sale_only,
            demo=self.demo,
            results=rank(results),
            sources=sorted(statuses, key=lambda s: s.source),
        )

    def close(self) -> None:
        for source in self._sources:
            source.close()


def _pair_with_stores(outcome: SourceResult) -> list[SearchResult]:
    stores: dict[tuple[str, str], Store] = {(s.source, s.store_id): s for s in outcome.stores}
    paired = []
    for deal in outcome.deals:
        store = stores.get((deal.source, deal.store_id))
        if store is None:  # defensive: a source returned a deal for a store it didn't report
            store = Store(source=deal.source, store_id=deal.store_id, chain=deal.source.upper(), name=deal.source)
        paired.append(SearchResult(deal=deal, store=store))
    return paired
