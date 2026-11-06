"""Sample data for building and demoing the UI without API keys.

Store names are made up and every response is flagged `demo: true`, so sample
prices can't be mistaken for real ones. Enable with AISLESCOUT_DEMO=1 or
`aislescout serve --demo`.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from aislescout.models import Deal, Store
from aislescout.parsing import parse_quantity, unit_price
from aislescout.sources.base import SourceResult

SOURCE = "demo"

DEMO_STORES = [
    Store(source=SOURCE, store_id="demo-mart", chain="DEMO MART", name="Demo Mart (sample data)",
          address="100 Example St", city="Los Angeles", state="CA", zip_code="90034"),
    Store(source=SOURCE, store_id="sample-foods", chain="SAMPLE FOODS", name="Sample Foods (sample data)",
          address="200 Placeholder Ave", city="Los Angeles", state="CA", zip_code="90034"),
]

# (store_id, name, brand, size, regular, sale, sold_by, member_only, rating, reviews)
_ROWS: list[tuple[str, str, str, str, float, float | None, str, bool, float | None, int | None]] = [
    ("demo-mart", "Honeycrisp Apples, 3 lb Bag", "Fresh Farms", "3 lb", 5.99, 4.49, "unit", False, 4.5, 812),
    ("demo-mart", "Gala Apples", "Fresh Farms", "", 1.49, None, "weight", False, None, None),
    ("sample-foods", "Organic Fuji Apples, 2 lb Bag", "Green Valley", "2 lb", 4.99, None, "unit", False, 4.2, 96),
    ("sample-foods", "Granny Smith Apples", "", "", 1.99, 1.29, "weight", True, None, None),
    ("demo-mart", "Whole Milk, 1 Gallon", "Demo Mart", "1 gal", 3.79, None, "unit", False, 4.7, 2310),
    ("sample-foods", "Organic Whole Milk, Half Gallon", "Green Valley", "64 fl oz", 4.49, 3.99, "unit", False, 4.6, 540),
    ("sample-foods", "2% Reduced Fat Milk, 1 Gallon", "Sample Foods", "1 gal", 3.59, None, "unit", False, 4.5, 1022),
    ("demo-mart", "Large Grade A Eggs, 18 ct", "Demo Mart", "18 ct", 5.49, 4.79, "unit", False, 4.4, 1388),
    ("sample-foods", "Cage-Free Large Brown Eggs, 12 ct", "Green Valley", "12 ct", 4.99, None, "unit", False, 4.6, 377),
    ("demo-mart", "Bananas", "", "", 0.59, None, "weight", False, None, None),
    ("sample-foods", "Organic Bananas, 2 lb Bunch", "Green Valley", "2 lb", 1.99, None, "unit", False, 4.1, 64),
    ("demo-mart", "Boneless Skinless Chicken Breast", "Demo Mart", "", 4.99, 2.99, "weight", True, None, None),
    ("sample-foods", "Boneless Chicken Breast, Family Pack 3 lb", "Sample Foods", "3 lb", 11.97, 9.97, "unit", False, 4.3, 211),
    ("demo-mart", "Sourdough Bread, 24 oz", "Bakery Co", "24 oz", 4.29, None, "unit", False, 4.8, 154),
    ("sample-foods", "Whole Wheat Sandwich Bread, 20 oz", "Sample Foods", "20 oz", 2.99, 2.49, "unit", False, 4.2, 89),
]


def _matches(term: str, name: str) -> bool:
    words = [re.sub(r"(es|s)$", "", w) for w in re.findall(r"[a-z0-9]+", term.lower())]
    haystack = name.lower()
    return all(w in haystack for w in words if w)


class DemoSource:
    name = SOURCE

    def search(self, term: str, zip_code: str, limit: int) -> SourceResult:
        today = date.today()
        deals = []
        for i, (store_id, name, brand, size, regular, sale, sold_by, member, rating, reviews) in enumerate(_ROWS):
            if not _matches(term, name):
                continue
            price = sale if sale is not None else regular
            normalized = unit_price(price, parse_quantity(size) or parse_quantity(name), per_lb=sold_by == "weight")
            deals.append(
                Deal(
                    source=SOURCE,
                    store_id=store_id,
                    product_id=f"demo-{i}",
                    name=name,
                    brand=brand,
                    size_text=size,
                    sold_by=sold_by,  # type: ignore[arg-type]
                    regular_price=regular,
                    sale_price=sale,
                    price=price,
                    member_only=member,
                    unit_price=normalized[0] if normalized else None,
                    unit_basis=normalized[1] if normalized else None,
                    valid_from=today - timedelta(days=1) if sale is not None else None,
                    valid_to=today + timedelta(days=5) if sale is not None else None,
                    product_rating=rating,
                    review_count=reviews,
                )
            )
        return SourceResult(stores=DEMO_STORES, deals=deals[:limit])

    def close(self) -> None:
        pass
