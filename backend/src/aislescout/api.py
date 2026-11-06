"""HTTP API for the web app.

    aislescout serve            # http://127.0.0.1:8000/docs
    aislescout serve --demo     # sample data, no API keys needed
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from aislescout import __version__
from aislescout.config import BACKEND_DIR, load_settings
from aislescout.models import SearchResponse
from aislescout.search import SearchService

ServiceFactory = Callable[[], SearchService]


def _default_service() -> SearchService:
    return SearchService.from_settings(load_settings())


def create_app(service_factory: ServiceFactory = _default_service) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One service (and one HTTP client per source) for the app's lifetime, so
        # Kroger's access token and connection pools are reused across requests.
        app.state.search = service_factory()
        try:
            yield
        finally:
            app.state.search.close()

    app = FastAPI(title="AisleScout API", version=__version__, lifespan=lifespan)
    load_dotenv(BACKEND_DIR / ".env")  # so AISLESCOUT_CORS_ORIGINS in .env is seen here
    raw_origins = os.environ.get("AISLESCOUT_CORS_ORIGINS") or "http://localhost:3000"
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        service: SearchService = request.app.state.search
        return {"status": "ok", "sources": service.source_names, "demo": service.demo}

    @app.get("/api/search", response_model=SearchResponse)
    def search(
        request: Request,
        q: Annotated[str, Query(min_length=3, max_length=80, description="What to search for, e.g. 'apples'")],
        zip: Annotated[str, Query(pattern=r"^\d{5}$", description="5-digit US zip code")],
        sale_only: bool = False,
        limit: Annotated[int, Query(ge=1, le=50, description="Max results per source")] = 25,
    ) -> SearchResponse:
        # Plain `def` (not async): sources use blocking HTTP clients, so FastAPI runs
        # this in its threadpool instead of blocking the event loop.
        service: SearchService = request.app.state.search
        return service.search(q.strip(), zip, limit=limit, sale_only=sale_only)

    return app


app = create_app()
