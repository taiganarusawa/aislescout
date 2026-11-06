"""Command-line entry point for trying the data sources by hand.

    aislescout stores 90034
    aislescout search 90034 "honeycrisp apples"
"""

from __future__ import annotations

import argparse
import sys

from aislescout.config import load_settings
from aislescout.models import Deal
from aislescout.sources.kroger import KrogerClient, KrogerError


def _kroger() -> KrogerClient:
    settings = load_settings()
    return KrogerClient(settings.kroger_client_id, settings.kroger_client_secret)


def _cmd_stores(args: argparse.Namespace) -> int:
    with _kroger() as kroger:
        stores = kroger.find_stores(args.zip, radius_miles=args.radius, limit=args.limit, chain=args.chain)
    if not stores:
        print(f"No Kroger-family stores within {args.radius} miles of {args.zip}.")
        return 1
    for s in stores:
        print(f"{s.store_id}  {s.chain:<12} {s.name:<35} {s.address}, {s.city} {s.state}")
    return 0


def _fmt_unit(d: Deal) -> str:
    return f"${d.unit_price:.2f}/{d.unit_basis}" if d.unit_price is not None else "n/a"


def _cmd_search(args: argparse.Namespace) -> int:
    with _kroger() as kroger:
        store_id = args.store
        if not store_id:
            nearest = kroger.find_stores(args.zip, radius_miles=args.radius, limit=1)
            if not nearest:
                print(f"No Kroger-family stores within {args.radius} miles of {args.zip}.")
                return 1
            store_id = nearest[0].store_id
            print(f"Using {nearest[0].chain} {nearest[0].name} ({store_id})\n")
        deals = kroger.search(args.term, store_id, limit=args.limit)

    if args.sale_only:
        deals = [d for d in deals if d.on_sale]
    deals.sort(key=lambda d: (d.unit_price is None, d.unit_basis or "", d.unit_price or 0))
    for d in deals:
        tag = f"SALE -{d.savings_pct:.0f}%" if d.on_sale and d.savings_pct else ""
        print(f"${d.price:>6.2f}  {_fmt_unit(d):>14}  {tag:<10} {d.name[:55]:<55} {d.size_text}")
    print(f"\n{len(deals)} results")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aislescout", description="Find grocery deals.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stores = sub.add_parser("stores", help="List Kroger-family stores near a zip code")
    p_stores.add_argument("zip")
    p_stores.add_argument("--radius", type=int, default=10)
    p_stores.add_argument("--limit", type=int, default=10)
    p_stores.add_argument("--chain", help="e.g. RALPHS")
    p_stores.set_defaults(func=_cmd_stores)

    p_search = sub.add_parser("search", help="Search products at the nearest (or given) Kroger-family store")
    p_search.add_argument("zip")
    p_search.add_argument("term")
    p_search.add_argument("--store", help="Kroger locationId (default: nearest store)")
    p_search.add_argument("--radius", type=int, default=10)
    p_search.add_argument("--limit", type=int, default=50)
    p_search.add_argument("--sale-only", action="store_true")
    p_search.set_defaults(func=_cmd_search)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KrogerError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
