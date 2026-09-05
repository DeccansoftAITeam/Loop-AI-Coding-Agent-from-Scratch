"""Step 8 - the Part 2 loop, with real file tools."""

from config import client, MODEL
import filetools
from filetools import ROOT, ToolError
from filetools import describe

MAX_TURNS = 15

TOOLS = [
    {
        "name": "list_files",
        "description": describe("list_files"),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob, e.g. '*.py'. Default '*'."}
            },
        },
    },
    {
        "name": "read_file",
        "description": describe("read_file"),
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
        "description": describe("write_file"),
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