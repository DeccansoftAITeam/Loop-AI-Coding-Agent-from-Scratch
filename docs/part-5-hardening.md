# Part 5 — Hardening

**Steps 13–19 · about 90 minutes**

Your agent works. It also fails in ways you have probably already seen: it edits a file it never read, it burns a turn because it got indentation slightly wrong, it floods its own context with the output of one careless search.

None of those are model problems. They are gaps in the tools, and every one of them is fixable in the tool layer. That is the theme of this part, and it is the most transferable idea in the module:

> **When the model reliably gets something wrong, fix the tool — not the prompt.**

Each step below takes one observed failure and closes it. Everything stays in `build/`; you are editing `filetools.py` and adding a `descriptions/` directory.

> **Reset your workspace first.** Steps 9, 10 and 11 all ran agents that rewrote `workspace/inventory.py` — by now it contains whatever they left. The verification commands in this part quote specific lines from that file, so restore the original from Part 3 Step 7 before you start, or they will fail for reasons that have nothing to do with your code.

---

## Step 13 — Descriptions are prompts, so version them like prompts

### Theory

Your tool descriptions currently live inside `step09_full_agent.py` as string literals in the middle of a Python dict. Think about what that means.

A description is read by the model on **every single request**. Changing one line of it changes agent behavior across every task. It is, functionally, a prompt — and you have it buried on line 40 of a source file where a reviewer skims past it.

Production agents separate them. In opencode, every tool is a pair of files: `edit.ts` next to `edit.txt`, `read.ts` next to `read.txt`. For its todo tool, `todowrite.txt` is *larger than the implementation it describes*.

Three reasons this is worth copying:

- **Reviewability.** A description change shows up as a diff to a text file, not a string literal inside logic. A reviewer can read it as prose, because it is prose.
- **Testability.** You can swap descriptions without touching code — which is exactly what Step 12's experiment did by hand, awkwardly, through `copy.deepcopy`.
- **Honesty.** It puts the prompt where the prompt belongs. Nobody looks at `todowrite.txt` and thinks "that's a comment."

### Code

Create a `descriptions/` directory next to your other build files. You need **one file per tool, all five** — `describe()` raises on a missing file, so the agent will not start until they all exist. Three are short; two are below in full, and the remaining three follow.

`build/descriptions/edit_file.txt`

```
Replace one occurrence of `old` with `new` in an existing file.

## When to use
- Any change to a file that already exists. Preferred over write_file,
  because a bad assumption fails loudly here instead of silently destroying
  the parts of the file you did not think to include.

## Requirements
- You must read the file with read_file first, this session. The edit is
  refused otherwise - your idea of the contents has to come from the file,
  not from memory.
- `old` must identify exactly one place in the file. If it appears more than
  once, include more surrounding lines until it is unique.
- Copy `old` from read_file output WITHOUT the line-number prefix. The format
  is `<number><tab><content>`; only the content after the tab is in the file.

## Notes
- Whitespace and indentation should match, but small differences in leading
  or trailing whitespace are tolerated and reported back to you.
- The edit is refused if the matched region is much larger than `old` - that
  means the match was too loose to trust. Re-read and supply exact text.
```

`build/descriptions/bash.txt`

```
Run a shell command in the workspace and return exit code, stdout and stderr.

## When to use
- Running tests, linters, builds, or a formatter.
- Inspecting state the other tools do not expose (git status, installed
  packages, environment).
- Anything with no dedicated tool.

## When NOT to use
- Reading files - use read_file, which gives line numbers you will need for
  editing. `cat` does not.
- Finding files - use list_files.

## Notes
- Runs with the workspace as the working directory. Times out after 30s.
- Commands that wait for input will hang until the timeout. Use
  non-interactive flags.
- Verify your own work with this tool. A change is not done until something
  has actually run and passed.
```

`build/descriptions/list_files.txt`

```
List files in the workspace matching a glob pattern.

## When to use
- First, when you do not yet know what the codebase contains. Discovering
  structure is much cheaper than guessing filenames and reading blindly.
- To check whether a file exists before reading it.

## When NOT to use
- To search inside files - use read_file once you know what to open.

## Notes
- Patterns match the whole relative path, e.g. `*.py`, `src/**/*.ts`.
```

`build/descriptions/read_file.txt`

```
Read a UTF-8 text file from the workspace and return it with line numbers.

## When to use
- Before editing any file you have not already read this session. edit_file
  requires a match against the real contents and will refuse otherwise.
- When you need to see actual code rather than just locate it.
- Call it in parallel when you know you want several files.

## When NOT to use
- To find which files exist - use list_files.

## Notes
- Output is `<line number><tab><content>`. The line number and tab are NOT
  part of the file. Never include them in an edit_file `old` string.
```

`build/descriptions/write_file.txt`

```
Create a new file, or completely replace an existing one.

## When to use
- Creating a file that does not exist yet.
- A rewrite so extensive that a targeted edit makes no sense.

## When NOT to use
- Changing part of an existing file. Use edit_file. write_file replaces the
  whole file, so anything you did not include is destroyed silently - and
  unlike a failed edit, nothing tells you it happened.

## Notes
- Parent directories are created automatically. There is no append mode.
```

Now the loader. Add to the top of `filetools.py`:

```python
DESCRIPTIONS = Path(__file__).parent / "descriptions"


def describe(name: str) -> str:
    """Load a tool description from descriptions/<name>.txt.

    A missing file is a hard error rather than a silent empty string. An
    undescribed tool is one the model will not call, and you would rather
    find that out at import than three turns into a session.
    """
    path = DESCRIPTIONS / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"missing tool description: {path}")
    return path.read_text(encoding="utf-8").strip()
```

And in `step09_full_agent.py`, replace every inline description:

```python
from filetools import describe          # add to the imports

TOOLS = BASE_TOOLS + [
    {
        "name": "edit_file",
        "description": describe("edit_file"),
        "input_schema": { ... },
    },
    ...
]
```

Do the same in `step08_file_agent.py` for `list_files`, `read_file`, and `write_file`.

### What just happened

Nothing, behaviorally. Run Step 11 and the trace should look the same — this is a pure refactor, and it is worth confirming that before moving on.

What changed is what a *diff* now looks like. Compare:

```diff
-        "description": ("Replace one exact occurrence of `old` with `new` in a file. Preferred "
-                        "over write_file for any change to an existing file, because it fails "
+        "description": describe("edit_file"),
```

versus a change to `descriptions/edit_file.txt`, which reads as an edit to a document because it is one.

### Run it

```
python step11_traced_agent.py
```

Same behavior, same trace. Then break it on purpose — rename `descriptions/bash.txt` and run again. You get a `FileNotFoundError` at import, not a silently undescribed tool that the model quietly stops calling. That failure mode is the reason `describe` raises instead of returning `""`.

---

## Step 14 — Error messages are prompts too

### Theory

Look at an error your agent produces today:

```
error: no such file: inventory.py
```

True, and useless. The model now has to work out on its own what to do next, and it will often guess — trying variations of the filename, or giving up and using `bash`.

Now this:

```
error: no such file: inventory.py. Use list_files to see what exists before reading.
```

Same failure. But the second one **steers the next turn**. opencode is explicit about this in a source comment — its validation error is described as *"the model-facing prose that the AI SDK feeds back as the tool result."* Their message ends: *"Please rewrite the input so it satisfies the expected schema."*

The rule: **every error message is a chance to say what to do instead.** You are not writing a log line for a human operator. You are writing the next instruction the model will read.

### Code

Rewrite the error paths in `filetools.py`. The pattern is `<what went wrong>. <what to do next>.`

```python
def read_file(path: str) -> str:
    p = _safe(path)
    if not p.exists():
        raise ToolError(
            f"no such file: {path}. Use list_files to see what exists before reading."
        )
    if p.is_dir():
        raise ToolError(f"{path} is a directory. Use list_files('{path}/*') to list it.")
    ...
```

```python
def _safe(path_str: str) -> Path:
    ...
    if not p.is_relative_to(ROOT):
        raise ToolError(
            f"path escapes the workspace: {path_str}. "
            "Use a workspace-relative path; you cannot reach outside the workspace."
        )
    return p
```

```python
def bash(command: str) -> str:
    try:
        ...
    except subprocess.TimeoutExpired:
        raise ToolError(
            f"command timed out after {BASH_TIMEOUT_S}s. If it was waiting for input, "
            "re-run it with a non-interactive flag."
        )
```

And in the dispatcher, an unknown tool should say what *is* available:

```python
    fn = HANDLERS.get(name)
    if fn is None:
        return f"unknown tool: {name}. Available tools: {', '.join(sorted(HANDLERS))}", True
```

Go through every `raise ToolError` you have and ask: *does this tell the model what to do next?*

### Run it

```
python step09_full_agent.py
```

Then force an error to read the new message:

```
python -c "from filetools import read_file; print(read_file('nope.py'))"
```

### Try this

Give the agent a task that requires a file it cannot guess the name of — `"fix the bug in the pricing module"` when no such file exists. With the old message it flails. With the new one it should reach for `list_files` on the next turn.

Worth watching for: this is a place where an eval would earn its keep. "Did the error message reduce recovery turns?" is measurable, and Step 11 already gives you the instrumentation.

---

## Step 15 — A prompt is a request; a guard is a guarantee

### Theory

Your `SYSTEM_PROMPT` says:

> *Read before you edit. Your memory of a file is not evidence about its current contents.*

That is a **request**. The model usually honours it, and sometimes does not — and when it does not, you get an edit based on a recollection, which either fails noisily or succeeds wrongly.

opencode's `edit.txt` says something different:

> *You must use your Read tool at least once in the conversation before editing. **This tool will error if you attempt an edit without reading the file.***

That second sentence is not a stronger request. It is a description of a **guarantee**, enforced in code. The model cannot make the mistake, because the tool will not let it.

This is the single sharpest illustration of a distinction that runs through the whole course:

| | Mechanism | Reliability |
|---|---|---|
| System prompt instruction | Asking | Usually |
| Tool description | Asking, more specifically | Usually |
| **Tool-level guard** | **Refusing** | **Always** |
| Hook / CI gate | Refusing, outside the agent | Always |

Anything you can move down that table, you should. Prompts are for judgment you cannot express as a check.

### Code

This needs a little session state — the tool layer has to remember which files have been read.

Add to `filetools.py`:

```python
# The only mutable state in the tool layer, and it exists for exactly one
# reason: edit_file has to know whether the model has actually looked at the
# file it is about to change.
_read_this_session: set[str] = set()


def reset_session() -> None:
    """Called by the agent at the start of each run."""
    _read_this_session.clear()
```

Now record reads. This is a one-line addition to two functions, but **where** the line goes matters and a floating snippet is easy to misplace — so here are both functions complete. Replace yours wholesale.

```python
def read_file(path: str) -> str:
    p = _safe(path)
    if not p.exists():
        raise ToolError(f"no such file: {path}. Use list_files to see what exists before reading.")
    if p.is_dir():
        raise ToolError(f"{path} is a directory. Use list_files('{path}/*') to list it.")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    _read_this_session.add(_rel(p))          # <- Step 15
    return "\n".join(f"{i:6d}\t{line}" for i, line in enumerate(lines, 1)) or "(empty)"


def write_file(path: str, content: str) -> str:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    p.write_text(content, encoding="utf-8")
    _read_this_session.add(_rel(p))          # <- we just wrote it, so we know it
    return f"{'overwrote' if existed else 'created'} {_rel(p)} ({len(content)} chars)"
```

Then guard `edit_file`, at the very top after the existence check:

```python
    if _rel(p) not in _read_this_session:
        raise ToolError(
            f"{_rel(p)} has not been read this session. "
            f"Call read_file('{_rel(p)}') first - edits must be based on the "
            "file's actual current contents, not on your recollection of them."
        )
```

Finally, have the agent reset that state per run. In `step11_traced_agent.py`:

```python
import filetools

def run_agent(task: str, system: str = SYSTEM_PROMPT, verbose: bool = True):
    filetools.reset_session()          # <- add this line
    messages = [{"role": "user", "content": task}]
    ...
```

Update `descriptions/edit_file.txt` to state the requirement — a guard the model does not know about just produces confusing failures.

### Run it

```
python step11_traced_agent.py
```

Then prove the guard works — **in both directions**. Testing only the refusal is the trap here: if you put `_read_this_session.add(...)` in the wrong function, the refusal still fires and everything looks correct, but *no edit will ever be allowed again*. You would not find out until Step 16, with a baffling error.

```
python -c "
import filetools as f

# 1. edit WITHOUT reading -> must be refused
f.reset_session()
try:
    f.edit_file('inventory.py', 'def remove', 'def remove')
    print('FAIL: the guard did not fire')
except f.ToolError as e:
    print('refused as expected:', str(e)[:60])

# 2. read, THEN edit -> must be allowed
f.reset_session()
f.read_file('inventory.py')
print(f.edit_file('inventory.py', 'def remove', 'def remove'))
"
```

**Expected:**

```
refused as expected: inventory.py has not been read this session. Call re
edited inventory.py
```

If the second line raises instead of printing `edited`, your `read_file` is not recording the read — check that the `_read_this_session.add(_rel(p))` line is inside `read_file` and not somewhere else.

### Try this

Now that the guard exists, **delete the "read before you edit" line from `SYSTEM_PROMPT`** and run the task three times. Does behavior change?

Most likely not much — the model reads first anyway because that is what the task needs, and when it forgets, the guard catches it and the error tells it what to do. You have replaced a prompt instruction with a mechanism, and freed a line of prompt budget.

That is the trade to look for everywhere: **prompt lines are expensive and probabilistic; guards are cheap and certain.**

---

## Step 16 — Absorbing a known model failure

### Theory

Your `edit_file` requires an exact match. Watch a few runs and you will see it fail on edits that were *nearly* right — a tab where the file has spaces, one level of indentation off, a trailing space dropped.

Each failure costs a turn: the model reads the error, re-reads the file, tries again. That is the loop working correctly, and it is still waste.

You have two options:

1. **Fail and make the model retry.** Correct, strict, costs a turn.
2. **Make the tool absorb the failure.** Try progressively looser matching.

Option 2 is what production agents do — opencode has **nine** matching strategies tried in sequence. But looseness is dangerous: a matcher relaxed enough to always find something will eventually find the *wrong* thing, and silently replace it.

The design that makes it safe has three parts:

- **Ordered strictest-first.** Exact match wins if it exists. Fuzziness is a fallback, never a first choice.
- **Uniqueness still required.** A loose match that hits two places is rejected, not guessed between.
- **A disproportionality guard.** If the matched region is much bigger than what was asked for, refuse. This is what stops a fuzzy matcher swallowing half the file.

We will build three matchers rather than nine. The principle is identical.

### Code

Add to `filetools.py`, above `edit_file`:

```python
# Requiring an exact match is correct but brittle: models reproduce
# indentation and trailing whitespace slightly wrong all the time, and
# every failed edit costs a turn. So we try progressively looser matchers,
# strictest first, and refuse the result if the match grew unreasonably
# large.
#
# Each matcher takes (file_contents, what_the_model_asked_for) and returns
# a list of candidate substrings that might be what was meant.

SEARCH_WINDOW_LINES = 200


def _needle_lines(find: str) -> list[str]:
    """Split the requested text into lines, dropping a trailing blank.

    A trailing newline is meaningless for matching but would make every
    line-based comparison off by one, so it is handled once, here.
    """
    lines = find.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _exact(content: str, find: str) -> list[str]:
    """The strictest matcher: what the model sent, verbatim."""
    return [find]


def _line_trimmed(content: str, find: str) -> list[str]:
    """Match ignoring leading and trailing whitespace on each line.

    Catches the common case where the model got the indentation almost right.
    Returns the original text from the file, so the replacement splices in
    cleanly rather than reintroducing the model's wrong indentation.
    """
    haystack = content.split("\n")
    needle = _needle_lines(find)
    if not needle:
        return []

    want = [line.strip() for line in needle]
    found = []
    for start in range(len(haystack) - len(needle) + 1):
        window = haystack[start : start + len(needle)]
        if [line.strip() for line in window] == want:
            found.append("\n".join(window))
    return found


def _block_anchor(content: str, find: str) -> list[str]:
    """Match on the first and last line only, for blocks of three or more.

    If the model quoted a function correctly at both ends but garbled the
    middle, this still finds the right block. The span is not fixed to the
    requested line count - we scan forward for the closing line - so a match
    can come back longer than what was asked for. That is what makes this
    matcher useful, and exactly why _disproportionate has to exist.

    Deliberately last in the cascade: it is much looser than the two above.
    """
    haystack = content.split("\n")
    needle = _needle_lines(find)
    if len(needle) < 3:
        return []

    first, last = needle[0].strip(), needle[-1].strip()
    found = []
    for start, line in enumerate(haystack):
        if line.strip() != first:
            continue
        end = _closing_line(haystack, start, last)
        if end is not None:
            found.append("\n".join(haystack[start : end + 1]))
    return found


def _closing_line(haystack: list[str], start: int, last: str) -> int | None:
    """Index of the nearest line after `start` matching `last`, or None.

    Nearest, not furthest: a closing line further down would select more of
    the file than the model meant.
    """
    stop = min(len(haystack), start + SEARCH_WINDOW_LINES)
    for i in range(start + 2, stop):
        if haystack[i].strip() == last:
            return i
    return None


MATCHERS = (_exact, _line_trimmed, _block_anchor)


def _disproportionate(matched: str, find: str) -> bool:
    """True if the match is much larger than what was asked for.

    A loose matcher that swallows half the file is worse than no match at
    all, because nothing about it looks wrong until the damage is done.
    """
    find_lines = len(find.split("\n"))
    match_lines = len(matched.split("\n"))
    if match_lines >= max(find_lines + 3, find_lines * 2):
        return True
    if find_lines == 1:
        return False
    return len(matched.strip()) > max(len(find.strip()) + 500, len(find.strip()) * 4)
```

Now replace `edit_file` with these two functions. Splitting them is the point: `edit_file` decides **whether** an edit is allowed, `_find_match` decides **what** it applies to. Keeping both jobs in one function is what made the original hard to read.

```python
def _find_match(text: str, old: str, where: str) -> tuple[str, str]:
    """Find the one region of `text` that `old` refers to.

    Returns (matched_text, matcher_name); matcher_name is empty for an exact
    match. Raises ToolError - with a message saying how to fix it - when the
    match is missing, ambiguous, or too loose to trust.
    """
    for matcher in MATCHERS:
        for candidate in matcher(text, old):
            if not candidate or candidate not in text:
                continue
            if text.count(candidate) > 1:
                continue  # ambiguous under this matcher; try the next candidate
            if _disproportionate(candidate, old):
                raise ToolError(
                    "refusing this edit: the matched region is much larger than the text "
                    "you supplied, so the match is probably wrong. Re-read the file and "
                    "give the exact text you want replaced."
                )
            return candidate, "" if matcher is _exact else matcher.__name__.lstrip("_")

    # No matcher found a unique region. The two reasons need different fixes,
    # so the error says which one it was.
    if old in text:
        raise ToolError(
            f"`old` appears {text.count(old)} times in {where}. Include more "
            "surrounding lines so it identifies exactly one place."
        )
    raise ToolError(
        f"`old` not found in {where}. Re-read the file - it may have changed, or your "
        "copy may include the line-number prefix from read_file output."
    )


def edit_file(path: str, old: str, new: str) -> str:
    """Replace the one region of a file that `old` identifies.

    This function decides whether an edit is allowed; _find_match decides
    what it applies to.
    """
    p = _safe(path)
    if not p.exists():
        raise ToolError(f"no such file: {path}. Use list_files to see what exists.")

    # A prompt asking the model to read before editing is a request. This is
    # a guarantee: the mistake becomes impossible rather than discouraged.
    if _rel(p) not in _read_this_session:
        raise ToolError(
            f"{_rel(p)} has not been read this session. "
            f"Call read_file('{_rel(p)}') first - edits must be based on the "
            "file's actual current contents, not on your recollection of them."
        )

    if not old:
        raise ToolError(
            "`old` cannot be empty. Provide the exact text to replace, or use "
            "write_file if you intend to replace the whole file."
        )

    text = p.read_text(encoding="utf-8")
    matched, how = _find_match(text, old, _rel(p))

    p.write_text(text.replace(matched, new, 1), encoding="utf-8")
    return f"edited {_rel(p)}" + (f" (matched via {how})" if how else "")
```

### What just happened

**The success message reports which matcher fired** — `edited inventory.py (matched via line_trimmed)`. That is not decoration. It tells you, in the trace, how often the model is getting exact matches wrong, which is data you would otherwise never see.

**Uniqueness is still enforced per candidate.** A matcher that finds two possible spots yields both; `text.count(candidate) > 1` skips them and we fall through. Fuzzier matching did not buy the model the right to be ambiguous.

**The two failure messages are different**, because they need different fixes: "appears N times" means *add context*; "not found" means *re-read*.

### Run it

Verify each matcher separately. Save this as `check_matchers.py` rather than fighting shell quoting:

```python
"""Throwaway - confirms each matcher fires."""

import filetools as f

f.reset_session()
f.read_file("inventory.py")

# 1. exact match
print(f.edit_file("inventory.py", "def total_value", "def total_value"))

# 2. MULTI-LINE block with wrong indentation. Multi-line matters - see below.
wrong = (
    "  def remove(self, sku, qty):\n"
    "      # BUG: lets quantity go negative, and raises a bare KeyError\n"
    "      # on an unknown sku.\n"
    '      self._items[sku]["qty"] -= qty'
)
print(f.edit_file("inventory.py", wrong, wrong))
```

```
python check_matchers.py
```

**Expected:**

```
edited inventory.py
edited inventory.py (matched via line_trimmed)
```

> **Why multi-line?** A *single* under-indented line will never reach `_line_trimmed`. `'  def remove(self, sku, qty):'` is a literal substring of `'    def remove(self, sku, qty):'`, so `_exact` finds it and wins — you would see `edited inventory.py` with no matcher note and wrongly conclude the fallback was broken. You need at least two lines before a whitespace difference actually defeats an exact match. Worth ten seconds of thought before moving on; substring behaviour like this is a recurring source of confusing test results.

> **Restore the workspace before continuing.** `check_matchers.py` wrote the
> model's *wrong* indentation back into `inventory.py` — that was the point of
> the second edit — which leaves the file with mixed indent levels and no longer
> valid Python. Put the Step 7 original back, or the next check and every agent
> run after it fails with an `IndentationError` that has nothing to do with your
> code.

Then prove the guardrail refuses an over-broad match. A file again, not a
one-liner — the anchor lines have to match the file character for character,
quote marks included, and shell escaping is the fastest way to get that wrong:

`build/check_guard.py`

```python
"""Throwaway - confirms _disproportionate refuses an over-broad match."""

import filetools as f

f.reset_session()
f.read_file("inventory.py")

# The first line anchors on add(), the last on total_value()'s body. Note the
# DOUBLE quotes inside the subscripts: that is how inventory.py writes them,
# and _block_anchor compares the anchor lines literally. Single quotes here
# match nothing and you get "`old` not found" instead of the refusal.
big = (
    "def add(self, sku, qty, unit_price):\n"
    "    ...\n"
    '    return sum(i["qty"] * i["unit_price"] for i in self._items.values())'
)
print(f.edit_file("inventory.py", big, "x"))
```

```
python check_guard.py
```

**Expected:**

```
ToolError: refusing this edit: the matched region is much larger than the text you
supplied, so the match is probably wrong. Re-read the file and give the exact text
you want replaced.
```

The first line of that block anchor matches `add`, the last matches `total_value`'s body — so a naive anchor matcher would have replaced both methods and everything between them. The guard caught it.

> **Getting `` `old` not found `` instead of the refusal?** Either the anchor lines do not match the file character for character - single vs double quotes is the usual culprit - or your `workspace/inventory.py` is not the Part 3 original — one of the agent runs in Steps 9 to 11 rewrote it, and `total_value` may no longer exist in the form this example quotes. Restore the original and re-run.

### Try this

1. **Comment out `_disproportionate` and re-run the guardrail test.** Watch it silently destroy two methods. Put it back. This is the fastest possible demonstration of why loose matching needs a brake.
2. **Count matcher usage across several runs.** If `line_trimmed` fires often, that is a measurement of how badly the model reproduces indentation on your codebase — useful, and invisible before now.

---

## Step 17 — The context window is a shared resource

### Theory

Run this and watch what happens:

```
python -c "
import filetools as f
print(len(f.bash('python -c \"print(chr(120)*200000)\"')))
"
```

Two hundred thousand characters, roughly 50,000 tokens, going straight into your conversation — where it stays, and gets re-sent on every subsequent turn (Step 2). One careless command can cost more context than the entire rest of the task.

`grep` on a large repo does this. So does a verbose test suite, an installer, or `cat` on a lockfile.

The naive fix is to truncate. But truncation loses information the model may actually need, and it has no way to ask for the rest.

The better pattern, and the one production agents use: **truncate, spill the full output to a file, and hand back the path.** The context stays small; the data stays reachable. If it turns out to matter, the model can `grep` or `read_file` the spill.

### Code

Add to `filetools.py`:

```python
# Budget for any single tool result. Beyond this the output is spilled to a
# file and the model gets a pointer instead. One unbounded grep can otherwise
# consume more context than the entire task needs.
MAX_TOOL_OUTPUT_CHARS = 20_000
SPILL_DIR = ".agent-output"

_spill_count = 0


def truncate(output: str) -> str:
    """Cap any tool result, spilling the remainder to a file.

    Truncating alone would lose information the model may need. Truncating
    and handing back a path keeps the context small while leaving the full
    text reachable.
    """
    global _spill_count
    if len(output) <= MAX_TOOL_OUTPUT_CHARS:
        return output

    _spill_count += 1
    spill = ROOT / SPILL_DIR / f"output-{_spill_count}.txt"
    spill.parent.mkdir(parents=True, exist_ok=True)
    spill.write_text(output, encoding="utf-8")

    kept = output[:MAX_TOOL_OUTPUT_CHARS]
    return (
        f"{kept}\n\n"
        f"[truncated: {len(output):,} chars total, {MAX_TOOL_OUTPUT_CHARS:,} shown. "
        f"Full output written to {SPILL_DIR}/{spill.name} - read or grep that file "
        "if you need the rest.]"
    )
```

Reset the counter in `reset_session`:

```python
def reset_session() -> None:
    global _spill_count
    _read_this_session.clear()
    _spill_count = 0
```

Exclude the spill directory from searches, or the agent will find its own output — add `SPILL_DIR` to whatever exclusion list `list_files` uses.

Now apply it in **one** place — the dispatcher in `step09_full_agent.py`:

```python
def run_tool(name: str, args: dict) -> tuple[str, bool]:
    fn = HANDLERS.get(name)
    if fn is None:
        return f"unknown tool: {name}. Available tools: {', '.join(sorted(HANDLERS))}", True
    try:
        return filetools.truncate(fn(**args)), False      # <- wrap here
    except ToolError as e:
        return f"error: {e}", True
    except TypeError as e:
        return f"error: bad arguments for {name}: {e}. Check the tool's schema.", True
```

### What just happened

**Truncation is applied once, in the dispatcher — not in each tool.** Every tool stays ignorant of the context budget and just returns whatever it returns; the layer that owns the conversation owns the budget. Add a tenth tool tomorrow and it is capped automatically.

This is the same reasoning as the error handling in the same function: cross-cutting concerns belong at the boundary, not scattered through every implementation.

**The message tells the model what it can do about it.** `read or grep that file if you need the rest` — an error message and a truncation notice have the same job.

### Run it

```
python -c "
import filetools as f
f.reset_session()
big = 'y' * 60000
open(f.ROOT / 'big.txt', 'w').write(big)
out = f.truncate(f.read_file('big.txt'))
print('returned', len(out), 'chars')
print(out[-200:])
"
```

**Expected:**

```
returned 20145 chars
[truncated: 60,007 chars total, 20,000 shown. Full output written to
.agent-output/output-1.txt - read or grep that file if you need the rest.]
```

### Try this

1. **Give the agent a task that produces huge output** — `"search the workspace for every occurrence of the letter e and summarise"`. Watch the trace. Without truncation this would blow out your context; with it, you get a bounded result and a pointer.
2. **Compare token counts** in `trace.jsonl` for the same task with `MAX_TOOL_OUTPUT_CHARS` set to 20,000 versus 200,000. This is the clearest measurement in the workbook of context as a cost centre.

---

## Step 18 — When "no tool calls" doesn't mean "done"

### Theory

This one was found by running the workbook, not by designing it — which makes it the most honest example in the module.

A Step 11 run produced this trace:

```json
{"turn": 1, "tools": ["list_files"],             "input_tokens": 1621, "output_tokens": 34}
{"turn": 2, "tools": ["read_file", "read_file"], "input_tokens": 1695, "output_tokens": 25}
{"turn": 3, "tools": [],                         "input_tokens": 2964, "output_tokens": 8000}
```

The agent reported success. It had changed nothing. No text, no edits, no error.

Look at turn 3: `output_tokens` is **exactly 8000** — the `max_tokens` value. The model was part-way through generating a large `edit_file` call when it hit the ceiling. The response was cut off mid-block, so the incomplete `tool_use` never arrived. Our loop asked its one question — *are there any tool calls?* — got "no", and exited.

Go back and look at the exit condition you have written five times now:

```python
tool_uses = [b for b in response.content if b.type == "tool_use"]
if not tool_uses:
    return text          # "the model is done"
```

**That is not what "no tool calls" means.** It means *this response contains no tool calls*, which happens for at least three different reasons:

| `stop_reason` | What actually happened | Should the loop stop? |
|---|---|---|
| `end_turn` | The model finished | **Yes** |
| `max_tokens` | Cut off mid-thought | **No** — it was not done |
| `refusal` | The model declined | Yes, but say so |

The API has been telling you which one all along. Since Step 1 you have been printing `stop_reason` and not acting on it.

This is the same class of bug as Step 5's dropped tool result: **a silent failure that looks like success.** Those are the expensive ones, and agents are full of them.

### Code

In `step11_traced_agent.py`, add the check immediately after appending the assistant message:

```python
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return "[the model declined this request]", trace

        # "No tool calls" is NOT the same as "finished". A response cut off at
        # max_tokens has no complete tool_use block either, so a loop that only
        # checks for tool calls treats truncation as success and exits having
        # done nothing at all.
        if response.stop_reason == "max_tokens":
            if verbose:
                print("  ! response truncated at max_tokens - asking it to continue")
            # Record the truncated turn BEFORE continuing, or it vanishes from
            # the trace and you cannot count how often this is happening.
            trace.per_turn.append({
                "turn": turn,
                "tools": [],
                "stop_reason": "max_tokens",
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "text_chars": 0,
            })
            messages.append({
                "role": "user",
                "content": (
                    "Your previous response was cut off at the output limit. "
                    "Continue, but work in smaller steps - make one edit per turn "
                    "rather than emitting a very large tool call."
                ),
            })
            continue
```

Also add `stop_reason` to the normal trace row further down:

```python
        trace.per_turn.append({
            "turn": turn,
            "tools": [t.name for t in tool_uses],
            "stop_reason": response.stop_reason,          # <- add this
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "text_chars": len(text),
        })
```

### What just happened

**We turned a silent failure into a loud one, then recovered from it.** The continuation message is not just a retry — it tells the model *why* it was interrupted and what to do differently, which is Step 14's lesson applied to the loop instead of a tool.

**Raising `max_tokens` is not the fix.** It moves the ceiling; it does not stop you walking into it. Any cap can be hit by a sufficiently large edit, and the failure mode is silent at every value.

### Run it

Force the failure by setting a ridiculous cap, then confirm the recovery:

```python
# temporarily, in step11_traced_agent.py
max_tokens=600,
```

Run the standard task. Without the fix you get an instant, empty "success". With it, you should see `! response truncated at max_tokens` and the agent working in smaller steps. Put `max_tokens` back to 8000 afterwards.

A real run at 600 looked like this — three truncations, all recovered, task completed:

```
turns        : 10
tool calls   : 7 (0 errored)
tokens in    : 41,779      <- 13x the output; recovery is not free
```

Two things worth noticing in that number. **Recovery costs a lot.** Each truncated turn still billed its full 600 output tokens, and the whole conversation was re-sent afterwards — 41,779 input tokens against about 6,000 for the same task at a sane cap. Silent failure is worse, but recovery is not free.

And **the work came out worse.** Forced into small steps, the agent produced tests that did not all pass. A cap tight enough to truncate is a cap tight enough to degrade the output, so treat frequent truncation as a signal to raise the limit — not as a solved problem because the loop no longer lies to you.

### Try this

Add `"stop_reason"` to your trace rows and run the Part A task a few times at the normal cap. How often does `max_tokens` show up? On a model that writes large edits, more often than you would guess — and every one of those was previously an invisible no-op.

---

## Part 5 checkpoint

- [ ] Why does a tool description belong in its own file?
- [ ] What makes an error message good, and who is the audience?
- [ ] Name three levels of enforcement, weakest to strongest.
- [ ] Why does loose matching need a disproportionality guard?
- [ ] Why is truncation applied in the dispatcher rather than in each tool?
- [ ] Name three reasons a response can contain no tool calls. Which one means "done"?
- [ ] How do you turn a collection of agent scripts into an installable CLI command?

---

## What you have built

Seven failures, seven fixes — five in the tool layer, one in the loop, one in the interface:

| Failure | Fix |
|---|---|
| Prompt changes buried in code | Descriptions as versioned text files |
| Model does not know how to recover | Errors that say what to do next |
| Edits based on stale recollection | A guard that refuses, rather than a prompt that asks |
| Turns wasted on near-miss indentation | Ordered fallback matchers with a safety brake |
| One command floods the context | Truncate at the boundary, spill to disk, return a pointer |
| Truncated response read as "finished" | Check `stop_reason`, don't infer it from missing tool calls |
| One-off script with hardcoded task | Interactive CLI packaged and runnable via `loop` |

**The loop still has not changed since Step 6.** Eleven steps later, that is worth saying again — because it is the whole argument of this module. Everything that makes an agent good lives around the loop, not in it.

And the pattern underneath all five is one you can apply to any agent you build or evaluate:

> Watch what the model gets wrong. Then ask whether the tool could have made that mistake impossible, or at least recoverable. Reach for the prompt only when the answer is no.

---

## Step 19 — Make it runnable as the `loop` command

### Theory

So far, running your agent meant launching one-off test scripts like `python step09_full_agent.py` or `python step11_traced_agent.py` with a task hardcoded in Python.

A real coding agent should not be run like a unit test. It should be an interactive command installed in your environment that you can launch from anywhere in your workspace by simply typing:

```
loop
```

We do not need an external template or pre-built repo to do this. We can package what we built step by step right inside `build/`:

1. `build/cli.py` — An interactive REPL that prints the loop banner, displays the configured model and workspace, accepts tasks from an interactive `loop>` prompt, runs `run_agent(task)` from `step11_traced_agent.py`, and prints the trace summary after each task.
2. `build/pyproject.toml` — Standard Python project configuration defining a console script entry point: `loop = "cli:main"`.

When you run `pip install -e .` inside `build/`, Python registers `loop` on your PATH.

### Code

Create `build/cli.py`:

```python
"""Step 19 - Interactive CLI entry point for the coding agent."""

import sys
from config import MODEL
from filetools import ROOT
from step11_traced_agent import run_agent

BANNER = f"""
  ╭───────────╮   loop v1.0
  │  ▸ read   │   a coding agent in ~200 lines
  │  ▸ edit   ├──╮
  │  ▸ test   │  │   {MODEL}
  ╰─────▲─────╯  │   {ROOT.name}
        ╰────────╯

type a task, or 'exit' to quit
"""


def main():
    print(BANNER)
    while True:
        try:
            task = input("loop> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not task:
            continue
        if task.lower() in ("exit", "quit", "q"):
            break

        answer, trace = run_agent(task)
        print(trace.summary())


if __name__ == "__main__":
    main()
```

Create `build/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "loop-agent"
version = "0.1.0"
description = "A coding agent in ~200 lines"
requires-python = ">=3.10"
dependencies = [
    "anthropic",
    "python-dotenv",
    "pytest",
]

[project.scripts]
loop = "cli:main"

[tool.setuptools]
py-modules = [
    "cli",
    "config",
    "filetools",
    "step08_file_agent",
    "step09_full_agent",
    "step10_system_prompt",
    "step11_traced_agent",
]
```

### Run it

Install your agent in editable mode from the `build/` directory:

```
pip install -e .
```

Now launch your coding agent directly with the `loop` command:

```
loop
```

**Expected:**

```
  ╭───────────╮   loop v1.0
  │  ▸ read   │   a coding agent in ~200 lines
  │  ▸ edit   ├──╮
  │  ▸ test   │  │   claude-opus-5
  ╰─────▲─────╯  │   workspace
        ╰────────╯

type a task, or 'exit' to quit

loop> 
```

Type a task at the prompt:

```
loop> Inventory.remove has a bug where quantities go negative. Fix it and run pytest.
```

The agent runs the full loop with your hardened tools, verifies its own fix, displays the trace summary, and returns right back to `loop>` ready for your next task.

---

## Next

The [lab](../lab/assignment.md) asks you to add a tool of your own, break it deliberately, and measure the result. You now have five worked examples of what "a well-built tool" means — apply them to yours.

If you want to see these hardening techniques at production scale, [opencode](https://github.com/anomalyco/opencode) is MIT-licensed and readable: `src/tool/` is where these ideas came from, and `edit.ts` has six more matchers than you just wrote.
