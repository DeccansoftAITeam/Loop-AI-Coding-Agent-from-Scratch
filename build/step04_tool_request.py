"""Step 4 - declare a tool and watch the model ASK for it.

Nothing is executed here. We only look at what comes back.
"""

from config import client, MODEL

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Hyderabad'",
                },
            },
            "required": ["city"],
        },
    }
]

response = client.messages.create(
    model=MODEL,
    max_tokens=2000,
    tools=TOOLS,
    messages=[{"role": "user", "content": "What is the weather in Hyderabad?"}],
)

print(f"stop_reason = {response.stop_reason}\n")

for block in response.content:
    print(f"block type = {block.type}")
    if block.type == "text":
        print(f"  text  : {block.text.strip()[:120]}")
    elif block.type == "tool_use":
        print(f"  id    : {block.id}")
        print(f"  name  : {block.name}")
        print(f"  input : {block.input}")
    print()

print("Note what did NOT happen: no weather was fetched.")
print("The model asked. Nothing ran. There is no weather service here at all.")