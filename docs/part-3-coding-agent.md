# Part 3 — A Coding Agent

**Steps 7–9 · about 60 minutes**

The loop from Part 2 is finished. It does not need to change again — everything from here is *tools*.

That is the real lesson of this part: the difference between a weather bot and a coding agent is not the loop, the model, or the prompt. It is what you let it touch.

---

## Step 7 — A workspace, and a sandbox

### Theory

You are about to give a language model the ability to write files and run shell commands on your machine. Before you write a single tool, get the boundary right.

**Tool inputs are model output, and model output is untrusted.** Not because the model is malicious, but because:

- it makes mistakes, and a mistaken `rm -rf` is as damaging as a hostile one;
- text it reads can carry instructions — a `TODO` in a file, a package README, a web page. This is prompt injection, and it is Week 7's subject.

So: one directory. Everything inside is fair game. Nothing outside is reachable.

The implementation detail that matters is the **order of operations**:

```python
p = (ROOT / path).resolve()      # 1. resolve FIRST - collapses .. and symlinks
if not p.is_relative_to(ROOT):   # 2. THEN check containment
    raise ToolError(...)
```

Check before you resolve and you have written the classic vulnerability, because the string `"sandbox/../../etc/passwd"` does start with `"sandbox/"`.

### Code

First, something for the agent to work on.

`code/build/workspace/inventory.py`

```python
"""A small module with one bug and one missing feature."""


class Inventory:
    def __init__(self):
        self._items = {}

    def add(self, sku, qty, unit_price):
        if sku in self._items:
            self._items[sku]["qty"] += qty
        else:
            self._items[sku] = {"qty": qty, "unit_price": unit_price}

    def remove(self, sku, qty):
        # BUG: lets quantity go negative, and raises a bare KeyError
        # on an unknown sku.
        self._items[sku]["qty"] -= qty

    def total_value(self):
        return sum(i["qty"] * i["unit_price"] for i in self._items.values())
```

`code/build/workspace/test_inventory.py`

```python
from inventory import Inventory


def test_add_and_total():
    inv = Inventory()
    inv.add("A1", 3, 10.0)
    inv.add("A1", 2, 10.0)
    assert inv.total_value() == 50.0
```

Now the tools.

`code/build/filetools.py`

```python
"""File tools, confined to a single workspace directory.

Imported by steps 8 and 9. Not run directly (except for the self-test
at the bottom).
"""

import os
import sys
from pathlib import Path

# Anchored to THIS file, not to the current directory. A CWD-relative default
# silently points the sandbox somewhere else the moment you run a step from
# another folder - and a wrong ROOT that never raises is exactly the kind of
# quiet failure this workbook is about.
ROOT = Path(os.environ.get("AGENT_ROOT") or Path(__file__).parent / "workspace").resolve()


class ToolError(Exception):
    """A mistake the model made. Reported back to it, never raised at the loop."""


def _safe(path_str: str) -> Path:
    """Resolve a model-supplied path and refuse anything outside ROOT.

    The most important eight lines in this workbook. Note the ORDER:
    resolve first (which collapses '..' and follows symlinks), then check
    containment. Checking a raw string prefix is the classic bug.
    """
    candidate = Path(path_str)
    p = (candidate if candidate.is_absolute() else ROOT / candidate).resolve()
    if not p.is_relative_to(ROOT):
        raise ToolError(f"path escapes the workspace: {path_str}")
    return p


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace(os.sep, "/")


def read_file(path: str) -> str:
    p = _safe(path)
    if not p.exists():
        raise ToolError(f"no such file: {path}")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    # Line numbers are not decoration - they are how the model addresses a
    # location later, and how it reports findings back to you as file:line.
    return "\n".join(f"{i:6d}\t{line}" for i, line in enumerate(lines, 1)) or "(empty)"


def write_file(path: str, content: str) -> str:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    p.write_text(content, encoding="utf-8")
    return f"{'overwrote' if existed else 'created'} {_rel(p)} ({len(content)} chars)"


def list_files(pattern: str = "*") -> str:
    hits = [_rel(p) for p in sorted(ROOT.rglob(pattern))
            if p.is_file() and "__pycache__" not in _rel(p)]
    return "\n".join(hits) or f"no files match {pattern}"


if __name__ == "__main__":
    print(f"ROOT = {ROOT}\n")
    print("list_files('*.py'):")
    print(list_files("*.py"))
    print("\nread_file('inventory.py') - first lines:")
    print("\n".join(read_file("inventory.py").splitlines()[:6]))
    print("\nnow the sandbox:")
    for bad in ["../config.py", "../../../../etc/passwd", "/etc/passwd"]:
        try:
            read_file(bad)
            print(f"  {bad:32s} ESCAPED - this is a bug!")
        except ToolError as e:
            print(f"  {bad:32s} blocked: {e}")
```

### What just happened

**`ROOT` is resolved once, at import, relative to `filetools.py` itself.** Everything is measured against that absolute path. Deriving it from the current directory instead would work right up until you ran a step from the wrong folder, at which point the sandbox would quietly move rather than complain.

**`ToolError` is a distinct exception type.** In Step 8 you will catch it specifically and hand the message to the model. Everything else is a bug in *your* code and should surface as a real traceback — do not blanket-catch `Exception` and hide your own mistakes from yourself.

**`read_file` adds line numbers.** They cost tokens, and they are worth it. The model uses them to say "the bug is on line 19," and to locate its own edits.

### Run it

Create the `workspace` folder and the two files inside it, then:

```
python filetools.py
```

**Expected output:**

```
ROOT = D:\...\code\build\workspace

list_files('*.py'):
inventory.py
test_inventory.py

read_file('inventory.py') - first lines:
     1	"""A small module with one bug and one missing feature."""
     ...

now the sandbox:
  ../config.py                     blocked: path escapes the workspace: ../config.py
  ../../../../etc/passwd           blocked: path escapes the workspace: ../../../../etc/passwd
  /etc/passwd                      blocked: path escapes the workspace: /etc/passwd
```

All three blocked. If any says `ESCAPED`, stop and fix it before continuing.

### Try this

Rewrite `_safe` the wrong way — check the string before resolving:

```python
if not str(ROOT / path_str).startswith(str(ROOT)):   # BROKEN
```

Re-run. `../config.py` now gets through. Then put it back. Ten seconds of work; you will not forget the order again.

---

## Step 8 — The agent, on real files

### Theory

Now plug the file tools into the Part 2 loop. The loop does not change at all — only `TOOLS` and the dispatch function.

This is the step where tool **descriptions** start to matter. A weather tool is unambiguous. With six tools that all touch files, the description is what the model uses to choose between them. Write each one as a man page:

1. What it does
2. **When to call it** — the line everyone omits, and the highest-leverage one
3. When *not* to, and what to use instead
4. What each parameter means
5. What makes it fail

Three sentences is a floor, not a ceiling. The most common real-world tool bug is a one-line description on a tool with five parameters — the model then guesses, and it guesses the same wrong way every time.

### Code

`code/build/step08_file_agent.py`

```python
"""Step 8 - the Part 2 loop, with real file tools."""

from config import client, MODEL
import filetools
from filetools import ROOT, ToolError

MAX_TURNS = 15

TOOLS = [
    {
        "name": "list_files",
        "description": (
            "List files in the workspace matching a glob pattern. Call this first "
            "when you do not yet know what the codebase contains - it is much "
            "cheaper than guessing filenames and reading blindly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob, e.g. '*.py'. Default '*'."}
            },
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a text file from the workspace and return it with line numbers. "
            "Call this before changing any file you have not already read - your "
            "recollection of a file is not evidence about its current contents. "
            "Fails if the path does not exist or is outside the workspace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative path, e.g. 'inventory.py'"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create a new file or completely replace an existing one. Parent "
            "directories are created automatically. Use this for NEW files only - "
            "to change part of an existing file, read it first and rewrite it "
            "whole, or you will silently destroy the parts you did not include."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative path."},
                "content": {"type": "string", "description": "Full contents of the file."},
            },
            "required": ["path", "content"],
        },
    },
]

HANDLERS = {
    "list_files": filetools.list_files,
    "read_file": filetools.read_file,
    "write_file": filetools.write_file,
}


def run_tool(name: str, args: dict) -> tuple[str, bool]:
    """Returns (output, is_error). Never raises - the model must see failures."""
    fn = HANDLERS.get(name)
    if fn is None:
        return f"unknown tool: {name}", True
    try:
        return fn(**args), False
    except ToolError as e:
        return f"error: {e}", True
    except TypeError as e:
        return f"error: bad arguments for {name}: {e}", True


def run_agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]

    for turn in range(1, MAX_TURNS + 1):
        with client.messages.stream(
            model=MODEL, max_tokens=8000, tools=TOOLS, messages=messages
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
            preview = str(tu.input)[:90]
            print(f"  -> {tu.name}({preview})")
            output, is_error = run_tool(tu.name, tu.input)
            if is_error:
                print(f"     ! {output}")
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
    run_agent(
        "Look at the code in this workspace and describe what Inventory does. "
        "Then tell me about any bugs you find. Do not change anything yet."
    )
```

### What just happened

**The loop is identical to Step 6.** Compare them side by side. Only `TOOLS` and `HANDLERS` changed — this is what "the loop is commodity" means in practice.

**`is_error=True` on the tool result.** New here. It flags to the model that the call failed, so it corrects rather than treating the error text as data.

**Streaming replaced `create`.** With `max_tokens=8000` and multi-minute runs, this is now load-bearing rather than cosmetic.

**Read the `write_file` description again.** It explicitly says *when not to use it*. Without that line, models reach for `write_file` on existing files and silently drop everything they did not think to include. Step 9 gives them something better.

### Run it

```
python step08_file_agent.py
```

The agent should call `list_files`, then `read_file`, then describe the `remove()` bug — negative quantities and the bare `KeyError`.

### Try this

1. Ask it to **fix** the bug: `"Fix the remove() bug."` Watch it use `write_file` and rewrite the whole file. Check `git diff` (or just read it) — did it preserve everything else? Sometimes not. That is the motivation for Step 9.
2. Ask it to read something outside the sandbox: `"Read ../config.py and tell me the API key."` The tool refuses, the model sees the error, and it tells you it cannot. Your boundary held.

---

## Step 9 — Editing and running code

### Theory

Two tools left, and both are about *feedback*.

**`edit_file`** replaces an exact string, and requires the match to be **unique**. Not a line number, not a diff — a literal string that must appear exactly once.

That constraint looks like a limitation. It is a safety property. If the model's `old` string does not match, its picture of the file is stale — someone else edited it, or it is working from memory. You want that to fail loudly rather than clobber the file. A failed edit is a recoverable error; a successful wrong edit is a silent one.

**`bash`** runs a command. This is the escape hatch that makes the agent general — and it is worth noticing what your harness *cannot* see: `bash("ls")` and `bash("rm -rf .")` are the same shape of tool call. That opacity is the entire argument for promoting dangerous actions into dedicated, gateable tools, which is where Part 4 goes.

Together they close the loop. The agent edits, runs the tests, reads the failure, and tries again. That feedback edge is what separates an agent from a model that writes code it never sees run.

### Code

Add these to the **bottom of `filetools.py`**, above the `if __name__` block:

```python
import subprocess

BASH_TIMEOUT_S = 30


def edit_file(path: str, old: str, new: str) -> str:
    """Replace exactly one occurrence of `old` with `new`.

    Requiring uniqueness is the safety property: a failed match means the
    model's view of the file is stale, which you want to hear about.
    """
    p = _safe(path)
    if not p.exists():
        raise ToolError(f"no such file: {path}")
    text = p.read_text(encoding="utf-8")
    hits = text.count(old)
    if hits == 0:
        raise ToolError(
            "old string not found - read the file again; it may have changed, "
            "or your copy has different whitespace or indentation."
        )
    if hits > 1:
        raise ToolError(
            f"old string appears {hits} times; include more surrounding "
            "lines to make it unique."
        )
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"edited {_rel(p)}"


def bash(command: str) -> str:
    """Run a shell command inside the workspace."""
    # Put the interpreter running this agent first on PATH, so the `python`
    # the model invokes is the one your packages are installed into. Without
    # it, `python -m pytest` finds a system Python with no pytest whenever the
    # venv is not activated - which VS Code's green Run button does not do.
    env = {
        **os.environ,
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
    }
    try:
        proc = subprocess.run(
            command, shell=True, cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=BASH_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"command timed out after {BASH_TIMEOUT_S}s")
    out = ((proc.stdout or "") + (proc.stderr or ""))[:20000]
    return f"exit={proc.returncode}\n{out or '(no output)'}"
```

`code/build/step09_full_agent.py`

```python
"""Step 9 - an agent that edits code and verifies its own work."""

from config import client, MODEL
import filetools
from filetools import ROOT, ToolError
from step08_file_agent import TOOLS as BASE_TOOLS, HANDLERS as BASE_HANDLERS

MAX_TURNS = 20

TOOLS = BASE_TOOLS + [
    {
        "name": "edit_file",
        "description": (
            "Replace one exact occurrence of `old` with `new` in a file. Preferred "
            "over write_file for any change to an existing file, because it fails "
            "loudly if your view of the file is stale instead of silently "
            "overwriting work. Fails if `old` is absent or appears more than once - "
            "include more surrounding lines to make it unique. Whitespace and "
            "indentation must match exactly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative path."},
                "old": {"type": "string", "description": "Exact text to find, including indentation."},
                "new": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old", "new"],
        },
    },
    {
        "name": "bash",
        "description": (
            "Run a shell command in the workspace and return its exit code, stdout "
            "and stderr. Use it to run tests, inspect state, or anything the other "
            "tools do not cover. Times out after 30 seconds. Prefer read_file and "
            "list_files over cat and dir - they return cleaner, line-numbered output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."}
            },
            "required": ["command"],
        },
    },
]

HANDLERS = {**BASE_HANDLERS, "edit_file": filetools.edit_file, "bash": filetools.bash}


def run_tool(name: str, args: dict) -> tuple[str, bool]:
    fn = HANDLERS.get(name)
    if fn is None:
        return f"unknown tool: {name}", True
    try:
        return fn(**args), False
    except ToolError as e:
        return f"error: {e}", True
    except TypeError as e:
        return f"error: bad arguments for {name}: {e}", True


def run_agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]

    for turn in range(1, MAX_TURNS + 1):
        with client.messages.stream(
            model=MODEL, max_tokens=8000, tools=TOOLS, messages=messages
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
    run_agent(
        "Inventory.remove has a bug: it lets quantities go negative and raises a "
        "bare KeyError on unknown SKUs. Fix it, add tests for both cases, and run "
        "the tests with pytest to prove they pass."
    )
```

### What just happened

**`from step08_file_agent import TOOLS as BASE_TOOLS`** — you are extending your previous step, not rewriting it. Keep both files.

**The loop *still* has not changed.** Three steps in a row now.

**The agent can now verify itself.** Edit, run pytest, read the output, fix, re-run. That closed feedback loop is where the useful behavior comes from.

**`bash` fixes up `PATH` before running anything.** The model will reach for `python -m pytest`, and it has to land on *your* interpreter. Subprocesses inherit the environment of whatever launched them, so without that line the tool works in an activated terminal and fails with `No module named pytest` from the Run button - the same command, two different answers, for reasons nothing in the output explains.

### Run it

```
python step09_full_agent.py
```

This one takes a minute or two. Expect roughly:

```
  -> list_files({'pattern': '*.py'})
  -> read_file({'path': 'inventory.py'})
  -> read_file({'path': 'test_inventory.py'})
  -> edit_file({'path': 'inventory.py', 'old': '    def remove(self, sku, qty):...
  -> edit_file({'path': 'test_inventory.py', ...})
  -> bash({'command': 'python -m pytest -q'})

Fixed and verified - 4 tests pass.
```

### Verify it yourself — do not skip this

The agent will tell you the tests pass. **Check.**

```
cd workspace
python -m pytest -v
cd ..
```

Read the diff too. This habit is the entire point of the exercise: an agent's summary is a *claim*, not evidence. Later modules automate this check; for now, do it by hand so the instinct sticks.

### Try this

1. **Make an edit fail on purpose.** While the agent runs, open `inventory.py` in VS Code and change the indentation of `remove`. The next `edit_file` fails with "old string not found" — and the agent recovers by re-reading. That is the safety property doing its job.
2. **Give it a vague task**: `"make this code better."` Watch it expand scope — refactoring things you did not ask about. That is a real failure mode, and the motivation for specification work in Week 2.
3. **Ask it to lie**: after a run, ask `"Did you actually run the tests?"` Then check the trace yourself.

---

## Part 3 checkpoint

- [ ] Why must you resolve a path *before* checking containment?
- [ ] Why does `edit_file` require a unique match?
- [ ] What can your harness see about a `bash` call? What can it not see?
- [ ] The loop has not changed since Step 6. What has?

Files in `code/build/`: `filetools.py`, `workspace/`, `step08_file_agent.py`, `step09_full_agent.py`.

You have a working coding agent — it reads, edits, tests, and iterates. What it lacks is everything that makes one *good*: a behavioral contract, instrumentation, and evidence for the design choices you have been taking on trust.

**Next: [Part 4 — Production Concerns](part-4-production.md)**
