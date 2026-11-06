"""Command-line entry point for trying the data sources by hand.

    aislescout stores 90034
    aislescout search 90034 "honeycrisp apples"
    aislescout walmart-keygen

`stores` and `search` use every source that has credentials in backend/.env and
skip the rest.
"""

from __future__ import annotations

import argparse
import sys

from aislescout.config import DEFAULT_KEYS_DIR, Settings, load_settings
from aislescout.models import Deal, Store
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
    if not _check_configured(settings):
        return 2
    deals: list[Deal] = []
    labels: dict[str, str] = {}

    if settings.kroger_configured:
        with _kroger(settings) as kroger:
            nearest = kroger.find_stores(args.zip, radius_miles=args.radius, limit=1)
            if nearest:
                store = nearest[0]
                labels[f"kroger:{store.store_id}"] = store.chain
                deals += kroger.search(args.term, store.store_id, limit=args.limit)
                print(f"Kroger family: {store.chain} {store.name} ({store.store_id})")
            else:
                print(f"Kroger family: no stores within {args.radius} miles of {args.zip}")
    if settings.walmart_configured:
        with _walmart(settings) as walmart:
            labels["walmart:online"] = "WALMART"
            deals += walmart.search(args.term, num_items=args.limit)
            print("Walmart: walmart.com online prices")

    if args.sale_only:
        deals = [d for d in deals if d.on_sale]
    # Group by unit basis ($/lb can't be compared with $/each), cheapest first.
    deals.sort(key=lambda d: (d.unit_price is None, d.unit_basis or "", d.unit_price or 0))
    print()
    for d in deals:
        store = labels.get(f"{d.source}:{d.store_id}", d.source.upper())
        tag = f"SALE -{d.savings_pct:.0f}%" if d.on_sale and d.savings_pct else ""
        print(f"{store:<10} ${d.price:>6.2f}  {_fmt_unit(d):>14}  {tag:<10} {d.name[:50]:<50} {d.size_text}")
    print(f"\n{len(deals)} results")
    return 0


def _cmd_walmart_keygen(args: argparse.Namespace) -> int:
    path, public_pem = generate_key_pair(DEFAULT_KEYS_DIR)
    print(f"Private key saved to {path} (gitignored; never share or commit it).\n")
    print("Upload this PUBLIC key to your app on walmart.io:\n")
    print(public_pem)
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
    p_search.add_argument("--radius", type=int, default=10, help="Kroger search radius in miles")
    p_search.add_argument("--limit", type=int, default=25, help="max results per source")
    p_search.add_argument("--sale-only", action="store_true")
    p_search.set_defaults(func=_cmd_search)

    p_keygen = sub.add_parser("walmart-keygen", help="Create the RSA key pair walmart.io asks for")
    p_keygen.set_defaults(func=_cmd_walmart_keygen)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KrogerError, WalmartError, ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
