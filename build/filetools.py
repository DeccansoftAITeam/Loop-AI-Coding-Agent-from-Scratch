

"""File tools, confined to a single workspace directory.

Imported by steps 8 and 9. Not run directly (except for the self-test
at the bottom).
"""

import os
import sys
from pathlib import Path

# Anchored to THIS file, not to the current directory. A CWD-relative default
# silently points the sandbox somewhere else the moment you run a step from
# another folder - and a wrong ROOT that never raises is exactly the kind of
# quiet failure this workbook is about.
ROOT = Path(os.environ.get("AGENT_ROOT") or Path(__file__).parent / "workspace").resolve()

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

class ToolError(Exception):
    """A mistake the model made. Reported back to it, never raised at the loop."""


def _safe(path_str: str) -> Path:
    """Resolve a model-supplied path and refuse anything outside ROOT.

    The most important eight lines in this workbook. Note the ORDER:
    resolve first (which collapses '..' and follows symlinks), then check
    containment. Checking a raw string prefix is the classic bug.
    """
    candidate = Path(path_str)
    p = (candidate if candidate.is_absolute() else ROOT / candidate).resolve()
    if not p.is_relative_to(ROOT):
        raise ToolError(
            f"path escapes the workspace: {path_str}. "
            "Use a workspace-relative path; you cannot reach outside the workspace."
        )
    return p


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace(os.sep, "/")


def read_file(path: str) -> str:
    p = _safe(path)
    if not p.exists():
        raise ToolError(f"no such file: {path}. Use list_files to see what exists before reading.")
    if p.is_dir():
        raise ToolError(f"{path} is a directory. Use list_files('{path}/*') to list it.")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    # Line numbers are not decoration - they are how the model addresses a
    # location later, and how it reports findings back to you as file:line.
    return "\n".join(f"{i:6d}\t{line}" for i, line in enumerate(lines, 1)) or "(empty)"


def write_file(path: str, content: str) -> str:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    p.write_text(content, encoding="utf-8")
    return f"{'overwrote' if existed else 'created'} {_rel(p)} ({len(content)} chars)"


def list_files(pattern: str = "*") -> str:
    hits = [_rel(p) for p in sorted(ROOT.rglob(pattern))
            if p.is_file() and "__pycache__" not in _rel(p)]
    return "\n".join(hits) or f"no files match {pattern}"


if __name__ == "__main__":
    print(f"ROOT = {ROOT}\n")
    print("list_files('*.py'):")
    print(list_files("*.py"))
    print("\nread_file('inventory.py') - first lines:")
    print("\n".join(read_file("inventory.py").splitlines()[:6]))
    print("\nnow the sandbox:")
    for bad in ["../config.py", "../../../../etc/passwd", "/etc/passwd"]:
        try:
            read_file(bad)
            print(f"  {bad:32s} ESCAPED - this is a bug!")
        except ToolError as e:
            print(f"  {bad:32s} blocked: {e}")
 
import subprocess

BASH_TIMEOUT_S = 30


def edit_file(path: str, old: str, new: str) -> str:
    """Replace exactly one occurrence of `old` with `new`.

    Requiring uniqueness is the safety property: a failed match means the
    model's view of the file is stale, which you want to hear about.
    """
    p = _safe(path)
    if not p.exists():
        raise ToolError(f"no such file: {path}")
    text = p.read_text(encoding="utf-8")
    hits = text.count(old)
    if hits == 0:
        raise ToolError(
            "old string not found - read the file again; it may have changed, "
            "or your copy has different whitespace or indentation."
        )
    if hits > 1:
        raise ToolError(
            f"old string appears {hits} times; include more surrounding "
            "lines to make it unique."
        )
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"edited {_rel(p)}"


def bash(command: str) -> str:
    """Run a shell command inside the workspace."""
    # Put the interpreter running this agent first on PATH, so the `python`
    # the model invokes is the one your packages are installed into. Without
    # it, `python -m pytest` finds a system Python with no pytest whenever the
    # venv is not activated - which VS Code's green Run button does not do.
    env = {
        **os.environ,
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
    }
    try:
        proc = subprocess.run(
            command, shell=True, cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=BASH_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(
            f"command timed out after {BASH_TIMEOUT_S}s. If it was waiting for input, "
            "re-run it with a non-interactive flag."
        )
    out = ((proc.stdout or "") + (proc.stderr or ""))[:20000]
    return f"exit={proc.returncode}\n{out or '(no output)'}"           