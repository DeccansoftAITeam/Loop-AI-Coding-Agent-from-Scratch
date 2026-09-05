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


messages = [{"role": "user", "content": "Weather in Hyderabad AND Bengaluru?"}]

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