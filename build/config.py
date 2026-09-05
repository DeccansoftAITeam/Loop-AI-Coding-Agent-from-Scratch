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