"""Normalize a price to a comparable unit: $/lb, $/fl oz, or $/each."""

from __future__ import annotations

from aislescout.models import UnitBasis
from aislescout.parsing.quantity import Dimension, Quantity

_OZ_PER_LB = 16.0


def unit_price(
    price: float, quantity: Quantity | None, *, per_lb: bool = False
) -> tuple[float, UnitBasis] | None:
    """Return (price per unit, basis), or None when the size is unknown.

    For a size range ("10 to 12 oz") the low end is used, so the unit price is
    conservative (it never looks better than the worst case).
    """
    if per_lb:
        return round(price, 4), "lb"
    if quantity is None or quantity.amount <= 0:
        return None
    if quantity.dimension is Dimension.WEIGHT:
        return round(price / (quantity.amount / _OZ_PER_LB), 4), "lb"
    if quantity.dimension is Dimension.VOLUME:
        return round(price / quantity.amount, 4), "fl oz"
    return round(price / quantity.amount, 4), "each"
