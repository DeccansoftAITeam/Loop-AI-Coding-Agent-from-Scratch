# Part 4 — Production Concerns

**Steps 10–12 · about 60 minutes**

Your agent works. This part is about the difference between *works* and *good*, which is where almost all the real engineering lives.

Three things: a behavioral contract, instrumentation, and evidence for a design claim you have been taking on trust since Step 8.

---

## Step 10 — The system prompt

### Theory

Everything so far has run with **no system prompt at all**. The agent's behavior has been whatever the model does by default. That works for a demo. It is not a product.

The system prompt is the behavioral contract. In a production coding agent it typically has six sections:

| Section | What it carries |
|---|---|
| **Identity and scope** | One or two sentences. What this agent is, and is not. |
| **How to work** | The largest section, and the one doing the most work. |
| **Tool-use policy** | When to prefer which tool. Mechanics live in the tool descriptions. |
| **Communication style** | What the user sees between tool calls. Badly underrated. |
| **Safety boundaries** | What it will not do regardless of instruction. |
| **Environment context** | Injected, not authored: OS, cwd, git state. |

When you read a real one, play this game with the "how to work" section: for each rule, ask *what did the model do, in front of a user, that made someone write this sentence?* Nearly every line is a mitigation for an observed failure. "Read before you edit" is not style advice — it is the stale-context failure, encoded.

**Three principles that govern how to write these.**

**Emphasis is a scarce resource, and it inflates.** Prompts written for older, less steerable models are full of `CRITICAL:` and `You MUST`. Current models follow the system prompt closely, so that language now *over*-applies — you get tools fired when they should not be, and rigid behavior where you wanted judgment. When five instructions are all marked critical, none of them are.

**Give the reason, not just the rule.** `Run the tests after editing` versus `Run the tests after editing, because a plausible-looking diff that does not compile is worse than no diff — the user will trust it.` The second generalizes to situations you did not enumerate. The first does not.

**Context is never cruft; instructions often are.** Apply the deletion test to every line: *could the model already know this?* "Be accurate and thorough" is a restatement of a trained default — dead weight. Your environment, your quality bar, your constraints and their reasons — that is the whole value of the prompt, and it is what beginners leave out.

### Code

`code/build/step10_system_prompt.py`

```python
"""Step 10 - give the agent a behavioral contract."""

from config import client, MODEL
import filetools
from filetools import ROOT, ToolError
from step09_full_agent import TOOLS, HANDLERS, run_tool

MAX_TURNS = 20

SYSTEM_PROMPT = """\
You are a coding agent working inside a single workspace directory.

<workspace>
All paths are relative to the workspace root. You cannot read or write
anything outside it; attempts will fail with an error.
</workspace>

<how_to_work>
Read before you edit. Your memory of a file is not evidence about its current
contents - read_file is. When a task touches code you have not seen, find it
first, read the relevant part, then change it.

Prefer edit_file over write_file for existing files. A failed edit tells you
your assumptions are stale; a successful write_file can silently destroy work.

Verify your own changes. If the project has tests, run them with bash after you
edit. Report what the output actually said - if it failed, say so and show it.
Never claim something works because it looks correct.

Deliver what was asked, at the scope intended. If you think the request is
mistaken or a better approach exists, say so in a sentence and continue with
the task as asked - do not quietly widen it.

Finish the whole task before you stop. If part is genuinely blocked, complete
everything else and state plainly what is left and why.
</how_to_work>

<communication>
The user sees your text between tool calls, not your reasoning and not the raw
tool output. Before your first tool call, say in one sentence what you are
about to do. Speak up when you find something load-bearing or change direction.
When you finish, lead with the outcome in one sentence, then the detail.
</communication>
"""


def run_agent(task: str, system: str = SYSTEM_PROMPT) -> str:
    messages = [{"role": "user", "content": task}]

    for turn in range(1, MAX_TURNS + 1):
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            # An empty string means "no system prompt", not "an empty one" -
            # some providers reject a text block with no text in it. The
            # `Try this` below depends on this line.
            system=[{"type": "text", "text": system}] if system else None,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content})

        text = "".join(b.text for b in response.content if b.type == "text")
        if text.strip():
            print(f"\n{text.strip()}\n")

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return text

        results = []
        for tu in tool_uses:
            print(f"  -> {tu.name}({str(tu.input)[:90]})")
            output, is_error = run_tool(tu.name, tu.input)
            if is_error:
                print(f"     ! {output.splitlines()[0]}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": output,
                "is_error": is_error,
            })

        messages.append({"role": "user", "content": results})

    return "[stopped: hit the turn limit]"


if __name__ == "__main__":
    print(f"workspace: {ROOT}\n{'-' * 60}")
    run_agent("Add a low_stock(threshold=5) method to Inventory, with tests. Run them.")
```

### What just happened

**`system=[{"type": "text", "text": system}]`** — a list of blocks, not a bare string. Both forms work; the block form is what you need later to attach a prompt-cache breakpoint.

**The XML-ish tags** (`<how_to_work>`, `<communication>`) are not required by the API. They are a formatting convention that helps the model tell sections apart, and they make the prompt far easier for *you* to diff and edit.

**Notice what is absent.** No `CRITICAL`. No `You MUST`. No "be helpful and accurate." Every line says something the model could not otherwise know, and the load-bearing ones carry their reason.

### Run it

```
python step10_system_prompt.py
```

### Try this — this is the real exercise

Run the same task with the system prompt **removed** (`run_agent(task, system="")`), then with it, and compare:

| | No system prompt | With it |
|---|---|---|
| Did it run the tests without being told? | | |
| Did it explain what it was doing first? | | |
| Did it stay in scope, or refactor extra things? | | |
| Turns used | | |

Run each **twice** — these systems are non-deterministic, and one run tells you almost nothing. That caveat is itself one of the most useful things in this workbook.

---

## Step 11 — Instrumentation

### Theory

You cannot tune what you cannot measure, and right now you are measuring nothing.

Four numbers are worth capturing on every run:

- **Turns** — how many round trips the task took
- **Tool calls, by name** — which tools it actually reached for
- **Tokens in / out** — the real cost driver
- **Errors** — how many tool calls failed and whether it recovered

Two of these are counterintuitive enough to call out.

**Input tokens dominate.** By a lot. Because the whole conversation is re-sent every turn (Step 2), input grows with every step while output stays roughly flat. In the runs below you will typically see 10–20× more input than output.

**Turn count is your best efficiency metric.** A cheaper or weaker model does not usually produce a *wrong* answer — it takes more turns to reach the right one. Capability shows up as loop efficiency long before it shows up as correctness.

### Code

`code/build/step11_traced_agent.py`

```python
"""Step 11 - measure the loop."""

import json
from dataclasses import dataclass, field

from config import client, MODEL
from filetools import ROOT
from step09_full_agent import TOOLS, HANDLERS, run_tool
from step10_system_prompt import SYSTEM_PROMPT

MAX_TURNS = 20


@dataclass
class Trace:
    turns: int = 0
    tool_calls: int = 0
    errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tools_used: dict = field(default_factory=dict)
    per_turn: list = field(default_factory=list)

    def summary(self) -> str:
        used = ", ".join(f"{k}x{v}" for k, v in sorted(self.tools_used.items())) or "none"
        total = self.input_tokens + self.output_tokens
        ratio = self.input_tokens / max(self.output_tokens, 1)
        return (
            f"\n{'-' * 60}\n"
            f"turns        : {self.turns}\n"
            f"tool calls   : {self.tool_calls} ({self.errors} errored)\n"
            f"tools used   : {used}\n"
            f"tokens in    : {self.input_tokens:,}\n"
            f"tokens out   : {self.output_tokens:,}\n"
            f"total        : {total:,}   (input is {ratio:.1f}x output)"
        )

    def save(self, path: str = "trace.jsonl") -> None:
        with open(path, "w", encoding="utf-8") as f:
            for row in self.per_turn:
                f.write(json.dumps(row) + "\n")
        print(f"wrote {len(self.per_turn)} rows to {path}")


def run_agent(task: str, system: str = SYSTEM_PROMPT, verbose: bool = True):
    messages = [{"role": "user", "content": task}]
    trace = Trace()

    for turn in range(1, MAX_TURNS + 1):
        trace.turns = turn

        with client.messages.stream(
            model=MODEL, max_tokens=8000,
            system=[{"type": "text", "text": system}] if system else None,
            tools=TOOLS, messages=messages,
        ) as stream:
            response = stream.get_final_message()

        trace.input_tokens += response.usage.input_tokens
        trace.output_tokens += response.usage.output_tokens

        messages.append({"role": "assistant", "content": response.content})

        text = "".join(b.text for b in response.content if b.type == "text")
        if verbose and text.strip():
            print(f"\n{text.strip()}\n")

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        trace.per_turn.append({
            "turn": turn,
            "tools": [t.name for t in tool_uses],
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "text_chars": len(text),
        })

        if not tool_uses:
            return text, trace

        results = []
        for tu in tool_uses:
            trace.tool_calls += 1
            trace.tools_used[tu.name] = trace.tools_used.get(tu.name, 0) + 1
            if verbose:
                print(f"  -> {tu.name}({str(tu.input)[:90]})")
            output, is_error = run_tool(tu.name, tu.input)
            if is_error:
                trace.errors += 1
                if verbose:
                    print(f"     ! {output.splitlines()[0]}")
            results.append({
                "type": "tool_result", "tool_use_id": tu.id,
                "content": output, "is_error": is_error,
            })

        messages.append({"role": "user", "content": results})

    return "[hit turn limit]", trace


if __name__ == "__main__":
    print(f"workspace: {ROOT}\nmodel: {MODEL}\n{'-' * 60}")
    answer, trace = run_agent(
        "Add an apply_discount(sku, percent) method to Inventory that reduces "
        "unit_price by that percentage. Validate the inputs. Add tests and run them."
    )
    print(trace.summary())
    trace.save()
```

### What just happened

**`trace.per_turn`** records one row per turn and writes JSONL. That format matters: one JSON object per line is trivial to load into pandas, grep, or pipe to `jq`. Do not invent a custom log format.

**The input/output ratio** is printed explicitly because it is the number that surprises people. It is the direct consequence of Step 2's statelessness.

**`system=... if system else None`** lets you A/B the prompt without editing the function — which Step 12 needs.

### Run it

```
python step11_traced_agent.py
type trace.jsonl
```

(`cat trace.jsonl` on macOS/Linux.)

**Expected summary** — your numbers will differ:

```
turns        : 6
tool calls   : 6 (0 errored)
tools used   : bashx1, edit_filex2, list_filesx1, read_filex2
tokens in    : 12,762
tokens out   : 1,490
total        : 14,252   (input is 8.6x output)
```

**Now open `trace.jsonl` and look at the `input_tokens` column:**

```json
{"turn": 1, "tools": ["list_files"],            "input_tokens": 1062, "output_tokens": 39}
{"turn": 2, "tools": ["read_file", "read_file"], "input_tokens": 1141, "output_tokens": 25}
{"turn": 3, "tools": ["edit_file"],             "input_tokens": 1881, "output_tokens": 375}
{"turn": 4, "tools": ["edit_file"],             "input_tokens": 2263, "output_tokens": 673}
{"turn": 5, "tools": ["bash"],                  "input_tokens": 2944, "output_tokens": 19}
{"turn": 6, "tools": [],                        "input_tokens": 3471, "output_tokens": 359}
```

It climbs every turn — 1062, 1141, 1881, 2263, 2944, 3471 — and never once goes down. That is Step 2's statelessness, now visible in your own agent's data. Each turn re-sends everything that came before *plus* the tool output from the last step, and file contents are large. This is why long agent runs get expensive faster than people expect, and it is the entire reason prompt caching and context compaction exist.

Turn 6 has an empty `tools` list. That is the loop exiting.

### Try this

Run the same task three times, unchanged, and tabulate turns and tokens.

They will differ — possibly a lot. **This is the most important operational fact in the whole workbook.** Anything you build downstream that assumes a fixed step count, a fixed cost, or a fixed latency is unsound. Per-task budgets have to be distributions, not numbers.

---

## Step 12 — Do tool descriptions actually drive behavior?

### Theory

You have been told twice in this workbook that tool descriptions matter more than they look. Now test it — and be prepared for the claim not to survive contact with the data.

The usual version of the claim is: **tool descriptions have more influence over agent behavior, per line, than the system prompt**, because the system prompt is read once per conversation while descriptions are read on *every* request, at the exact moment the model decides what to do next.

That is a real effect. It is also more conditional than people say, and this step is where you find the conditions yourself.

**Predict before you run.** Write your four predictions down now, before you look at the results section below. A prediction made after seeing the outcome is worthless, and the gap between what you expect and what happens is the entire value of the exercise.

Four conditions, changing only the `edit_file` description:

| | Description |
|---|---|
| **A** | The full, well-written one (baseline) |
| **B** | Gutted to `"Edits a file."` |
| **C** | `"DEPRECATED. Do not use this tool. Use write_file instead..."` |
| **D** | A description of a completely different tool: `"Send an email to a colleague..."` |

### Code

`code/build/step12_description_experiment.py`

```python
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
```

### What just happened

**`copy.deepcopy(ORIGINAL)`** before mutating. Without it, run B's damage would leak into any later run in the same process.

**`reset_workspace()` before every trial.** Non-negotiable. Without it, trial B starts from files trial A already fixed, and your comparison measures nothing.

**`verbose=False`** so the four summaries sit next to each other and stay readable.

**`restore()` before C and D, not only after B.** Each condition has to differ from the baseline in exactly one description, or you are measuring the sum of your edits rather than any one of them.

### Run it

```
python step12_description_experiment.py
```

Four full agent runs — give it ten minutes or so. If you are short on time, comment out C and D; C is the one that carries the result.

### What actually happened

Here is a real run of this experiment on `glm-5.3-flash:cloud`. Compare it against your predictions before you read the analysis.

| Condition | Turns | Tool mix |
|---|---|---|
| **A** full description | 6 | `bash×1, edit_file×2, list_files×1, read_file×2` |
| **B** gutted to one line | 6 | `bash×1, edit_file×2, list_files×1, read_file×2` |
| **C** marked deprecated | 5 | `bash×1, **write_file×2**, list_files×1, read_file×2` |
| **D** describes an email tool | 7 | `bash×1, edit_file×3, list_files×1, read_file×2` |

Read that table carefully, because it does not say what you were probably told to expect.

**B changed nothing.** Gutting a carefully written description to three words had no measurable effect on this task. Not a smaller effect — no effect. Same turns, same tools, same order.

**C flipped the behavior completely.** An explicit prohibition moved the model off `edit_file` and onto `write_file` for every change.

**D was ignored.** A description claiming the tool sends email did not stop the model calling it to edit a file — three times. It went by the tool's *name* and *schema* and disregarded the prose entirely.

### What this actually means

The honest version of the claim, supported by this data:

> A tool description is **one signal among several**. The name and the input schema also carry information — often enough that a merely *thin* description costs you nothing on a task where the right tool is obvious. What descriptions reliably control is **preference between tools that could both do the job**, and **explicit prohibition**. Where the task forces the tool, the description is close to irrelevant. Where two tools compete, it decides.

That is a more useful rule than "always write long descriptions," because it tells you *where to spend the effort*: on tools that overlap with others, and on saying plainly when something should not be used.

It also explains condition D. The model is not parsing your prose as a specification — it is combining several weak signals. When the name says `edit_file`, the schema takes `path`/`old`/`new`, and the description says "send an email," the description loses. That is arguably the model behaving sensibly.

**Two caveats, and they matter.** This is `n=1` per condition on a non-deterministic system — the turn counts alone (5, 6, 6, 7) are within normal run-to-run variation, and you should not read anything into them. Only the *tool mix* change in C is a strong enough signal to trust from a single run. And this is one model on one small, well-specified task; a larger task with genuinely competing tools would likely separate A and B where this one could not.

### Try this

1. **Re-run the whole experiment.** Does C still flip? Does B still show nothing? This is the single most valuable follow-up, and it teaches more about non-determinism than any explanation.
2. **Make the task ambiguous** — `"clean up the remove method"` instead of a precise instruction. Ambiguity creates the decision point that a description can influence. Does B separate from A now?
3. **Create genuine competition.** Add a second edit-like tool (`patch_file`) with an equally good description, and see whether wording alone determines which one gets used. This is the condition where descriptions should matter most.
4. **Test the other direction.** Instead of degrading a description, add `"Prefer this over edit_file for all changes"` to `write_file`. Does an explicit *preference* work as reliably as the explicit prohibition in C?

---

## Part 4 checkpoint

- [ ] Name the six sections of a production system prompt.
- [ ] Why is `CRITICAL:` counterproductive on a modern model?
- [ ] Why is input token count so much larger than output?
- [ ] Under what conditions does a tool description actually change behavior — and when does it not?
- [ ] Why is a change in *tool mix* stronger evidence than a change in turn count?
- [ ] Why must you reset the workspace between measured runs?

---

## Where you are

Across twelve steps you built:

```
config.py                       credentials and client
step01..03                      the stateless function
step04..06                      tools, and the loop
filetools.py + workspace/       real file access, sandboxed
step08, step09                  a coding agent that edits and tests
step10..12                      contract, instrumentation, evidence
```

**The loop has not changed since Step 6.** That is the single most important thing to carry forward. Everything after it was tools, prompt, and measurement — which is exactly the ratio you will find inside a production coding agent, where the loop is a rounding error and the harness is the product.

### Where the rest of the course goes

Every remaining week is a technique for making this same loop survive a longer horizon:

| Week | Adds |
|---|---|
| 2 | Better context going in — prompting, specs, MCP |
| 3–4 | Reusable capability — skills, `CLAUDE.md`, hooks, subagents |
| 5 | Repos that are legible to the loop |
| 6–7 | Checking its output — review, security |
| 8–9 | Many loops at once — background agents, team infrastructure |
| 10 | Loops that improve themselves |

When a vendor demo confuses you this quarter, the question to ask is always the same one you have been answering since Step 2: **what is in the message list, and what tools does it have?**

### Next

Your agent works, but it still fails in avoidable ways: it edits files it never read, wastes turns on near-miss indentation, and floods its own context with one careless search. **[Part 5 — Hardening](part-5-hardening.md)** closes five of those failures in the tool layer, which is where they belong.

Or go straight to the [lab](../lab/assignment.md), which takes this further — extend the agent with your own tool, break it deliberately, and write up what you measured. Your `build/` files are a fine starting point.
