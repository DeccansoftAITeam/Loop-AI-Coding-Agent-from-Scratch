# Module 1 Workbook — Build a Coding Agent From Scratch

A hands-on build. You will type (or paste) every line yourself and run each step before moving on. Nothing here refers to pre-written code — by the end, the working agent in `build/` is something **you built**, not something you read.

---

## How this workbook is organised

Nineteen steps across five parts. Every step has the same four beats:

| Beat | What it is |
|---|---|
| **Theory** | The idea, before any code. Read it. |
| **Code** | A complete, runnable file. Copy it whole — never a fragment to splice in. |
| **What just happened** | Line-by-line explanation of the parts that matter. |
| **Run it** | Exact VS Code steps and the output you should see. |

Most steps end with **Try this** — small experiments that take a minute and are where the learning actually lands. Do them.

---

## The build

| Part | Steps | You end up with |
|---|---|---|
| **[1 — The Model](part-1-the-model.md)** | 0–3 | A stateless function you can talk to, and an understanding of what it costs |
| **[2 — Tools](part-2-tools.md)** | 4–6 | A working agent loop — the whole idea, in about 30 lines |
| **[3 — A Coding Agent](part-3-coding-agent.md)** | 7–9 | File tools, a sandbox, and an agent that edits and tests real code |
| **[4 — Production Concerns](part-4-production.md)** | 10–12 | A system prompt, instrumentation, and evidence about what really drives behavior |
| **[5 — Hardening](part-5-hardening.md)** | 13–18 | Six silent failures closed — five in the tools, one in the loop |

Each part builds on the one before. Do them in order.

---

## Before you start

**Read [the introduction](../introduction.md) first** (about 20 minutes). It covers what a coding agent actually is, how the field got from IntelliSense to here, what one is made of, and the vocabulary used throughout. The build makes far more sense with it than without.

You need:

- **Python 3.10 or newer** — check with `python --version`
- **VS Code** with the Microsoft **Python** extension installed
- **An API key** for Ollama Cloud, Anthropic, or any Anthropic-compatible endpoint

Roughly 4–5 hours for all five parts. Parts 1 and 2 alone (about 75 minutes) get you to a working agent loop, which is the core idea — a good stopping point if you are short on time.

---

## Where your files go

Everything you write lands in `build/`, which starts empty. Each step creates one new file:

```
├── .env                       your credentials (Step 0)
├── build/                     ← YOU work here
│   ├── config.py              Step 0
│   ├── step01_hello.py        Step 1
│   ├── ...
│   ├── filetools.py           Steps 7, 9, and 13-17
│   ├── descriptions/          Step 13 - one .txt per tool
│   ├── cli.py                 Step 19 - interactive CLI entry point
│   ├── pyproject.toml         Step 19 - packaging for the loop command
│   └── workspace/             the code your agent edits
```

Files are numbered so you can always go back and re-run an earlier step to compare behavior. Later steps import from earlier ones, so **do not delete them** as you go.

---

## A note on what you are building

The finished agent is about 200 lines. That is not a simplification for teaching — it is genuinely how much code the loop takes. Production coding agents are far larger, but almost none of that size is the loop; it is permissions, interfaces, context management, and integrations built *around* the same 200 lines you are about to write.

That is the point of building it yourself. Once you have, every technique in the rest of the course becomes an engineering decision you can evaluate, rather than a trick you have to take on faith.

Then start with **[Part 1 — The Model](part-1-the-model.md)**.
