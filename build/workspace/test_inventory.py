import pytest

from inventory import Inventory


def test_add_and_total():
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    inv.add("A1", 2, 10.0)
    assert inv.total_value() == 50.0


def test_remove_within_stock():
    inv = Inventory()
    inv.add("A1", 5, 10.0)
    inv.remove("A1", 2)
    assert inv._items["A1"]["qty"] == 3


def test_remove_more_than_stock_raises():
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    with pytest.raises(ValueError):
        inv.remove("A1", 4)
    assert inv._items["A1"]["qty"] == 3  # stock unchanged after failed remove


@pytest.mark.parametrize("bad", [-1, -100])
def test_remove_negative_qty_raises(bad):
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    with pytest.raises(ValueError):
        inv.remove("A1", bad)
    assert inv._items["A1"]["qty"] == 3  # stock unchanged after failed remove


def test_remove_unknown_sku_raises_keyerror_with_message():
    inv = Inventory()
    with pytest.raises(KeyError, match="unknown sku: 'NOPE'"):
        inv.remove("NOPE", 1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_remove_non_finite_qty_raises(bad):
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    with pytest.raises(ValueError):
        inv.remove("A1", bad)
    assert inv._items["A1"]["qty"] == 3  # stock unchanged after failed remove


@pytest.mark.parametrize("bad", ["2", None, 2.5j, True])
def test_remove_non_numeric_qty_raises(bad):
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    with pytest.raises(TypeError):
        inv.remove("A1", bad)
    assert inv._items["A1"]["qty"] == 3  # stock unchanged after failed remove


def test_apply_discount_reduces_unit_price():
    inv = Inventory()
    inv.add("A1", 2, 20.0)
    inv.apply_discount("A1", 25)
    assert inv._items["A1"]["unit_price"] == pytest.approx(15.0)
    assert inv.total_value() == pytest.approx(30.0)


def test_apply_discount_only_affects_target_sku():
    inv = Inventory()
    inv.add("A1", 1, 10.0)
    inv.add("B2", 1, 10.0)
    inv.apply_discount("A1", 50)
    assert inv._items["A1"]["unit_price"] == pytest.approx(5.0)
    assert inv._items["B2"]["unit_price"] == pytest.approx(10.0)


def test_apply_discount_zero_and_hundred():
    inv = Inventory()
    inv.add("A1", 1, 10.0)
    inv.add("B2", 1, 10.0)
    inv.apply_discount("A1", 0)
    inv.apply_discount("B2", 100)
    assert inv._items["A1"]["unit_price"] == pytest.approx(10.0)
    assert inv._items["B2"]["unit_price"] == pytest.approx(0.0)


def test_apply_discount_unknown_sku_raises():
    inv = Inventory()
    inv.add("A1", 1, 10.0)
    with pytest.raises(KeyError):
        inv.apply_discount("NOPE", 10)


@pytest.mark.parametrize("bad", [-1, 101, 150])
def test_apply_discount_out_of_range_raises(bad):
    inv = Inventory()
    inv.add("A1", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("A1", bad)
    assert inv._items["A1"]["unit_price"] == 10.0  # price unchanged after failure


@pytest.mark.parametrize("bad", ["10", None, 10.5j, True])
def test_apply_discount_non_numeric_raises(bad):
    inv = Inventory()
    inv.add("A1", 1, 10.0)
    with pytest.raises(TypeError):
        inv.apply_discount("A1", bad)
    assert inv._items["A1"]["unit_price"] == 10.0  # price unchanged after failure


def test_add_negative_qty_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add("A1", -2, 10.0)
    assert "A1" not in inv._items


def test_add_negative_qty_to_existing_sku_raises():
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    with pytest.raises(ValueError):
        inv.add("A1", -2, 10.0)
    assert inv._items["A1"]["qty"] == 3  # stock unchanged after failed add


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_add_non_finite_qty_raises(bad):
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add("A1", bad, 10.0)
    assert "A1" not in inv._items


@pytest.mark.parametrize("bad", ["3", None, 2.5j, True])
def test_add_non_numeric_qty_raises(bad):
    inv = Inventory()
    with pytest.raises(TypeError):
        inv.add("A1", bad, 10.0)
    assert "A1" not in inv._items
