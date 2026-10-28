"""Count forbidden paths in an agent's own tool-call inputs (not its prompt, not tool results).

Usage: python isolation_check.py <transcript.jsonl> <forbidden substring> [...]
Prints counts only. A zero count cannot prove an agent never saw a file; it shows that no
tool call the agent made named one.
"""

import json
import sys


def tool_inputs(path):
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = ev.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield json.dumps(block.get("input", {}))


def main():
    path, forbidden = sys.argv[1], sys.argv[2:]
    calls = list(tool_inputs(path))
    counts = {f: sum(f in c for c in calls) for f in forbidden}
    print(json.dumps({"tool_calls": len(calls), "forbidden_hits": counts}))


if __name__ == "__main__":
    main()
