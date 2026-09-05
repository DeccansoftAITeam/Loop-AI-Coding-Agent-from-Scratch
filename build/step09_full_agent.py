"""Step 9 - an agent that edits code and verifies its own work."""

from config import client, MODEL
import filetools
from filetools import ROOT, ToolError
from step08_file_agent import TOOLS as BASE_TOOLS, HANDLERS as BASE_HANDLERS
from filetools import describe
MAX_TURNS = 20

TOOLS = BASE_TOOLS + [
    {
        "name": "edit_file",
        "description": describe("edit_file"),
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
        "description": describe("bash"),
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
        return f"unknown tool: {name}. Available tools: {', '.join(sorted(HANDLERS))}", True
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