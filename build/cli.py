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