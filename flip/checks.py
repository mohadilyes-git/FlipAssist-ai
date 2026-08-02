"""The safety checks. Every AI answer goes through these before you see it.

A failed check means: throw the answer away and let the paid model try; if
that fails too, the item is marked "needs you". Each check is plain code, so it
gives the same result every time and costs nothing to run. The checks can
catch an answer that's broken or made up; they can't tell whether a believable
answer is true. That's why you approve every draft.
"""

import re
from decimal import Decimal

from flip.catalogue import words
from flip.money import pounds, to_pence

MAX_CONDITION_NOTE = 1000  # eBay's limit for the condition description
MAX_DESCRIPTION = 1500     # our own limit: short listings read better and cost fewer tokens
MAX_MESSAGE = 500
NEW_CONDITIONS = {"1000", "1500"}  # New, Opened - never used: eBay ignores a condition note on these

# things a draft must not mention unless your inputs (title, description,
# notes, catalogue) do too. Each line is one thing; any of its words counts
PROMISES = {
    "box": ["box", "boxed", "packaging"],
    "charger": ["charger", "adapter", "adaptor"],
    "cable": ["cable", "lead", "cord"],
    "case": ["case"],
    "controller": ["controller", "dualsense"],
    "game": ["game"],
    "screen protector": ["protector"],
    "receipt": ["receipt", "invoice"],
    "warranty": ["warranty", "guarantee", "guaranteed", "applecare"],
    "unlocked": ["unlocked", "simfree"],
}
# claims about the item's condition: only your own notes can back these,
# never the seller's old description
CONDITION_PROMISES = {
    "new": ["new", "bnib", "unused", "unopened"],
    "sealed": ["sealed"],
    "battery": ["battery"],
    "flawless": ["mint", "flawless", "perfect", "perfectly", "pristine", "immaculate", "spotless", "excellent"],
    "marks": ["scratch", "scuff", "mark", "dent", "crack", "cracked", "chip", "chipped"],
}
KEYWORDS = {word: promise for promise, keywords in {**PROMISES, **CONDITION_PROMISES}.items() for word in keywords}
# phrases rewritten before reading claims: same meaning, one way of writing it
SAME_AS = {"sim free": "simfree", "apple care": "applecare", "proof of purchase": "receipt",
           "like new": "mint", "joy con": "controller", "scratch free": "no scratch",
           "mark free": "no mark"}
# phrases that contain a claim word but aren't a claim
HARMLESS = ["perfect for", "perfect gift", "new owner", "new home", "since new", "from new"]
# a claim word with one of these shortly before it, in the same part of the
# sentence, is a "no": "no box", "doesn't come with a charger"
NEGATIONS = {"no", "not", "without", "missing", "never", "none", "nor", "isn", "doesn", "don", "hasn", "wasn"}

NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
# number words count as numbers. Not "one": "this one", "one of the best"
NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
                "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
                "hundred": 100}

AMOUNT = r"(\d[\d,]*(?:\.\d{2})?)"
PRICES = [re.compile(r"£\s?" + AMOUNT),
          re.compile(AMOUNT + r"\s?(?:quid|pounds|gbp)\b", re.IGNORECASE),
          re.compile(r"\b(?:take|do|offer|pay|go to|up to)\s+" + AMOUNT + r"\b(?!\s?(?:gb|tb|%))", re.IGNORECASE)]
# the asking price may be mentioned, but only like this: "I know it's listed at £200"
ASKING_MENTION = re.compile(r"\b(?:asking|listed at|listed for|instead of)\s+£?\s?" + AMOUNT, re.IGNORECASE)

LINK = re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|co\.uk|uk|net|org|io)\b", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.\w+")
HANDLE = re.compile(r"(?<![\w.])@\w{3,}")
CONTACT_WORDS = re.compile(r"\b(?:whats ?app|instagram|insta|snapchat|telegram|gmail|hotmail|outlook|yahoo)\b"
                           r"|\bdot (?:com|co|uk|net)\b", re.IGNORECASE)
# checked with the spaces, dashes and brackets between digits removed
PHONE = re.compile(r"(?:\+|00)44\d{9,11}|\b0[1-37]\d{8,9}\b")  # UK mobiles and landlines
LONG_NUMBER = re.compile(r"\b\d{10,}\b")  # 10+ digits in a row: a phone number or an IMEI

ANSWER_FIELDS = {"colour", "condition_id", "condition_note", "description"}


# ── reading text ────────────────────────────────────────────────────────────

def numbers_in(text):
    """Every number in the text, written one way: "£1,200.00" and "1200" are
    both "1200", and "two" is "2"."""
    found = {f"{Decimal(n.replace(',', '')).normalize():f}" for n in NUMBER.findall(text)}
    found |= {str(NUMBER_WORDS[word]) for word in words(text) if word in NUMBER_WORDS}
    return found


def singular(word):
    """"chargers" -> "charger", "boxes" -> "box", "batteries" -> "battery", for claim words only."""
    for ending, replacement in (("ies", "y"), ("es", ""), ("s", "")):
        if word.endswith(ending) and word[:-len(ending)] + replacement in KEYWORDS:
            return word[:-len(ending)] + replacement
    return word


def promises_in(text):
    """Each claim the text makes, and whether it says yes or no to it.

    "Boxed, no charger" -> {"box": {"yes"}, "charger": {"no"}}
    """
    found = {}
    # read one part of a sentence at a time, so "no scratches, comes with box"
    # or "no scratches and comes with box" doesn't turn into "no box"
    for part in re.split(r"[,.;:!?\n()]|\bbut\b|\band\b(?= (?:comes|has|includes|with))", text.lower()):
        part = " " + " ".join(words(part)) + " "
        for phrase, same in SAME_AS.items():
            part = part.replace(f" {phrase} ", f" {same} ")
        for phrase in HARMLESS:
            part = part.replace(f" {phrase} ", " ")
        part_words = part.split()
        for i, word in enumerate(part_words):
            promise = KEYWORDS.get(singular(word))
            if promise:
                # up to 5 words back: "doesn't come with a charger" splits into
                # doesn / t / come / with / a, so "doesn" is 5 words before
                said = "no" if NEGATIONS & set(part_words[max(0, i - 5):i]) else "yes"
                found.setdefault(promise, set()).add(said)
    return found


def contact_details_in(text):
    joined = re.sub(r"(?<=\d)[\s().\-]+(?=\d)", "", text)  # "07700 900-123" -> "07700900123"
    return any(pattern.search(text) for pattern in (LINK, EMAIL, HANDLE, CONTACT_WORDS)) or \
        any(pattern.search(joined) for pattern in (PHONE, LONG_NUMBER))


def canonical(value, allowed):
    """The allowed spelling of a value, ignoring case and punctuation
    ("midnight" -> "Midnight", 3000 -> "3000"), or None if it isn't allowed."""
    for option in allowed:
        if words(str(value)) == words(option):
            return option
    return None


def sources_text(title, description, notes, item):
    """Everything the AI may state: your inputs plus the catalogue's facts."""
    facts = [item.get("brand"), item.get("model"), item.get("storage"), item.get("colour"),
             item.get("network"), *item.get("options", {}).values(), *item.get("specs", {}).values()]
    return " ".join([title or "", description or "", notes or "", *[fact for fact in facts if fact]])


# ── single checks: each returns a list of problems, empty = passed ──────────

def check_allowed(what, value, allowed):
    if canonical(value, allowed) is None:
        return [f"{what} {value!r} isn't one of the allowed values"]
    return []


def check_length(what, text, limit, required=True):
    if not isinstance(text, str):
        return [f"{what} isn't text"]
    if required and not text.strip():
        return [f"{what} is empty"]
    if len(text) > limit:
        return [f"{what} is {len(text)} characters, over the {limit} limit"]
    return []


def check_no_invented_numbers(what, text, sources):
    extra = numbers_in(text) - numbers_in(sources)
    if extra:
        return [f"{what} has numbers that aren't in your inputs: {', '.join(sorted(extra))}"]
    return []


def check_no_invented_promises(what, text, sources, notes):
    """Every claim in the text must be backed, with the same yes or no: by your
    inputs for things like a box or charger, by your notes for condition."""
    from_inputs, from_notes = promises_in(sources), promises_in(notes)
    unbacked, unbacked_condition = [], []
    for promise, saids in sorted(promises_in(text).items()):
        condition = promise in CONDITION_PROMISES
        backing = (from_notes if condition else from_inputs).get(promise, set())
        for said in sorted(saids, reverse=True):
            if said not in backing:
                (unbacked_condition if condition else unbacked).append(promise if said == "yes" else f"no {promise}")
    problems = []
    if unbacked:
        problems.append(f"{what} says things your inputs don't: {', '.join(unbacked)}")
    if unbacked_condition:
        problems.append(f"{what} says things about the condition your notes don't: {', '.join(unbacked_condition)}")
    return problems


def check_no_contact_details(what, text):
    if contact_details_in(text):
        return [f"{what} contains a link, email, phone number, handle or long ID number"]
    return []


# ── all checks for one AI answer ────────────────────────────────────────────

def check_listing_answer(answer, item, colours, conditions, sources, notes):
    """Every check on the AI's part of a listing. An empty list means it passed.

    answer: what the AI sent back
    item: what code already filled (fill_from_catalogue)
    colours: the model's real colours; conditions: eBay's list for the category
    sources: sources_text(...) for this item; notes: your notes on their own
    """
    if not isinstance(answer, dict) or set(answer) != ANSWER_FIELDS:
        return ["the answer isn't in the agreed shape"]

    problems = check_allowed("colour", answer["colour"], colours)
    colour = canonical(answer["colour"], colours)
    if item.get("colour") and colour and colour != item["colour"]:
        problems.append(f"colour {colour!r} disagrees with the listing text ({item['colour']!r})")
    problems += check_allowed("condition", answer["condition_id"], [c["id"] for c in conditions])

    condition = canonical(answer["condition_id"], [c["id"] for c in conditions])
    if condition in NEW_CONDITIONS:
        said_new = promises_in(notes or "").get("new", set()) | promises_in(notes or "").get("sealed", set())
        if "yes" not in said_new:
            problems.append("condition is New or Opened, but your notes don't say it's new or unused")
        if isinstance(answer["condition_note"], str) and answer["condition_note"].strip():
            problems.append("condition_note must be empty on a new item: eBay ignores it")

    # once checked, the chosen colour is a fact the description may repeat
    sources = f"{sources} {colour or ''}"
    for what, limit, required in (("condition_note", MAX_CONDITION_NOTE, False),
                                  ("description", MAX_DESCRIPTION, True)):
        text = answer[what]
        length_problems = check_length(what, text, limit, required)
        problems += length_problems
        if not length_problems:
            problems += check_no_invented_numbers(what, text, sources)
            problems += check_no_invented_promises(what, text, sources, notes or "")
            problems += check_no_contact_details(what, text)
    return problems


def check_message(message, offer, sources, asking=None):
    """Every check on a drafted message to a seller. offer and asking are in pence.

    The only price it may state is the offer (the asking price only as "listed
    at £200"). No claim check: a message asks things ("does it come with the box?").
    """
    problems = check_length("message", message, MAX_MESSAGE)
    if problems:
        return problems
    mentions = {to_pence(amount) for amount in ASKING_MENTION.findall(message)}
    prices = {to_pence(amount) for pattern in PRICES for amount in pattern.findall(message)}
    if asking is not None and asking in mentions:
        prices.discard(asking)
    if prices != {offer}:
        problems.append(f"the message must offer exactly {pounds(offer)} and no other price")
    problems += check_no_invented_numbers("message", message, f"{sources} {pounds(offer)}")
    problems += check_no_contact_details("message", message)
    return problems
