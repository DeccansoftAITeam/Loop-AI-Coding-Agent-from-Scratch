"""Step 1 - the smallest possible call."""

from config import client, MODEL

response = client.messages.create(
    model=MODEL,
    max_tokens=1000,
    messages=[
        {"role": "user", "content": "In one sentence, what is a race condition?"}
    ],
)

print("--- raw response object ---")
print(f"id           = {response.id}")
print(f"model        = {response.model}")
print(f"stop_reason  = {response.stop_reason}")
print(f"content      = {len(response.content)} block(s)")
for block in response.content:
    print(f"  - type={block.type}")

print("\n--- the text ---")
for block in response.content:
    if block.type == "text":
        print(block.text)

print("\n--- what it cost ---")
print(f"input tokens  = {response.usage.input_tokens}")
print(f"output tokens = {response.usage.output_tokens}")