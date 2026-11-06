"""Parse price tags from weekly ads: "$2.99", "2/$5", "2 for $5", "99¢", "$6.99 lb",
"member price", "Buy 1 Get 1 Free".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MULTI_RE = re.compile(r"(?P<n>\d+)\s*(?:/|for)\s*\$?\s*(?P<total>\d+(?:\.\d{1,2})?)", re.IGNORECASE)
_CENTS_RE = re.compile(r"(?P<c>\d+)\s*¢")
# A number not followed by "%" (so "Save 30%" isn't read as $30)
_DOLLARS_RE = re.compile(r"\$?\s*(?P<d>\d+(?:\.\d{1,2})?)(?![\d.]|\s*%)")
_PER_LB_RE = re.compile(r"(?:^|[\s/])(?:lb|lbs|pound)\b|per\s+(?:lb|pound)", re.IGNORECASE)
_MEMBER_RE = re.compile(r"member|club\s*price|with\s+(?:club\s+)?card|loyalty", re.IGNORECASE)
_BOGO_RE = re.compile(r"buy\s*(?:1|one)\s*,?\s*get\s*(?:1|one)\s*free|\bbogo\b|\bb1g1\b", re.IGNORECASE)


@dataclass(frozen=True)
class PriceTerms:
    """What a shopper actually pays for one purchase unit under this offer."""

    price: float  # effective price per item (or per lb when per_lb)
    min_quantity: int = 1  # must buy this many to get the price ("2 for $5" -> 2)
    per_lb: bool = False  # price is per pound, not per item
    member_only: bool = False  # needs a loyalty account
    bogo: bool = False


def parse_price_terms(
    price_text: str | None,
    pre_price_text: str | None = None,
    post_price_text: str | None = None,
    sale_story: str | None = None,
) -> PriceTerms | None:
    """Combine the pieces of a weekly-ad price tag into PriceTerms.

    Returns None when there's no concrete price (e.g. "Save 30%").
    """
    pre, core, post, story = (s or "" for s in (pre_price_text, price_text, post_price_text, sale_story))
    tag = f"{pre} {core}".strip()
    everything = f"{pre} {core} {post} {story}"

    member = bool(_MEMBER_RE.search(everything))
    per_lb = bool(_PER_LB_RE.search(post)) or bool(_PER_LB_RE.search(core))
    bogo = bool(_BOGO_RE.search(everything))

    if m := _MULTI_RE.search(tag):
        n = int(m.group("n"))
        total = float(m.group("total"))
        if n >= 1:
            return PriceTerms(round(total / n, 4), min_quantity=n, per_lb=per_lb, member_only=member)

    price: float | None = None
    if m := _CENTS_RE.search(core):
        price = int(m.group("c")) / 100
    elif m := _DOLLARS_RE.search(core):
        price = float(m.group("d"))
    if price is None or price <= 0:
        return None

    if bogo:
        return PriceTerms(round(price / 2, 4), min_quantity=2, per_lb=per_lb, member_only=member, bogo=True)
    return PriceTerms(price, per_lb=per_lb, member_only=member)
