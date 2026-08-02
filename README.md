# FlipAssist-ai

Drafts eBay listings and offer messages for a reseller. Plain code does everything it can. A small local AI model does only what code can't. A paid API model steps in only when the local answer fails a check, and a person approves every draft.

> **Work in progress.** The plain-code half and its safety checks are built and tested. No AI model is connected yet.

## What it does now

- **Finds the product** in a messy listing title ("iphone13 128gb unlocked boxed") using a catalogue of 12 models (phones, consoles, headphones). It then fills every fact the catalogue knows:
  - model and storage;
  - colour, when the text names exactly one;
  - options such as Disc or Digital;
  - network lock;
  - specs.
- **Leaves gaps instead of guessing.**
  - Anything code isn't sure about goes on a "missing" list.
  - Parts, accessories, wanted ads and listings that name two products aren't matched at all.
- **Builds the eBay title** from a template, within eBay's 80-character limit.
- **Does the money in pence:** profit after fees, and an offer price rounded to a tidy number.
- **Checks an AI answer before it's used:**
  - the agreed shape and allowed values;
  - no numbers the inputs don't contain;
  - no yes/no claims about the box, charger, cable, case, controller, game, screen protector, receipt, warranty or network lock that the inputs don't back up;
  - condition claims (new, sealed, flawless, battery, marks) and the condition "New" only when the reseller's own notes back them;
  - no contact details;
  - length limits.
- **Scores the code** against a private test set of real items, with a scoring script.

## Planned

- **Local model:** Gemma 3 4B via Ollama reads the photo and the notes. It gives only the colour (picked from the catalogue's list for that model), the condition, a condition note and a description.
- **Fallback:** Claude Haiku tries again when a local answer fails a check. If that fails too, the item is marked "needs you".
- **Message drafter:** code sets the offer price. The wording follows the reseller's own style, using a few similar past messages found with MiniLM embeddings in Chroma.
- **Around both:**
  - a cost meter (tokens, £, seconds per draft);
  - an audit log;
  - a web app (FastAPI + React) where a person approves each draft.
- **Measured results on the test set:**
  - fields right for local, API and the switch;
  - cost per 100 listings;
  - minutes per listing by hand vs with the assistant.

## Who does what

| Field | Filled by |
|---|---|
| Model, storage, specs, title | Code, from `data/catalogue.json` |
| Colour | Code if the text names it; otherwise the AI from the photo (planned) |
| Condition, condition note, description | The AI (planned), then checked by code |
| Offer price, profit | Code |

## Run it

Needs Python 3.11 or newer.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pytest
```

## The test set

Real items stay in `testset/private/`, which git never uploads: it holds other sellers' listing text and photos.

```bash
mkdir -p testset/private/photos
cp testset/items.example.json testset/private/items.json
```

1. For each item, fill in:
   - the original title and description;
   - your notes;
   - the photo paths;
   - the prices;
   - the correct answer for every field.
2. Run `.venv/bin/python -m flip.score` to see how often code alone gets each field right.

Include a few items the catalogue doesn't have: the right answer for those is "needs you".

## Folders

- `flip/`: the code
- `data/`: the catalogue and eBay's item conditions (facts, not code)
- `tests/`: a test for every rule
- `testset/`: the example format for the test set
