"""Step 3 - stream tokens as they arrive."""

from config import client, MODEL

print("--- streaming ---")

with client.messages.stream(
    model=MODEL,
    max_tokens=2000,
    messages=[
        {"role": "user", "content": "List 5 causes of flaky tests, one line each."}
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

    # The stream also accumulates the full Message for you.
    final = stream.get_final_message()

print("\n\n--- and the complete object is still available ---")
print(f"stop_reason   = {final.stop_reason}")
print(f"output tokens = {final.usage.output_tokens}")
print(f"blocks        = {[b.type for b in final.content]}")