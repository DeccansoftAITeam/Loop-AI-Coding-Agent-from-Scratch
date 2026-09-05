"""Step 2 - a conversation is a list you keep re-sending."""

from config import client, MODEL

messages = []

QUESTIONS = [
    "In one sentence, what is a race condition?",
    "Show me a short Python example of one.",
    "How would you fix that example?",
]

total_in = 0
total_out = 0

for turn, question in enumerate(QUESTIONS, start=1):
    messages.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=messages,
    )

    answer = "".join(b.text for b in response.content if b.type == "text")

    # THIS is the only reason the model has any memory at all:
    # we append its reply to our list and send it again next time.
    messages.append({"role": "assistant", "content": answer})

    total_in += response.usage.input_tokens
    total_out += response.usage.output_tokens

    print(f"=== turn {turn} ===")
    print(f"messages sent : {len(messages) - 1}")
    print(f"input tokens  : {response.usage.input_tokens}")
    print(f"Q: {question}")
    print(f"A: {answer[:150].strip()}...")
    print()

print("--- the list the model received on the LAST call ---")
for m in messages[:-1]:
    print(f"  {m['role']:>9}: {str(m['content'])[:70].strip()}")

print(f"\ntotal input tokens  = {total_in}")
print(f"total output tokens = {total_out}")
print(
    "\nInput tokens climbed every turn. You paid to re-send the whole\n"
    "conversation each time. That is the economics of agents in one number."
)