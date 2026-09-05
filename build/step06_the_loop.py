"""Step 6 - the agent loop. This is the whole idea."""

from config import client, MODEL

MAX_TURNS = 10

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
    {
        "name": "get_population",
        "description": "Get the population of a city, in millions.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
]

WEATHER = {"Hyderabad": "34C, hazy", "Bengaluru": "27C, light rain", "Chennai": "36C, humid"}
POPULATION = {"Hyderabad": 10.5, "Bengaluru": 13.6, "Chennai": 11.5}


def run_tool(name: str, args: dict) -> str:
    """Dispatch one tool call. Errors come back as text, never as exceptions."""
    try:
        if name == "get_weather":
            return WEATHER.get(args["city"], f"No weather data for {args['city']}")
        if name == "get_population":
            pop = POPULATION.get(args["city"])
            return f"{pop} million" if pop else f"No population data for {args['city']}"
        return f"error: unknown tool {name}"
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"


def run_agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]

    for turn in range(1, MAX_TURNS + 1):
        response = client.messages.create(
            model=MODEL, max_tokens=4000, tools=TOOLS, messages=messages
        )

        # 1. The assistant turn goes back verbatim, always.
        messages.append({"role": "assistant", "content": response.content})

        text = "".join(b.text for b in response.content if b.type == "text")
        if text.strip():
            print(f"\n[turn {turn}] {text.strip()}")

        # 2. No tool calls? The model is finished. Exit the loop.
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return text

        # 3. Run EVERY requested tool, collect ALL results into ONE message.
        results = []
        for tu in tool_uses:
            print(f"[turn {turn}]   -> {tu.name}({tu.input})")
            output = run_tool(tu.name, tu.input)
            print(f"[turn {turn}]   <- {output}")
            results.append(
                {"type": "tool_result", "tool_use_id": tu.id, "content": output}
            )

        messages.append({"role": "user", "content": results})

    return "[stopped: hit the turn limit]"


if __name__ == "__main__":
    answer = run_agent(
        "Compare Hyderabad and Bengaluru on both weather and population. "
        "Which is more pleasant right now?"
    )
    print("\n" + "=" * 60)
    print(answer)