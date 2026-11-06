"""Command-line entry point.

    aislescout stores 90034
    aislescout search 90034 "honeycrisp apples"
    aislescout search 90034 apples --demo
    aislescout serve [--demo]
    aislescout walmart-keygen

`stores` and `search` use every source that has credentials in backend/.env and
skip the rest.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace

from aislescout.config import DEFAULT_KEYS_DIR, Settings, load_settings
from aislescout.models import Deal, Store
from aislescout.search import SearchService
from aislescout.sources.kroger import KrogerClient, KrogerError
from aislescout.sources.walmart import WalmartClient, WalmartError, generate_key_pair


def _kroger(settings: Settings) -> KrogerClient:
    return KrogerClient(settings.kroger_client_id, settings.kroger_client_secret)


def _walmart(settings: Settings) -> WalmartClient:
    return WalmartClient(
        settings.walmart_consumer_id,
        settings.walmart_private_key_path.read_text(),
        key_version=settings.walmart_key_version,
        publisher_id=settings.walmart_publisher_id or None,
    )


def _check_configured(settings: Settings) -> bool:
    if not settings.kroger_configured:
        print("(skipping Kroger: set KROGER_CLIENT_ID / KROGER_CLIENT_SECRET in backend/.env)", file=sys.stderr)
    if not settings.walmart_configured:
        print("(skipping Walmart: set WALMART_CONSUMER_ID and create the key with `walmart-keygen`)", file=sys.stderr)
    if not (settings.kroger_configured or settings.walmart_configured):
        print("error: no data sources are configured (see backend/.env.example)", file=sys.stderr)
        return False
    return True


def _print_store(s: Store) -> None:
    print(f"{s.source:<8} {s.store_id:<10} {s.chain:<12} {s.name[:30]:<30} {s.address}, {s.city} {s.state}")


def _cmd_stores(args: argparse.Namespace) -> int:
    settings = load_settings()
    if not _check_configured(settings):
        return 2
    stores: list[Store] = []
    if settings.kroger_configured:
        with _kroger(settings) as kroger:
            stores += kroger.find_stores(args.zip, radius_miles=args.radius, limit=args.limit)
    if settings.walmart_configured:
        with _walmart(settings) as walmart:
            stores += walmart.find_stores(args.zip)[: args.limit]
    for s in stores:
        _print_store(s)
    print(f"\n{len(stores)} stores")
    return 0 if stores else 1


def _fmt_unit(d: Deal) -> str:
    return f"${d.unit_price:.2f}/{d.unit_basis}" if d.unit_price is not None else "n/a"


def _cmd_search(args: argparse.Namespace) -> int:
    settings = load_settings()
    if args.demo:
        settings = replace(settings, demo=True)
    elif not _check_configured(settings):
        return 2
    service = SearchService.from_settings(settings)
    try:
        response = service.search(args.term, args.zip, limit=args.limit, sale_only=args.sale_only)
    finally:
        service.close()

    if response.demo:
        print("SAMPLE DATA: these are made-up prices for testing, not real deals.\n")
    for status in response.sources:
        detail = f" ({status.message})" if status.message else ""
        print(f"{status.source:<8} {status.status:<8} {status.result_count:>3} results{detail}")
    print()
    for r in response.results:
        d = r.deal
        tag = f"SALE -{d.savings_pct:.0f}%" if d.on_sale and d.savings_pct else ""
        print(f"{r.store.chain[:12]:<12} ${d.price:>6.2f}  {_fmt_unit(d):>14}  {tag:<10} {d.name[:50]:<50} {d.size_text}")
    print(f"\n{len(response.results)} results")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.demo:
        os.environ["AISLESCOUT_DEMO"] = "1"
    print(f"AisleScout API on http://{args.host}:{args.port}  (docs at /docs){'  [SAMPLE DATA]' if args.demo else ''}")
    uvicorn.run("aislescout.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_walmart_keygen(args: argparse.Namespace) -> int:
    path, public_pem = generate_key_pair(DEFAULT_KEYS_DIR, args.file)
    # walmart.io's key-upload form wants only the base64 body, without the
    # "-----BEGIN/END PUBLIC KEY-----" lines (https://walmart.io/key-tutorial).
    body = "\n".join(line for line in public_pem.strip().splitlines() if not line.startswith("-----"))
    print(f"Private key saved to {path} (gitignored; never share or commit it).\n")
    print("Paste this PUBLIC key into walmart.io's key-upload page (environment: PRODUCTION):\n")
    print(body)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aislescout", description="Find grocery deals.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stores = sub.add_parser("stores", help="List stores near a zip code from every configured source")
    p_stores.add_argument("zip")
    p_stores.add_argument("--radius", type=int, default=10, help="Kroger search radius in miles")
    p_stores.add_argument("--limit", type=int, default=10, help="max stores per source")
    p_stores.set_defaults(func=_cmd_stores)

    p_search = sub.add_parser("search", help="Search every configured source and rank by unit price")
    p_search.add_argument("zip")
    p_search.add_argument("term")
    p_search.add_argument("--limit", type=int, default=25, help="max results per source")
    p_search.add_argument("--sale-only", action="store_true")
    p_search.add_argument("--demo", action="store_true", help="use made-up sample data instead of real APIs")
    p_search.set_defaults(func=_cmd_search)

    p_serve = sub.add_parser("serve", help="Run the HTTP API for the web app")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    p_serve.add_argument("--demo", action="store_true", help="serve made-up sample data instead of real APIs")
    p_serve.set_defaults(func=_cmd_serve)

    p_keygen = sub.add_parser("walmart-keygen", help="Create the RSA key pair walmart.io asks for")
    p_keygen.add_argument(
        "--file",
        default="walmart_private_key.pem",
        help="private key file name inside backend/keys/ (point WALMART_PRIVATE_KEY_PATH at it if not the default)",
    )
    p_keygen.set_defaults(func=_cmd_walmart_keygen)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KrogerError, WalmartError, ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
