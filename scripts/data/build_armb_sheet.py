"""Arm B (docs/real_world_check.md): build the blind labeling sheet from data/labeling/armb/*_items.jsonl.

Writes data/labeling/armb/labeling_sheet.csv. One row per item. Columns: id, domain, scenario, options
(shown as "code: text" lines in a seeded random order, so list position does not hint at the answer),
acceptable (labeler fills in: one or more codes, separated by "|"), unsure (y/n), notes.
The answer key is NOT read here. Each labeler copies the sheet and fills it alone. Do not discuss answers
until both are done. Rules: docs/labeling.md.

Also validates the item files. Usage: python3 scripts/data/build_armb_sheet.py
"""
import csv, glob, json, random

D = "data/labeling/armb/"
items = []
for f in sorted(glob.glob(D + "*_items.jsonl")):
    items += [json.loads(l) for l in open(f) if l.strip()]
assert len({s["id"] for s in items}) == len(items), "duplicate ids"
rng = random.Random(1684)
with open(D + "labeling_sheet.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "domain", "scenario", "options", "acceptable", "unsure", "notes"])
    order = list(items); rng.shuffle(order)            # item order mixed across domains too
    for s in order:
        assert s["options"][-1] == "need_more_information" and set(s["options"]) == set(s["option_text"]), s["id"]
        opts = list(s["options"]); rng.shuffle(opts)
        w.writerow([s["id"], s["domain"], s["prompts"]["base"],
                    "\n".join(f"{c}: {s['option_text'][c]}" for c in opts), "", "", ""])
print(f"wrote {D}labeling_sheet.csv with {len(items)} items")
