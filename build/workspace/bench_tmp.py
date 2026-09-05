import timeit

from inventory import Inventory


class OldInventory(Inventory):
    def add(self, sku, qty, unit_price):
        if sku in self._items:
            self._items[sku]["qty"] += qty
        else:
            self._items[sku] = {"qty": qty, "unit_price": unit_price}

    def remove(self, sku, qty):
        if sku not in self._items:
            raise KeyError(f"unknown sku: {sku!r}")
        if qty < 0:
            raise ValueError(f"cannot remove a negative quantity: {qty}")
        if qty > self._items[sku]["qty"]:
            raise ValueError(
                f"cannot remove {qty} of {sku}: only {self._items[sku]['qty']} in stock"
            )
        self._items[sku]["qty"] -= qty

    def apply_discount(self, sku, percent):
        if sku not in self._items:
            raise KeyError(f"unknown sku: {sku!r}")
        self._items[sku]["unit_price"] *= (100 - percent) / 100


def make(cls, n=1000):
    inv = cls()
    for i in range(n):
        inv.add(f"SKU{i}", 5, 10.0)
    return inv


def work(inv):
    inv.remove("SKU5", 1)
    inv.add("SKU5", 1, 10.0)
    inv.apply_discount("SKU5", 1)
    inv.apply_discount("SKU5", 0)


old_inv = make(OldInventory)
new_inv = make(Inventory)

best = {"old": float("inf"), "new": float("inf")}
for round_no in range(5):
    for name, inv in [("old", old_inv), ("new", new_inv)]:
        t = timeit.timeit(lambda: work(inv), number=50000)
        best[name] = min(best[name], t)
        print(f"round {round_no} {name}: {t:.4f}s")
print("best old:", round(best["old"], 4), " best new:", round(best["new"], 4))
print("speedup: {:.0%}".format(best["old"] / best["new"] - 1))