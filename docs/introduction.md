# Before You Start: What Is an AI Coding Agent?

**Read this before Session 1 or Part 1 of the workbook. About 20 minutes.**

You are about to build a coding agent. Before you do, it is worth being precise about what that phrase means — because it is used loosely, it is used to sell things, and the loose version will not survive contact with the code you are about to write.

---

## The short answer

> **A coding agent is a language model in a loop with tools, working against a real codebase until it decides it is finished.**

Every word in that sentence is doing work:

- **in a loop** — it acts more than once, and what it does next depends on what just happened
- **with tools** — it can read files, change them, run commands; it is not confined to producing text
- **a real codebase** — not a snippet in a chat window; your actual project, on disk
- **until it decides** — nobody scripts the number of steps; the model stops when it stops

Take away the loop and you have autocomplete. Take away the tools and you have a chatbot. Take away the codebase and you have a demo. The combination is what is new.

---

## Sixty years of helping programmers type less

The current moment looks like a rupture, and in one specific way it is. But it sits at the end of a long line of tools that all tried to solve the same problem, and understanding that line tells you exactly what changed.

### Lexical help: the editor reads characters

Syntax highlighting, bracket matching, indentation. The editor knows nothing about your program — it is pattern-matching on text. Useful, and completely ignorant.

### Symbolic help: the editor reads types

In 1996, Microsoft shipped IntelliSense in the Visual Basic 5.0 Control Creation Edition, and it spread through Visual Studio from there. Type a dot, get the members of that object.

The insight was that **the compiler already knows the answer.** IntelliSense was not predicting anything; it was surfacing type information the toolchain had computed anyway. That is why it was so reliable — and why it could only ever tell you things that were already provably true. It could complete `customer.` but it could never write the loop around it.

Everything up to about 2018 is a refinement of this idea: better refactoring, static analysis, language servers. Precise, correct, and strictly bounded by what a type system can prove.

### Statistical help: the editor reads other people's code

The 2010s brought completion trained on large corpora rather than derived from types. Suggestions became probabilistic — often right, sometimes nonsense, no longer provable. This was the first crack in the "correct by construction" model, and it made people uncomfortable for good reasons.

### Neural help: the editor reads intent

In August 2021 OpenAI introduced Codex, a model descended from GPT-3 and fine-tuned on publicly available code. GitHub Copilot entered technical preview on 29 June 2021 and became generally available on 21 June 2022.

The shift was categorical. Earlier tools completed *what you were typing*. Copilot completed *what you appeared to be trying to do* — write a comment describing a function, get the function. For the first time the tool was working from intent rather than syntax.

But it was still fundamentally a **completion** system. It suggested; you accepted or rejected; it never found out whether its suggestion worked.

### Conversational help: the tool reads the conversation

ChatGPT arrived in November 2022 and developers immediately used it as a coding surface: paste code, describe a problem, get an answer. Copilot Chat, Cursor and others pulled that conversation into the editor, where the tool could see the file you had open.

Better, and still missing the crucial thing. The model wrote code it never saw run. You were the runtime, the test harness, and the feedback loop — copying output back into the chat by hand.

### Agentic help: the tool closes the loop

The step everyone is now talking about came from a boring-sounding change: **let the model run things and see the results.**

SWE-bench, released in 2023, made the difference measurable. It poses real GitHub issues from real repositories and asks whether a system can produce a patch that passes the project's own tests. When Cognition announced Devin in March 2024, it resolved **13.86%** of SWE-bench issues, against a previous best unassisted baseline of **1.96%**.

Sit with that pair of numbers. The models were not seven times better. The *harness* was. Same class of model, wrapped in a loop with tools, went from "essentially cannot do this" to "sometimes can." A wave of agent scaffolds followed — SWE-agent, OpenHands, Aider, Claude Code, Cursor's agent mode, OpenAI's Codex agent, opencode.

**That gap between 1.96% and 13.86% is what this module is about.** You are going to build the thing that produced it.

---

## The dividing line: does it close a loop?

Forget product categories for a moment. There are three genuinely different kinds of tool, separated by one question — *does the tool find out whether it was right?*

| | Completion | Chat | Agent |
|---|---|---|---|
| **Sees** | Nearby code | The conversation, some files | The repository |
| **Produces** | A suggestion | An answer | Changes on disk |
| **Acts** | No | No | Yes — edits, runs commands |
| **Learns it was wrong** | Never | Only if you tell it | **From the test output** |
| **Steps per request** | One | One | As many as it takes |
| **You are** | The chooser | The runtime | The reviewer |

The bottom-right cell is the whole thing. An agent that edits a file, runs the tests, reads the failure, and edits again is doing something no completion system can do at any model size — because the completion system never gets to find out.

This also explains the failure modes. An agent that cannot run your tests is a chatbot with file access, and it will confidently tell you a change works. **The feedback edge, not the model, is what makes an agent useful** — which is why so much of this course is about tools rather than prompts.

---

## What a coding agent is made of

Here is the part that surprises people. The loop at the centre of every coding agent on the market is about thirty lines of code. You will write it in Part 2 of the workbook, in roughly forty minutes.

Everything else is the **harness** around it. Reading a real production agent — [opencode](https://github.com/anomalyco/opencode) is open source under MIT and worth an afternoon — the rough breakdown looks like this:

| Component | Share of the code | What it is |
|---|---|---|
| **The loop** | ~0% | Call model → run tools → repeat until it stops |
| **System prompt & tool descriptions** | Tiny, huge effect | The behavioural contract |
| **Tool implementations** | ~15% | Robust file ops, search, git, diffs, encodings |
| **Permissions & safety** | ~15% | What runs automatically, what asks, what is refused |
| **Context management** | ~15% | Compaction, pruning, caching, retrieval |
| **Interface** | ~25% | The terminal UI, diffs, streaming, interrupts, sessions |
| **Integrations** | ~20% | MCP, language servers, git, CI, editors |
| **Telemetry & evals** | ~10% | Traces, regression suites, cost accounting |

Two things to take from that table.

**The loop rounds to zero.** Nobody has a secret loop. The differences between products live in the other rows.

**The two rows with the most behavioural leverage per line are the two smallest.** A single sentence in a tool description changes what the agent does on every request, forever. That asymmetry is why this course spends real time on text that is not code.

A few components in more detail, since you will meet them again:

**Tools.** Typically read, write, edit, search, and run-a-command. The interesting design question is not *what* tools but *how many* — an agent with only a shell can do anything, but its harness cannot tell a harmless command from a destructive one. Promoting an action into its own typed tool is what makes it possible to gate, log, or render it.

**The system prompt.** Not personality. It is a behavioural contract, and in a mature agent nearly every line is a scar — a mitigation for something the model did in front of a user. "Read the file before editing it" is not style advice; it encodes a real failure.

**Context management.** The model API is stateless, so the entire conversation is re-sent on every single step. Long runs therefore get expensive in a way that surprises people, and something has to decide what to keep, what to summarise, and what to throw away.

**The permission layer.** The dividing question is *what is reversible?* `git commit` is. `git push --force` is not. `rm -rf` is not. Serious agents gate on that axis rather than on a vague notion of danger.

---

## The landscape

Products move fast and any list dates quickly, so it is more useful to know the **shapes** than the names.

**By where they run:**

- **Terminal agents** — Claude Code, opencode, Aider. The repository is the workspace; the terminal is the interface. Scriptable, composable, no editor lock-in.
- **Editor agents** — Cursor, GitHub Copilot's agent mode, Windsurf, Cline. Tighter feedback with what you are looking at; diffs and approvals rendered inline.
- **Cloud / asynchronous agents** — Devin, OpenAI's Codex agent, background modes in several products. You hand over a task and come back to a pull request.

**By how open they are:** opencode, Aider, OpenHands, SWE-agent and Cline are open source and readable. Claude Code, Cursor, Copilot and Devin are proprietary, though several publish their system prompts. Reading an open one is the fastest way to understand all of them, because they share the same skeleton.

**By autonomy:** some ask before every action, some ask before dangerous ones, some run unattended for hours. This is a configuration choice more often than a product difference, and it is the choice that most affects whether you can trust the output.

> **Currency warning.** This section will age faster than anything else in the course. Treat it as a map of categories, not a buying guide, and check current capabilities yourself. The mechanism you are about to build is stable; the product landscape is not.

---

## What they are genuinely good and bad at

Useful to have calibrated expectations before you start, and this is an area where marketing and reality have diverged.

**Reliably good at:**

- Well-specified changes in a codebase with tests — the tests give it the feedback edge
- Mechanical work at scale: renames, migrations, repetitive refactors
- Working across many files at once, which is where humans lose track
- Explaining unfamiliar code, and finding where something is used
- Writing tests for code that already exists

**Genuinely bad at:**

- Anything underspecified. It will not ask enough; it will guess and proceed
- Work with no feedback signal — no tests, no types, no way to check
- Knowing when to stop. Ask for a bug fix, receive a refactor you did not want
- Reporting its own failures accurately. "All tests pass" is a *claim*, not evidence
- Architectural judgement where the tradeoffs are about your organisation, not the code

**The failure mode to internalise now**, because you will see it within an hour of starting: an agent that says it verified something it never ran. This is not lying. The model produces plausible continuations, and after a set of sensible-looking edits, "and the tests pass" is an extremely plausible next sentence. Nothing in a naive loop forces the check, and nothing compares the claim against what actually happened.

The engineering answer is not to ask the model more nicely. It is to make the failure impossible — a tool that refuses, a hook that blocks, a CI gate that does not care what the summary said. That principle runs through the entire module.

---

## Vocabulary

You will meet these constantly. Worth knowing before they appear in code.

| Term | What it actually means |
|---|---|
| **Token** | The unit models read and bill in, roughly ¾ of a word |
| **Context window** | The maximum tokens one request may contain |
| **Message list** | The whole conversation, re-sent on every request — *everything the model knows* |
| **Stateless** | The API remembers nothing between calls. You resend the history each time |
| **Tool / function calling** | The model emits a structured request; **your** code executes it |
| **`tool_use` / `tool_result`** | The request block, and the answer you send back |
| **Stop reason** | Why generation ended — finished, ran out of tokens, wants a tool, refused |
| **System prompt** | Instructions framing the whole conversation |
| **Prompt caching** | Paying less to re-send an unchanged prefix |
| **Compaction** | Summarising old conversation to fit the window |
| **MCP** | Model Context Protocol — a standard way to expose tools to an agent |
| **Harness / scaffold** | Everything around the model: loop, tools, permissions, interface |

One correction worth making early, because it causes real confusion: **the model never runs anything.** It emits a structured request describing what it wants done, and then stops. Your code decides whether to comply. Every effect an agent has on your machine was produced by a function somebody wrote. That is not a technicality — it is where the entire security boundary lives.

---

## How to read the rest of this module

The order is deliberate.

**Parts 1 and 2** build the mechanism: what an API call really is, and the loop. Resist the urge to skip ahead. Almost every confusing thing later follows from the statelessness in Part 1.

**Part 3** turns it into a coding agent — file access, a sandbox, and the feedback edge.

**Part 4** is about evidence: instrumenting the loop, and an experiment whose result contradicts something you will probably have been told about tool descriptions.

**Part 5** is where it stops being a toy. Six silent failures, each closed in the tool layer rather than the prompt.

Two things to hold onto as you go:

1. **The loop does not change after Part 2.** Everything afterwards is tools, prompt, and measurement. When that keeps being true step after step, notice it — it is the module's central claim, demonstrated rather than asserted.

2. **Build it before you judge it.** You will finish able to evaluate any agent product on its merits, because you will know which parts are hard and which are marketing.

When something in the field confuses you later, the question that resolves most of it is the one you will be able to answer from Part 1 onwards:

> **What is in the message list, and what tools does it have?**

---

## Sources

- [Code completion](https://en.wikipedia.org/wiki/Code_completion) and [IntelliSense History](https://devblogs.microsoft.com/cppblog/intellisense-history-part-1/) — origins of symbolic completion, Visual Basic 5.0, 1996
- [GitHub Copilot](https://en.wikipedia.org/wiki/GitHub_Copilot) and [Copilot general availability](https://techcrunch.com/2022/06/21/copilot-githubs-ai-powered-programming-assistant-is-now-generally-available/) — preview June 2021, GA June 2022, Codex lineage
- [SWE-bench](https://github.com/swe-bench/SWE-bench) — the benchmark that made agent progress measurable
- [Introducing Devin](https://cognition.com/blog/introducing-devin) — the 13.86% vs 1.96% result, March 2024
- [opencode](https://github.com/anomalyco/opencode) — a production coding agent, MIT licensed and worth reading
