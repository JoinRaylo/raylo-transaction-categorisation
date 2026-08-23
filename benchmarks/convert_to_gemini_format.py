"""Convert our Gemma-style {"messages": [system, user, assistant]} training
rows into Gemini's Content/Parts tuning format ({"systemInstruction": ...,
"contents": [user, model]}), per the Gemini supervised-tuning research.

Usage: python convert_to_gemini_format.py <input.jsonl> <output.jsonl> [n_rows]
"""
import json
import sys

src = sys.argv[1]
dst = sys.argv[2]
n_rows = int(sys.argv[3]) if len(sys.argv) > 3 else None

with open(src) as f:
    lines = f.readlines()
if n_rows:
    lines = lines[:n_rows]

converted = []
for line in lines:
    row = json.loads(line)
    msgs = row["messages"]
    system_msg = next(m["content"] for m in msgs if m["role"] == "system")
    user_msg = next(m["content"] for m in msgs if m["role"] == "user")
    assistant_msg = next(m["content"] for m in msgs if m["role"] == "assistant")
    converted.append({
        "systemInstruction": {"role": "system", "parts": [{"text": system_msg}]},
        "contents": [
            {"role": "user", "parts": [{"text": user_msg}]},
            {"role": "model", "parts": [{"text": assistant_msg}]},
        ],
    })

with open(dst, "w") as f:
    for row in converted:
        f.write(json.dumps(row) + "\n")

print(f"Converted {len(converted)} rows -> {dst}", file=sys.stderr)
