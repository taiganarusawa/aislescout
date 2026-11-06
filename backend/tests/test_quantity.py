import pytest

from aislescout.parsing import Dimension, parse_quantity


@pytest.mark.parametrize(
    ("text", "dimension", "amount"),
    [
        ("12 oz", Dimension.WEIGHT, 12),
        ("11.7-oz.", Dimension.WEIGHT, 11.7),
        ("1 lb", Dimension.WEIGHT, 16),
        ("3 lbs", Dimension.WEIGHT, 48),
        ("2 Pounds", Dimension.WEIGHT, 32),
        ("500 g", Dimension.WEIGHT, 500 * 0.035274),
        ("1 gal", Dimension.VOLUME, 128),
        ("0.5 gal", Dimension.VOLUME, 64),
        ("64 fl oz", Dimension.VOLUME, 64),
        ("16.9fl oz", Dimension.VOLUME, 16.9),
        ("2 L", Dimension.VOLUME, 2 * 33.814),
        ("1 qt", Dimension.VOLUME, 32),
        ("18 ct", Dimension.COUNT, 18),
        ("each", None, None),  # no number -> no quantity
    ],
)
def test_simple_sizes(text, dimension, amount):
    q = parse_quantity(text)
    if dimension is None:
        assert q is None
        return
    assert q is not None
    assert q.dimension is dimension
    assert q.amount == pytest.approx(amount)
    assert not q.is_range


def test_range_keeps_low_and_high():
    # Real Safeway weekly-ad text
    q = parse_quantity("10 to 12-oz. Bag or 10 - 15 K-Cups, Selected varieties")
    assert q is not None
    assert q.dimension is Dimension.WEIGHT
    assert q.amount == 10
    assert q.amount_max == 12
    assert q.is_range


@pytest.mark.parametrize(
    ("text", "dimension", "amount"),
    [
        ("6 ct / 16.9 fl oz", Dimension.VOLUME, 6 * 16.9),
        ("12 pk 12 fl oz", Dimension.VOLUME, 144),
        ("6 x 12 oz", Dimension.WEIGHT, 72),
        ("4 × 6 oz", Dimension.WEIGHT, 24),
    ],
)
def test_multipacks(text, dimension, amount):
    q = parse_quantity(text)
    assert q is not None
    assert q.dimension is dimension
    assert q.amount == pytest.approx(amount)


def test_count_after_size_is_not_a_multiplier():
    q = parse_quantity("3 lb bag, about 12 ct")
    assert q is not None
    assert q.amount == 48


def test_weight_beats_count_and_first_size_wins():
    q = parse_quantity("1 lb (16 oz)")
    assert q is not None
    assert q.amount == 16


@pytest.mark.parametrize("text", ["", None, "Selected varieties.", "Limit 4-pkgs.", "Large"])
def test_no_size(text):
    assert parse_quantity(text) is None
