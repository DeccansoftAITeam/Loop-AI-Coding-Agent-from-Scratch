"""A small module with one bug and one missing feature."""
import math


class Inventory:
    def __init__(self):
        self._items = {}

    def add(self, sku, qty, unit_price):
        if isinstance(qty, bool) or not isinstance(qty, (int, float)):
            raise TypeError(f"qty must be a number, got {type(qty).__name__}")
        if not math.isfinite(qty):
            raise ValueError(f"qty must be finite, got {qty}")
        if qty < 0:
            raise ValueError(f"cannot add a negative quantity: {qty}")
        item = self._items.get(sku)
        if item is None:
            self._items[sku] = {"qty": qty, "unit_price": unit_price}
        else:
            item["qty"] += qty

    def remove(self, sku, qty):
        if isinstance(qty, bool) or not isinstance(qty, (int, float)):
            raise TypeError(f"qty must be a number, got {type(qty).__name__}")
        if not math.isfinite(qty):
            raise ValueError(f"qty must be finite, got {qty}")
        try:
            item = self._items[sku]
        except KeyError:
            raise KeyError(f"unknown sku: {sku!r}") from None
        if qty < 0:
            raise ValueError(f"cannot remove a negative quantity: {qty}")
        if qty > item["qty"]:
            raise ValueError(
                f"cannot remove {qty} of {sku}: only {item['qty']} in stock"
            )
        item["qty"] -= qty

    def apply_discount(self, sku, percent):
        """Reduce the unit price of `sku` by `percent` percent."""
        if sku not in self._items:
            raise KeyError(f"unknown sku: {sku!r}")
        if isinstance(percent, bool) or not isinstance(percent, (int, float)):
            raise TypeError(
                f"percent must be a number, got {type(percent).__name__}"
            )
        if not 0 <= percent <= 100:
            raise ValueError(f"percent must be between 0 and 100, got {percent}")
        item = self._items[sku]
        item["unit_price"] *= (100 - percent) / 100

    def total_value(self):
        return sum(i["qty"] * i["unit_price"] for i in self._items.values())
