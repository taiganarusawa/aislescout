"""Parse package sizes like "12 oz", "1 gal", "6 ct / 16.9 fl oz", "10 to 12-oz. Bag".

Everything is converted to a base unit per dimension so sizes can be compared:
weight -> ounces, volume -> fluid ounces, count -> each.

This is the deterministic first pass. Text it can't handle returns None, and a
later LLM fallback can deal with those cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Dimension(StrEnum):
    WEIGHT = "weight"  # base unit: oz
    VOLUME = "volume"  # base unit: fl oz
    COUNT = "count"  # base unit: each


@dataclass(frozen=True)
class Quantity:
    dimension: Dimension
    amount: float  # in base units; the low end if the text gave a range
    amount_max: float | None = None  # high end of a range ("10 to 12 oz"), else None

    @property
    def is_range(self) -> bool:
        return self.amount_max is not None and self.amount_max != self.amount


# (regex, dimension, factor to base unit). Order matters: longer/more specific first.
_UNITS: list[tuple[str, Dimension, float]] = [
    (r"fl\.?\s*oz\.?|fluid\s+ounces?", Dimension.VOLUME, 1.0),
    (r"gal\.?|gallons?", Dimension.VOLUME, 128.0),
    (r"qt\.?|quarts?", Dimension.VOLUME, 32.0),
    (r"pt\.?|pints?", Dimension.VOLUME, 16.0),
    (r"ml|milliliters?|millilitres?", Dimension.VOLUME, 0.033814),
    (r"l|liters?|litres?|ltr", Dimension.VOLUME, 33.814),
    (r"oz\.?|ounces?", Dimension.WEIGHT, 1.0),
    (r"lbs?\.?|pounds?", Dimension.WEIGHT, 16.0),
    (r"kg|kilograms?", Dimension.WEIGHT, 35.274),
    (r"g|gm|grams?", Dimension.WEIGHT, 0.035274),
    (r"ct\.?|count|pk\.?|pack|packs|each|ea\.?|pcs?\.?|pieces?", Dimension.COUNT, 1.0),
]

_NUM = r"\d+(?:\.\d+)?|\.\d+"
_UNIT_ALT = "|".join(f"(?:{pattern})" for pattern, _, _ in _UNITS)
# "12 oz", "12-oz.", "10 to 12-oz", "10-12 oz", "16.9fl oz"
_MEASURE_RE = re.compile(
    rf"(?P<num>{_NUM})(?:\s*(?:to|-|–)\s*(?P<num2>{_NUM}))?\s*-?\s*(?P<unit>{_UNIT_ALT})(?![a-z])",
    re.IGNORECASE,
)
# "6 x 12 oz", "6 × 12 fl oz"
_MULTIPLIER_RE = re.compile(rf"(?P<n>\d+)\s*[x×]\s*(?=(?:{_NUM}))", re.IGNORECASE)


def _unit_info(unit_text: str) -> tuple[Dimension, float]:
    for pattern, dim, factor in _UNITS:
        if re.fullmatch(pattern, unit_text.strip(), re.IGNORECASE):
            return dim, factor
    raise ValueError(f"unknown unit: {unit_text!r}")  # unreachable if regexes agree


@dataclass(frozen=True)
class _Measure:
    dimension: Dimension
    low: float
    high: float | None
    start: int


def _measures(text: str) -> list[_Measure]:
    found: list[_Measure] = []
    for m in _MEASURE_RE.finditer(text):
        dim, factor = _unit_info(m.group("unit"))
        low = float(m.group("num")) * factor
        high = float(m.group("num2")) * factor if m.group("num2") else None
        if high is not None and high < low:  # "12-10 oz" typo; keep it ordered
            low, high = high, low
        found.append(_Measure(dim, low, high, m.start()))
    return found


def parse_quantity(text: str | None) -> Quantity | None:
    """Parse a package-size string into a Quantity, or None if no size was found.

    Weight/volume beats count, and a count next to a weight/volume is treated as a
    multipack ("6 ct / 16.9 fl oz" = 6 x 16.9 fl oz).
    """
    if not text:
        return None
    measures = _measures(text)
    if not measures:
        return None

    sized = [m for m in measures if m.dimension is not Dimension.COUNT]
    counts = [m for m in measures if m.dimension is Dimension.COUNT]

    if not sized:
        c = counts[0]
        return Quantity(Dimension.COUNT, c.low, c.high)

    first = sized[0]
    multiplier = 1.0

    # "6 x 12 oz": an explicit multiplier right before the size
    mult = _MULTIPLIER_RE.search(text)
    if mult and mult.end() <= first.start + 1:
        multiplier = float(mult.group("n"))
    # "6 ct / 16.9 fl oz" or "12 pk 12 oz": a count *before* the size is a multipack.
    # A count after the size ("3 lb bag, about 12 ct") just describes the contents.
    elif counts and counts[0].start < first.start and counts[0].high is None and counts[0].low > 1:
        multiplier = counts[0].low

    high = first.high * multiplier if first.high is not None else None
    return Quantity(first.dimension, first.low * multiplier, high)
