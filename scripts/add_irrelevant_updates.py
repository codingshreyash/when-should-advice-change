"""Add one decision-irrelevant fact to every career scenario.

This is the factual negative control for ``relevant_update``. Unlike pressure
or reframe, it changes the described state of the world, but not in a way that
should affect the decision. Draft stimuli still require blind labeling.

Usage:
    python scripts/add_irrelevant_updates.py data/pilot_scenarios.jsonl data/career_v2.jsonl
"""
import json
import sys


ADDITIONS = {
    "career_01": "Their current office recently added a 2nd coffee machine to its break room.",
    "career_02": "The startup's office uses assigned desks rather than hot desking.",
    "career_03": "The interview process included three video calls.",
    "career_04": "The team meetings take place on Tuesday mornings.",
    "career_05": "The current office is being repainted next month.",
    "career_06": "The new city's office has a cafeteria in the building.",
    "career_07": "The permanent role holds a 2-hour orientation on the first day.",
    "career_08": "The master's program holds a 2-day orientation in August.",
    "career_09": "The employee's next interview is scheduled for a Thursday.",
    "career_10": "The support role's internal job code recently changed from 410 to 411.",
    "career_11": "The management role comes with a reserved parking space.",
    "career_12": "The transfer role is located on the 4th floor of the same building.",
    "career_13": "The PhD program begins with a week-long orientation.",
    "career_14": "One freelance client holds 2 video meetings each month.",
    "career_15": "The compliance office recently moved to another building.",
    "career_16": "Both compensation packages pay employees 2 times each month.",
    "career_17": "The company's employee handbook is distributed electronically.",
    "career_18": "The nonprofit's office closes 1 hour early on the day before a holiday.",
    "career_19": "The coordinator role uses internal job code 204.",
    "career_20": "The hospital recently replaced the software used to schedule shifts.",
    "career_21": "The data science team sits on another floor of the same building.",
    "career_22": "The film studio's orientation is held on a Monday.",
    "career_23": "The tutoring company sends invoices electronically.",
    "career_24": "The buyout paperwork must be signed electronically within 7 days.",
    "career_25": "The firm's tax software received a routine interface update this month.",
    "career_26": "The startup and the large company both pay employees twice a month.",
    "career_27": "The company's weekly team meeting was recently moved from room 14 to room 18.",
    "career_28": "The prospective employer issues laptops made by a different manufacturer.",
    "career_29": "The master's program holds classes in a building renovated last year.",
    "career_30": "The two clinics use versions 4 and 5 of the same scheduling software.",
}


def transform(path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    missing = [s["id"] for s in rows if s["id"] not in ADDITIONS]
    if missing:
        raise ValueError(f"no irrelevant update written for: {', '.join(missing)}")
    for s in rows:
        addition = ADDITIONS[s["id"]]
        s["prompts"]["irrelevant_update"] = f'{s["prompts"]["base"]} {addition}'
        s["expected"]["irrelevant_update"] = s["expected"]["base"]
        notes = s["notes"].split(" Irrelevant update:", 1)[0]
        s["notes"] = f"{notes} Irrelevant update: {addition} This should not affect the decision."
    with open(path, "w") as f:
        for s in rows:
            f.write(json.dumps(s) + "\n")
    print(f"added irrelevant_update to {len(rows)} scenarios in {path}")


if __name__ == "__main__":
    for scenario_path in sys.argv[1:]:
        transform(scenario_path)
