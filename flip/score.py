"""Score the code-only part against your test set: for each field, how often
plain code fills it correctly, leaves it for you, or gets it wrong.

    .venv/bin/python -m flip.score                      # your real items
    .venv/bin/python -m flip.score testset/items.example.json

"Wrong" is the number that matters most: a gap goes to you, a wrong answer
could reach a buyer.
"""

import json
import sys
from pathlib import Path

from flip.catalogue import fill_from_catalogue, load_catalogue

FIELDS = ["model_id", "storage", "colour", "network", "options"]


def score(items, catalogue):
    totals = {field: {"right": 0, "left for you": 0, "wrong": 0} for field in FIELDS}
    wrong = []
    for item in items:
        filled = fill_from_catalogue(item["original_title"], item["my_notes"], catalogue)
        for field in FIELDS:
            expected = item["answer"].get(field)
            got = filled.get(field)
            # an option code couldn't pick counts as "left for you" for the whole field
            if field == "options" and got is not None and any(value is None for value in got.values()):
                got = None
            if got == expected:
                totals[field]["right"] += 1
            elif got is None:
                totals[field]["left for you"] += 1
            else:
                totals[field]["wrong"] += 1
                wrong.append(f"{item['id']}: {field} = {got!r}, should be {expected!r}")
    return totals, wrong


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "testset/private/items.json")
    items = json.loads(path.read_text(encoding="utf-8"))
    totals, wrong = score(items, load_catalogue())
    print(f"{len(items)} items from {path}\n")
    print(f"{'field':<10} {'right':>6} {'left for you':>13} {'wrong':>6}")
    for field, counts in totals.items():
        print(f"{field:<10} {counts['right']:>6} {counts['left for you']:>13} {counts['wrong']:>6}")
    if wrong:
        print("\nwrong answers (fix the catalogue or the code for these):")
        print("\n".join(f"  {line}" for line in wrong))


if __name__ == "__main__":
    main()
