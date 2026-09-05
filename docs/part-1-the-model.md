# Part 1 — The Model

**Steps 0–3 · about 40 minutes**

Before you can build an agent you need to know exactly what a language model API is. Not roughly — exactly. Almost every confusing thing about agents later on follows from the answer.

---

## Step 0 — Setup

### Theory

Two rules for credentials, and they are not bureaucracy:

**Never put a key in your source code.** It ends up in git, and git never forgets. Rotating a leaked key is a bad afternoon.

**Never put it in your shell profile either.** It leaks into every process you launch, including ones you did not think about.

Instead: a `.env` file that is git-ignored, read at startup. This is universal practice, and you should build the habit now rather than after your first incident.

### Code

**File 1 of 3** — `code/.env`

```
ANTHROPIC_BASE_URL=https://ollama.com
ANTHROPIC_AUTH_TOKEN=paste-your-key-here
MINIAGENT_MODEL=glm-5.3-flash:cloud
```

<details>
<summary>Using Anthropic directly instead?</summary>

```
ANTHROPIC_API_KEY=sk-ant-...
MINIAGENT_MODEL=claude-opus-5
```

Use **one** of the two blocks, never both. In particular do not set `ANTHROPIC_API_KEY=""` alongside `ANTHROPIC_AUTH_TOKEN` — an empty string still occupies the SDK's precedence slot and you will get a confusing 401.
</details>

**File 2 of 3** — `code/.gitignore`

```
.env
__pycache__/
*.pyc
.venv/
trace.jsonl
.pytest_cache/
.agent-output/
```

The last three are for files later steps produce — a trace log, pytest's cache, and output your agent spills to disk. Add them now so you never accidentally commit them.

**File 3 of 3** — `code/build/config.py`

```python
"""Shared setup for every step in this workbook.

Every later file starts with:  from config import client, MODEL
"""

import os
import sys
from pathlib import Path

import anthropic

# --- Windows consoles die on model output without this ---------------------
# Models emit arrows, smart quotes and emoji freely. A cp1252 console raises
# UnicodeEncodeError on them - after you have already paid for the tokens.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# --- Load .env into the environment ----------------------------------------
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# --- Build the client -------------------------------------------------------
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("MINIAGENT_MODEL", "claude-opus-5")

if not (TOKEN or API_KEY):
    sys.exit(f"No credentials. Create {ENV_FILE} - see Step 0 of the workbook.")

_kwargs = {"timeout": 600.0}
if BASE_URL:
    _kwargs["base_url"] = BASE_URL
if TOKEN:
    _kwargs["auth_token"] = TOKEN
    _kwargs["api_key"] = None
else:
    _kwargs["api_key"] = API_KEY

client = anthropic.Anthropic(**_kwargs)

if __name__ == "__main__":
    print(f"model    = {MODEL}")
    print(f"base_url = {BASE_URL or 'https://api.anthropic.com (default)'}")
    print(f"auth     = {'auth_token' if TOKEN else 'api_key'}")
    print("config OK")
```

### What just happened

The `.env` loader is fifteen lines, so you can see there is no magic in it. It uses `setdefault`, which means **a real environment variable always wins over the file** — that lets an instructor override the model for one demo without editing anyone's `.env`.

The `reconfigure` block at the top is not boilerplate you can skip. On Windows, printing model output will eventually crash without it.

The `api_key=None` when a token is present is deliberate. The SDK checks `api_key` before `auth_token`, so leaving an empty key in place would authenticate with nothing.

### Run it

1. Open VS Code. **File → Open Folder** → select the `code` folder.
2. Open a terminal: **Ctrl + `** (backtick). It opens in `code/`.
3. Create the virtual environment and install the SDK:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install anthropic pytest
   ```

   On macOS or Linux the second line is `source .venv/bin/activate`.

4. Select the interpreter so VS Code uses the venv: **Ctrl+Shift+P** → `Python: Select Interpreter` → pick the one with `.venv` in the path. This is what makes the green Run button work correctly.
5. Create the three files above. **Ctrl+N**, paste, **Ctrl+S**, save with the right name in the right folder.
6. Run:

   ```
   python build\config.py
   ```

**Expected output:**

```
model    = glm-5.3-flash:cloud
base_url = https://ollama.com
auth     = auth_token
config OK
```

> **Keep the venv activated.** Every terminal you use for the rest of this workbook needs `(.venv)` at the start of the prompt. If it disappears — you opened a new terminal — run `.venv\Scripts\activate` again.

---

## Step 1 — One API call

### Theory

Here is the entire mental model, and it is smaller than most people expect:

> **A language model API call is a pure function. A list of messages goes in. One message comes out.**

No session. No connection state. No memory. The server handles your request and forgets you completely.

That single fact is the root of nearly everything you will deal with later: why conversations cost more as they get longer, why context windows matter, why prompt caching exists, why agents "forget," and why you have total control over what the model sees.

### Code

`code/build/step01_hello.py`

```python
"""Step 1 - the smallest possible call."""

from config import client, MODEL

response = client.messages.create(
    model=MODEL,
    max_tokens=1000,
    messages=[
        {"role": "user", "content": "In one sentence, what is a race condition?"}
    ],
)

print("--- raw response object ---")
print(f"id           = {response.id}")
print(f"model        = {response.model}")
print(f"stop_reason  = {response.stop_reason}")
print(f"content      = {len(response.content)} block(s)")
for block in response.content:
    print(f"  - type={block.type}")

print("\n--- the text ---")
for block in response.content:
    if block.type == "text":
        print(block.text)

print("\n--- what it cost ---")
print(f"input tokens  = {response.usage.input_tokens}")
print(f"output tokens = {response.usage.output_tokens}")
```

### What just happened

**`messages` is a list, always.** Even for a single question. The API has exactly one input shape and you will be building this list for the rest of the course.

**`response.content` is a list of blocks, not a string.** Look at your own output — you very likely got **two** blocks:

```
content      = 2 block(s)
  - type=thinking
  - type=text
```

That is the model's reasoning block, followed by its answer. A response can contain `text`, `thinking`, `tool_use`, or several of each, in an order you do not control.

So `response.content[0].text` — the obvious thing to write — **crashes here**, because block 0 is a `thinking` block with no `.text` attribute. This is the single most common beginner bug against this API, and you just saw why. Always filter by `block.type`, exactly as the loop at the bottom of the script does.

**`stop_reason` tells you why it stopped.** Right now it says `end_turn` — it finished naturally. In Step 4 you will see `tool_use`, and that value is what drives the entire agent loop.

**`max_tokens` is a hard ceiling on the response**, not a target. If output gets truncated you will see `stop_reason: "max_tokens"`.

### Run it

```
cd build
python step01_hello.py
```

**Expected output** (yours will differ in wording):

```
--- raw response object ---
id           = msg_cf411b854df4510ede554e86
model        = glm-5.3-flash:cloud
stop_reason  = end_turn
content      = 2 block(s)
  - type=thinking
  - type=text

--- the text ---
A race condition is a software bug that occurs when two or more threads
access shared data concurrently, and the outcome depends on timing.

--- what it cost ---
input tokens  = 22
output tokens = 194
```

> **`ModuleNotFoundError: No module named 'config'`** means you are not in the `build` directory. `cd build` first — `from config import ...` looks in the current directory.

### Try this

1. **Add `print(response.content[0].text)` at the end and run it.** It will probably crash with `AttributeError`. That is the block-type lesson, felt rather than read.
2. Change the question to something long: *"Explain the CAP theorem with examples."* Watch `output tokens` grow.
3. Set `max_tokens=20` and run again. Look at `stop_reason`.
4. Run the script twice unchanged. **The answers differ.** These systems are non-deterministic — hold on to that, it matters in Step 12.

---

## Step 2 — Statelessness, and what it costs

### Theory

If the API has no memory, how does a conversation work?

**You send the entire history, every single time.** Turn 1 sends one message. Turn 5 sends nine. Turn 20 sends thirty-nine — including every word of every earlier exchange.

The consequences are worth stating plainly, because all three come back repeatedly:

1. **Everything the model knows about your task is in that list.** There is no hidden state to appeal to. If the agent does not know something, it is because you did not put it there.
2. **You pay to re-upload it, every turn.** Input tokens grow with conversation length, so cost grows *quadratically* over a long agent run.
3. **You control it completely.** Because there is no server state, the list is yours to edit, prune, summarize, or replay. Every advanced technique later in this course is an exercise of that control.

### Code

`code/build/step02_conversation.py`

```python
"""Step 2 - a conversation is a list you keep re-sending."""

from config import client, MODEL

messages = []

QUESTIONS = [
    "In one sentence, what is a race condition?",
    "Show me a short Python example of one.",
    "How would you fix that example?",
]

total_in = 0
total_out = 0

for turn, question in enumerate(QUESTIONS, start=1):
    messages.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=messages,
    )

    answer = "".join(b.text for b in response.content if b.type == "text")

    # THIS is the only reason the model has any memory at all:
    # we append its reply to our list and send it again next time.
    messages.append({"role": "assistant", "content": answer})

    total_in += response.usage.input_tokens
    total_out += response.usage.output_tokens

    print(f"=== turn {turn} ===")
    print(f"messages sent : {len(messages) - 1}")
    print(f"input tokens  : {response.usage.input_tokens}")
    print(f"Q: {question}")
    print(f"A: {answer[:150].strip()}...")
    print()

print("--- the list the model received on the LAST call ---")
for m in messages[:-1]:
    print(f"  {m['role']:>9}: {str(m['content'])[:70].strip()}")

print(f"\ntotal input tokens  = {total_in}")
print(f"total output tokens = {total_out}")
print(
    "\nInput tokens climbed every turn. You paid to re-send the whole\n"
    "conversation each time. That is the economics of agents in one number."
)
```

### What just happened

Look closely at the append:

```python
messages.append({"role": "assistant", "content": answer})
```

**We** add the model's reply to **our** list. The server did nothing. Delete that line and the model becomes an amnesiac that answers each question as if the previous ones never happened.

That is worth internalising: "the model remembered what I said" always means "my code re-sent it." When you hear someone say a model "learned their codebase," the accurate translation is that somebody put the codebase in the message list, and paid for it.

### Run it

```
python step02_conversation.py
```

Watch the `input tokens` line across the three turns. It only goes up.

### Try this

1. **Comment out the `messages.append({"role": "assistant", ...})` line** and run again. The model loses the thread completely. This is the single most useful experiment in Part 1 — do it.
2. Add three more questions to the list. Watch the input tokens on the final turn.
3. Print `len(str(messages))` each turn to see the raw payload growing.

---

## Step 3 — Streaming

### Theory

The call in Step 2 blocked until the model finished. For a one-sentence answer that is fine. For an agent that thinks for two minutes, it is unusable — the user stares at a frozen screen, and long requests risk an HTTP timeout.

Streaming sends tokens as they are generated. Two reasons you want it:

- **Perceived speed.** Output starts immediately instead of after the full generation.
- **Reliability.** Large `max_tokens` on a non-streaming request can exceed the HTTP timeout. Streaming keeps the connection active.

The SDK helper does the accumulation for you, so you get live output *and* a complete response object at the end.

### Code

`code/build/step03_streaming.py`

```python
"""Step 3 - stream tokens as they arrive."""

from config import client, MODEL

print("--- streaming ---")

with client.messages.stream(
    model=MODEL,
    max_tokens=2000,
    messages=[
        {"role": "user", "content": "List 5 causes of flaky tests, one line each."}
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

    # The stream also accumulates the full Message for you.
    final = stream.get_final_message()

print("\n\n--- and the complete object is still available ---")
print(f"stop_reason   = {final.stop_reason}")
print(f"output tokens = {final.usage.output_tokens}")
print(f"blocks        = {[b.type for b in final.content]}")
```

### What just happened

**`with ... as stream:`** — the context manager guarantees the connection closes even if your loop raises.

**`stream.text_stream`** yields text fragments as they arrive. `flush=True` forces them to the terminal immediately instead of sitting in a buffer.

**`stream.get_final_message()`** is the important part. You do not have to choose between streaming and having a usable response object — you get both. Everything you learned in Steps 1 and 2 still applies.

From here on, every call in this workbook streams.

### Run it

```
python step03_streaming.py
```

You should see text appear progressively rather than all at once.

### Try this

Remove `flush=True` and run again. On most terminals the output arrives in lumps — you are watching Python's output buffer, not the network.

---

## Part 1 checkpoint

You should now be able to answer these without looking:

- [ ] On turn 10 of a conversation, how much gets sent to the model?
- [ ] What actually gives a conversation its memory?
- [ ] Why is `response.content` a list rather than a string?
- [ ] What does `stop_reason` tell you, and why will it matter?

Files in `code/build/`: `config.py`, `step01_hello.py`, `step02_conversation.py`, `step03_streaming.py`.

You have a stateless function you can talk to. It cannot do anything yet — it cannot read a file, run a command, or touch your machine in any way. Fixing that is Part 2, and it is where this becomes an agent.

**Next: [Part 2 — Tools](part-2-tools.md)**
