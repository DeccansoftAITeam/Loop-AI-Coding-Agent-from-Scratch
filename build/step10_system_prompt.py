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