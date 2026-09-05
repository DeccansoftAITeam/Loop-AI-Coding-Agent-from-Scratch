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