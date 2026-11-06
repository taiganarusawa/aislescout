import pytest

from aislescout.parsing import parse_price_terms, parse_quantity, unit_price


def test_plain_price():
    t = parse_price_terms("2.99")
    assert t is not None
    assert t.price == 2.99
    assert t.min_quantity == 1
    assert not t.per_lb and not t.member_only


@pytest.mark.parametrize(
    ("pre", "core", "price", "n"),
    [
        ("", "2/$5", 2.5, 2),
        ("2/", "5.00", 2.5, 2),
        ("", "2 for $5", 2.5, 2),
        ("10 for", "$10", 1.0, 10),
    ],
)
def test_multi_buy(pre, core, price, n):
    t = parse_price_terms(core, pre_price_text=pre)
    assert t is not None
    assert t.price == pytest.approx(price)
    assert t.min_quantity == n


def test_cents():
    t = parse_price_terms("99¢")
    assert t is not None
    assert t.price == 0.99


def test_real_safeway_per_lb_member_price():
    # USDA Choice Boneless Beef Top Sirloin Steak: "6.99" + "lb member price"
    t = parse_price_terms("6.99", post_price_text="lb member price")
    assert t is not None
    assert t.price == 6.99
    assert t.per_lb
    assert t.member_only


def test_real_safeway_each_member_price():
    t = parse_price_terms("5.00", post_price_text="ea member price")
    assert t is not None
    assert not t.per_lb
    assert t.member_only


def test_bogo_halves_price():
    t = parse_price_terms("4.00", sale_story="Buy 1 Get 1 FREE")
    assert t is not None
    assert t.bogo
    assert t.price == 2.0
    assert t.min_quantity == 2


@pytest.mark.parametrize("core", ["", "Save 30%", "25 % off"])
def test_no_concrete_price(core):
    assert parse_price_terms(core) is None


def test_unit_price_weight_is_per_lb():
    assert unit_price(3.0, parse_quantity("12 oz")) == (4.0, "lb")


def test_unit_price_volume_is_per_fl_oz():
    assert unit_price(3.84, parse_quantity("1 gal")) == (0.03, "fl oz")


def test_unit_price_count_is_each():
    assert unit_price(4.5, parse_quantity("18 ct")) == (0.25, "each")


def test_unit_price_per_lb_flag_wins():
    assert unit_price(1.29, None, per_lb=True) == (1.29, "lb")


def test_unit_price_range_uses_low_end():
    # Starbucks 7.99 for "10 to 12-oz": worst case is 10 oz -> $12.784/lb
    price, basis = unit_price(7.99, parse_quantity("10 to 12-oz. Bag"))
    assert basis == "lb"
    assert price == pytest.approx(12.784)


def test_unit_price_unknown_size():
    assert unit_price(2.0, None) is None
