# Part 2 — Tools

**Steps 4–6 · about 35 minutes**

The model you built in Part 1 is a brain in a jar. It has no file system, no shell, no network. It cannot do anything at all.

By the end of this part you will have a working agent. The distance between those two sentences is smaller than you think.

---

## Step 4 — The model asks, it does not act

### Theory

Here is the puzzle. The model is a function from text to text. So how does a coding agent edit your files?

The answer is the thing most people get wrong, so read it twice:

> **The model never touches your machine. It emits a structured request describing what it wants done, and then stops. Your code does the work.**

You give the model a list of tools — each a name, a description, and a JSON schema. When the model decides it needs one, it returns a `tool_use` block instead of finishing its turn, and `stop_reason` comes back as `"tool_use"`.

The security consequence is worth writing down now, because Week 7 builds on it: **the security boundary is your dispatch code, not the model.** Every effect an agent has on your system was produced by a function you wrote.

### Code

`code/build/step04_tool_request.py`

```python
"""Step 4 - declare a tool and watch the model ASK for it.

Nothing is executed here. We only look at what comes back.
"""

from config import client, MODEL

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Hyderabad'",
                },
            },
            "required": ["city"],
        },
    }
]

response = client.messages.create(
    model=MODEL,
    max_tokens=2000,
    tools=TOOLS,
    messages=[{"role": "user", "content": "What is the weather in Hyderabad?"}],
)

print(f"stop_reason = {response.stop_reason}\n")

for block in response.content:
    print(f"block type = {block.type}")
    if block.type == "text":
        print(f"  text  : {block.text.strip()[:120]}")
    elif block.type == "tool_use":
        print(f"  id    : {block.id}")
        print(f"  name  : {block.name}")
        print(f"  input : {block.input}")
    print()

print("Note what did NOT happen: no weather was fetched.")
print("The model asked. Nothing ran. There is no weather service here at all.")
```

### What just happened

**`stop_reason` is now `tool_use`**, not `end_turn`. The model stopped early to ask you for something. That value is the signal your loop will run on in Step 6.

**The `tool_use` block has three fields that matter:**

- `id` — a unique handle. You must quote it when returning the result, so the model knows which request the answer belongs to.
- `name` — which tool it wants.
- `input` — the arguments, already parsed into a dict, validated against your schema.

**The `description` field is not documentation for you.** It is the only thing the model reads when deciding whether to call this tool. That single line is doing all the work here — Step 12 is devoted to proving how much.

### Run it

```
python step04_tool_request.py
```

**Expected output:**

```
stop_reason = tool_use

block type = thinking
  ...

block type = tool_use
  id    : call_kc5uo6n1
  name  : get_weather
  input : {'city': 'Hyderabad'}
```

> Tool-use IDs look different across providers — `call_xxxx` on Ollama, `toolu_xxxx` on Anthropic. Never write code that pattern-matches the prefix; just pass the string back unchanged.

### Try this

1. Ask something the tool cannot help with — *"What is 2+2?"* Does the model call it anyway? A well-described tool should not be called here.
2. Change the description to just `"Weather."` and re-run the original question. Does it still work? (Keep the result in mind for Step 12.)
3. Ask for **two** cities in one question. You may get two `tool_use` blocks in a single response — that is parallel tool calling, and Step 6 handles it.

---

## Step 5 — Closing the loop by hand

### Theory

The model asked. Now you answer. Three moves:

1. **Append the assistant's response to the message list — verbatim, every block.** Not just the text. If you drop the `tool_use` block, your next request is malformed and the API rejects it.
2. **Execute the tool yourself.** Plain Python. No framework.
3. **Send the result back** as a `tool_result` block in a **user** message, carrying the same `tool_use_id`.

One rule that catches people later: if the model asked for three tools, all three results go in **one** user message. Splitting them across separate messages teaches the model to stop making parallel calls — a silent, permanent regression, and a real production bug.

### Code

`code/build/step05_tool_result.py`

```python
"""Step 5 - execute the tool and hand the result back. Still no loop."""

from config import client, MODEL

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    }
]


def get_weather(city: str) -> str:
    """Our 'weather service'. A real one would call an API."""
    fake = {"Hyderabad": "34C, hazy", "Bengaluru": "27C, light rain"}
    return fake.get(city, f"No data for {city}")


messages = [{"role": "user", "content": "What is the weather in Hyderabad?"}]

# --- 1. the model asks -----------------------------------------------------
response = client.messages.create(
    model=MODEL, max_tokens=2000, tools=TOOLS, messages=messages
)
print(f"[1] model stopped with: {response.stop_reason}")

tool_use = next(b for b in response.content if b.type == "tool_use")
print(f"[1] it wants: {tool_use.name}({tool_use.input})")

# --- 2. WE execute it ------------------------------------------------------
result = get_weather(**tool_use.input)
print(f"[2] we ran it locally -> {result}")

# --- 3. hand the result back -----------------------------------------------
# The assistant turn goes back VERBATIM - all blocks, not just the text.
messages.append({"role": "assistant", "content": response.content})

# Tool results are a USER message. tool_use_id must match exactly.
messages.append(
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            }
        ],
    }
)

final = client.messages.create(
    model=MODEL, max_tokens=2000, tools=TOOLS, messages=messages
)

print(f"\n[3] model stopped with: {final.stop_reason}")
answer = "".join(b.text for b in final.content if b.type == "text")
print(f"[3] final answer: {answer.strip()}")

print(f"\nThe conversation is now {len(messages)} messages long.")
print("Roles:", [m["role"] for m in messages])
```

### What just happened

**`messages.append({"role": "assistant", "content": response.content})`** — pass `response.content` straight through. Do not extract the text and re-wrap it. The `tool_use` block must survive, and so must any `thinking` block.

**Tool results are a `user` message.** This surprises everyone. Conceptually it makes sense: the model asked a question, and the answer comes from *outside* the model, which is the user side of the conversation.

**`tool_use_id` is the join key.** Match it exactly and pass it through unmodified.

Look at the printed roles at the end: `['user', 'assistant', 'user']`. You have a four-step handshake — ask, request, execute, answer.

### Run it

```
python step05_tool_result.py
```

**Expected output:**

```
[1] model stopped with: tool_use
[1] it wants: get_weather({'city': 'Hyderabad'})
[2] we ran it locally -> 34C, hazy
[3] model stopped with: end_turn
[3] final answer: The weather in Hyderabad is currently 34C and hazy.
```

### Try this

Change the question to ask about **two** cities:

```python
messages = [{"role": "user", "content": "Weather in Hyderabad AND Bengaluru?"}]
```

Run it. You might expect a crash. You will probably get something worse:

```
[1] it wants: get_weather({'city': 'Hyderabad'})
[2] we ran it locally -> 34C, hazy
[3] final answer: Hyderabad: 34°C, hazy. Bengaluru: 34°C, hazy.
                  Both cities are currently at 34°C with hazy conditions.
```

**Bengaluru is 27C and raining.** Look at the dict — the script never called the tool for it.

Here is the mechanism, and it is worth working through carefully:

- The model emitted **two** `tool_use` blocks, one per city.
- `next(b for b in response.content if b.type == "tool_use")` takes the **first** and silently discards the second.
- We sent back one `tool_result` for two requests.
- Nothing complained. The model saw one answer, needed two, and produced a plausible second.

Three lessons, all of which the rest of this workbook builds on:

1. **The bug was in our harness, not the model.** The model asked correctly. We dropped half the question on the floor.
2. **It failed silently.** No exception, no warning — just a confident wrong answer. Silent failures are the expensive kind, and agents are full of them.
3. **A missing tool result gets filled in with something plausible.** That is not the model lying; it is the model doing what it always does — continuing the conversation sensibly given what it can see. If you want it to know a fact, the fact has to be in the message list.

> **Provider note.** Anthropic's API is stricter here and generally rejects a turn where a `tool_use` block has no matching `tool_result`, giving you a loud 400 instead of a quiet fabrication. Ollama Cloud accepts it. Loud is better — but you cannot rely on your provider to catch this for you, which is why Step 6 fixes it properly.

Do not patch it yet. Step 6 handles it, and having seen this failure makes that step obvious rather than arbitrary.

---

## Step 6 — The loop. This is an agent.

### Theory

In Step 5 you did one round trip by hand. What if the model needs another tool after seeing the result?

You do it again. And again. Until it stops asking.

That is the whole thing:

```
messages = [the task]

while True:
    response = model(messages, tools)
    messages.append(response)

    if response contains no tool_use blocks:
        break                                # the model is done

    messages.append(run_every_tool(response))
```

There is no planner. No state machine. No orchestration graph. No supervisor deciding when the task is complete — **the model ends the loop by not asking for another tool.**

This is worth sitting with, because it is genuinely counterintuitive: the autonomy people find impressive in coding agents is an emergent property of a `while` loop wrapped around a stateless function. Everything else in this course is a technique for making this loop behave well over longer horizons.

### Code

`code/build/step06_the_loop.py`

```python
"""Step 6 - the agent loop. This is the whole idea."""

from config import client, MODEL

MAX_TURNS = 10

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
    {
        "name": "get_population",
        "description": "Get the population of a city, in millions.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
]

WEATHER = {"Hyderabad": "34C, hazy", "Bengaluru": "27C, light rain", "Chennai": "36C, humid"}
POPULATION = {"Hyderabad": 10.5, "Bengaluru": 13.6, "Chennai": 11.5}


def run_tool(name: str, args: dict) -> str:
    """Dispatch one tool call. Errors come back as text, never as exceptions."""
    try:
        if name == "get_weather":
            return WEATHER.get(args["city"], f"No weather data for {args['city']}")
        if name == "get_population":
            pop = POPULATION.get(args["city"])
            return f"{pop} million" if pop else f"No population data for {args['city']}"
        return f"error: unknown tool {name}"
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"


def run_agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]

    for turn in range(1, MAX_TURNS + 1):
        response = client.messages.create(
            model=MODEL, max_tokens=4000, tools=TOOLS, messages=messages
        )

        # 1. The assistant turn goes back verbatim, always.
        messages.append({"role": "assistant", "content": response.content})

        text = "".join(b.text for b in response.content if b.type == "text")
        if text.strip():
            print(f"\n[turn {turn}] {text.strip()}")

        # 2. No tool calls? The model is finished. Exit the loop.
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return text

        # 3. Run EVERY requested tool, collect ALL results into ONE message.
        results = []
        for tu in tool_uses:
            print(f"[turn {turn}]   -> {tu.name}({tu.input})")
            output = run_tool(tu.name, tu.input)
            print(f"[turn {turn}]   <- {output}")
            results.append(
                {"type": "tool_result", "tool_use_id": tu.id, "content": output}
            )

        messages.append({"role": "user", "content": results})

    return "[stopped: hit the turn limit]"


if __name__ == "__main__":
    answer = run_agent(
        "Compare Hyderabad and Bengaluru on both weather and population. "
        "Which is more pleasant right now?"
    )
    print("\n" + "=" * 60)
    print(answer)
```

### What just happened

You just wrote an agent. Thirty lines of loop.

**The exit condition is the model's silence.** `if not tool_uses: return`. Nothing else decides the task is complete.

**`for turn in range(1, MAX_TURNS + 1)`** instead of `while True`. A model can get stuck retrying a failing tool forever; the cap is a real production concern, not a toy guard.

**Errors are returned as text, not raised.** Look at `run_tool` — every failure becomes a string the model reads. If a tool exception killed the loop, you would throw away the agent's most useful property: seeing a failure and trying something else. A traceback here is information, and it belongs in the conversation.

**All results in one message.** The `results` list is built up and appended once, after the `for` loop over `tool_uses`. This is the rule from Step 5, now load-bearing.

### Run it

```
python step06_the_loop.py
```

**Expected output** — the shape matters more than the wording:

```
[turn 1] I'll gather the current weather and population data for both cities.
[turn 1]   -> get_weather({'city': 'Hyderabad'})
[turn 1]   <- 34C, hazy
[turn 1]   -> get_weather({'city': 'Bengaluru'})
[turn 1]   <- 27C, light rain
[turn 1]   -> get_population({'city': 'Hyderabad'})
[turn 1]   <- 10.5 million
[turn 1]   -> get_population({'city': 'Bengaluru'})
[turn 1]   <- 13.6 million

[turn 2] Here's the comparison:
...
Verdict: Bengaluru is more pleasant right now
```

Two things worth pausing on.

**It planned.** Nobody told it to fetch weather before population, or to gather all four facts before answering. It worked out what the question needed and got it.

**It called four tools in one turn.** That is parallel tool calling — the thing that broke Step 5's `next(...)`, now handled by iterating `tool_uses` and batching the results. On a real codebase this is what lets an agent read six files at once instead of six turns in a row.

The whole task took **two turns**: one to gather, one to answer.

### Try this

1. **Ask about a city that is not in the dicts** — *"What about Kolkata?"* Watch the tool return an error string and the model handle it gracefully instead of crashing. That is error recovery, and it is why errors are results.
2. **Set `MAX_TURNS = 1`** and ask the comparison question. You get the turn-limit message — the loop was doing real work.
3. **Add a third tool** — `get_timezone`, say — with a good description, and ask a question that needs all three.
4. **Break the rule deliberately.** Append each tool result as its own separate message instead of batching them. Does the model still make parallel calls? This is the silent regression, reproduced.

---

## Part 2 checkpoint

You should now be able to answer these without looking:

- [ ] What does the model actually do when it "uses a tool"?
- [ ] What ends the agent loop?
- [ ] Why must all tool results go in one message?
- [ ] Why are tool errors returned rather than raised?
- [ ] Where is the security boundary of an agent?

Files in `code/build/`: Part 1's four, plus `step04_tool_request.py`, `step05_tool_result.py`, `step06_the_loop.py`.

**You have built an agent.** It is a real one — the loop is not a simplified version of what Claude Code or Cursor do, it is the same loop.

What it lacks is useful tools. Weather dictionaries are not a codebase. Part 3 replaces them with file access, a shell, and a sandbox — and turns this into something that edits and tests real code.

**Next: [Part 3 — A Coding Agent](part-3-coding-agent.md)**
