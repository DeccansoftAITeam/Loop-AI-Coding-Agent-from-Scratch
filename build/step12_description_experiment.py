"""Step 12 - does the description actually change behavior?

Same task, same model, same system prompt. Only one tool description differs.
"""

import copy

from config import MODEL
from filetools import ROOT
import step09_full_agent
from step11_traced_agent import run_agent

TASK = (
    "The remove() method should reject removing more than the current stock. "
    "Change it so it raises ValueError in that case, and add a test."
)

ORIGINAL = copy.deepcopy(step09_full_agent.TOOLS)


def set_description(tool_name: str, text: str) -> None:
    """Mutate the shared TOOLS list that run_agent imports."""
    for tool in step09_full_agent.TOOLS:
        if tool["name"] == tool_name:
            tool["description"] = text
            return
    raise SystemExit(f"no such tool: {tool_name}")


def restore() -> None:
    step09_full_agent.TOOLS[:] = copy.deepcopy(ORIGINAL)


def reset_workspace() -> None:
    """Every run must start from identical files or the comparison is noise."""
    (ROOT / "inventory.py").write_text(
        '"""A small module with one bug and one missing feature."""\n\n\n'
        "class Inventory:\n"
        "    def __init__(self):\n"
        "        self._items = {}\n\n"
        "    def add(self, sku, qty, unit_price):\n"
        "        if sku in self._items:\n"
        '            self._items[sku]["qty"] += qty\n'
        "        else:\n"
        '            self._items[sku] = {"qty": qty, "unit_price": unit_price}\n\n'
        "    def remove(self, sku, qty):\n"
        '        self._items[sku]["qty"] -= qty\n\n'
        "    def total_value(self):\n"
        '        return sum(i["qty"] * i["unit_price"] for i in self._items.values())\n',
        encoding="utf-8",
    )
    (ROOT / "test_inventory.py").write_text(
        "from inventory import Inventory\n\n\n"
        "def test_add_and_total():\n"
        "    inv = Inventory()\n"
        '    inv.add("A1", 3, 10.0)\n'
        '    inv.add("A1", 2, 10.0)\n'
        "    assert inv.total_value() == 50.0\n",
        encoding="utf-8",
    )


def trial(label: str) -> None:
    reset_workspace()
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    _, trace = run_agent(TASK, verbose=False)
    print(trace.summary())


if __name__ == "__main__":
    print(f"model: {MODEL}")

    # --- A: the good description -------------------------------------------
    restore()
    trial("A - full edit_file description")

    # --- B: gutted to one line ---------------------------------------------
    set_description("edit_file", "Edits a file.")
    trial("B - edit_file description gutted to 'Edits a file.'")

    # --- C: an explicit prohibition ----------------------------------------
    restore()
    set_description(
        "edit_file",
        "DEPRECATED. Do not use this tool. Use write_file instead for all changes.",
    )
    trial("C - edit_file marked deprecated")

    # --- D: a description of a completely different tool -------------------
    restore()
    set_description(
        "edit_file",
        "Send an email to a colleague. Provide the recipient and the message body.",
    )
    trial("D - edit_file described as an email tool")

    restore()
    print(
        "\nCompare: turns, tool mix, errors, tokens.\n"
        "Did B fall back to write_file? Did it take more turns?\n"
        "Which condition changed the TOOL MIX rather than just the turn count?"
    )