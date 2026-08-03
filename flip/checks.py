"""The safety checks. Every AI answer goes through these before you see it.

A failed check means: throw the answer away and let the paid model try; if
that fails too, the item is marked "needs you". Each check is plain code, so it
gives the same result every time and costs nothing to run. The checks can
catch an answer that's broken or made up; they can't tell whether a believable
answer is true. That's why you approve every draft.
"""

import re
from decimal import Decimal

from flip.catalogue import (COMMON_COLOURS, colours_named, contains, find_phrase, item_colour_mentioned,
                            options_named, sizes_in, words)
from flip.money import pounds, to_pence

MAX_CONDITION_NOTE = 1000  # eBay's limit for the condition description
MAX_DESCRIPTION = 1500     # our own limit: short listings read better and cost fewer tokens
MAX_MESSAGE = 500
NEW_CONDITIONS = {"1000", "1500"}  # New, Opened - never used: eBay ignores a condition note on these
UNSURE = "unsure"  # the AI may answer this for colour when the photo doesn't show it: then it's for you

# things a draft must not mention unless your inputs (title, description,
# notes, catalogue) do too. Each line is one thing; any of its words counts.
# If your notes mention it, only your notes count: your "no box" beats the
# seller's "boxed"
PROMISES = {
    "box": ["box", "boxed", "packaging"],
    "charger": ["charger", "adapter", "adaptor"],
    "cable": ["cable", "lead", "cord"],
    "case": ["case"],
    "controller": ["controller", "dualsense"],
    "dock": ["dock"],
    "game": ["game"],
    "screen protector": ["protector"],
    "accessories": ["accessory", "extras"],
    "ear tips": ["tips", "eartips"],
    "manual": ["manual", "instructions", "paperwork"],
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
    "working": ["working", "works", "functional", "functioning"],
    "flawless": ["mint", "flawless", "perfect", "perfectly", "pristine", "immaculate", "spotless", "excellent"],
    "marks": ["scratch", "scuff", "mark", "dent", "crack", "cracked", "chip", "chipped"],
}
KEYWORDS = {word: promise for promise, keywords in {**PROMISES, **CONDITION_PROMISES}.items() for word in keywords}
# phrases rewritten before reading claims: same meaning, one way of writing it.
# Applied in this order, so longer phrases go first
SAME_AS = [
    ("perfect working order", "working"), ("full working order", "working"), ("good working order", "working"),
    ("works perfectly", "works"), ("working perfectly", "working"), ("perfectly working", "working"),
    ("fully working", "working"), ("fully functional", "working"),
    ("no faults", "working"), ("no fault", "working"), ("no issues", "working"), ("no problems", "working"),
    ("doesn t work", "not working"), ("does not work", "not working"), ("won t turn on", "not working"),
    ("faulty", "not working"),
    ("never used", "unused"), ("never opened", "unopened"),
    ("sim free", "simfree"), ("apple care", "applecare"), ("proof of purchase", "receipt"),
    ("like new", "mint"), ("as new", "mint"),
    ("joy cons", "controllers"), ("joy con", "controller"), ("joycons", "controllers"), ("joycon", "controller"),
    ("scratch free", "no scratch"), ("mark free", "no mark"), ("dent free", "no dent"),
    ("scuff free", "no scuff"), ("crack free", "no crack"), ("free from", "no"), ("free of", "no"),
]
# phrases that contain a claim word but aren't a claim
HARMLESS = ["perfect for", "perfect gift", "new owner", "new home", "since new", "from new",
            "works with", "working with", "compatible with", "games console", "games consoles", "game console"]
# a claim word with one of these shortly before it, in the same part of the
# sentence, is a "no": "no box", "doesn't come with a charger", "can't find the box"
NEGATIONS = {"no", "not", "without", "missing", "never", "none", "nor", "isn", "doesn", "don", "hasn", "wasn",
             "lost", "t"}
# ...and so is one of these shortly after it: "charger MISSING", "box LOST"
NEGATED_AFTER = {"missing", "lost", "none", "excluded"}
# ...or "not" and one of these: "charger NOT INCLUDED"
INCLUDED = {"included", "supplied", "provided", "present"}
# "new" right before one of these is about a part, not the item: "new battery fitted"
PARTS = {"battery", "screen", "display", "glass", "back", "housing", "camera", "lens", "port", "speaker",
         "speakers", "case", "charger", "cable", "strap", "pads", "cushions", "tips", "box", "protector",
         "controller", "controllers", "dock", "stand", "fan", "ssd", "drive", "seal", "seals", "sim",
         "firmware", "software", "update", "buttons", "button", "sound", "headband"}
# a condition word next to one of these is about that part only: "screen perfect"
CONDITION_PARTS = {"screen", "display", "glass", "back", "housing", "camera", "lens", "speaker", "speakers",
                   "sound", "buttons", "battery", "case", "box", "controller", "controllers", "pads",
                   "cushions", "headband"}
# a condition word right before one of these describes the model, not this
# one: "excellent noise cancelling"
FEATURES = {"noise", "cancelling", "canceling", "anc", "bass", "graphics", "performance", "value"}
# your notes must say one of these for the item to be New or Opened - never used
NEW_ITEM = re.compile(r"\b(?:brand new|bnib|bnwt|new in box|new sealed|still sealed|factory sealed|sealed|"
                      r"unopened|never opened|unused|never used)\b")
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?(?:%|per ?cent\b)", re.IGNORECASE)

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
                           r"|\bdot (?:com|co|uk|net)\b"
                           r"|\b(?:snap|sc|ig|fb|tiktok|discord|kik)\s*(?::|@|me\b)"  # "Snap: name"
                           r"|\bon (?:snap|ig|fb|tiktok|discord|kik)\b", re.IGNORECASE)  # "find me on IG"
# checked with the spaces, dashes and brackets between digits removed
PHONE = re.compile(r"(?:\+|00)44\d{9,11}|\b0[1-37]\d{8,9}\b")  # UK mobiles and landlines
LONG_NUMBER = re.compile(r"\b\d{10,}\b")  # 10+ digits in a row: a phone number or an IMEI

ANSWER_FIELDS = {"colour", "condition_id", "condition_note", "description"}
# "iPhone 13 PLUS a case" is an iPhone 13 and a case, not an iPhone 13 Plus
PLUS_MEANS_AND = {"a", "an", "the", "case", "cases", "charger", "box", "cable", "free", "original", "postage"}


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
    "box: no", "charger not included" and "free from scratches" are all a no.
    A condition word next to a part is about that part only: "screen perfect"
    -> {"flawless screen": {"yes"}}, not a flawless item.
    """
    found = {}
    text = text.lower()
    # "box: no", "charger - none" -> "no box", "no charger"; "box: yes" -> "box"
    text = re.sub(r"\b([a-z]+(?: [a-z]+)?)\s*[:=\-–—]\s*(?:no|none|nope|missing|not included)\s*(?=[,.;\n]|$)",
                  r"no \1", text)
    text = re.sub(r"\b([a-z]+(?: [a-z]+)?)\s*[:=\-–—]\s*(?:yes|yep|included)\s*(?=[,.;\n]|$)", r"\1", text)
    # read one part of a sentence at a time, so "no scratches, comes with box"
    # or "no scratches and comes with box" doesn't turn into "no box"
    for part in re.split(r"[,.;:!?\n()]|\bbut\b|\band\b(?= (?:comes|has|includes|included|with|is|boxed))", text):
        part = " " + " ".join(words(part)) + " "
        for phrase, same in SAME_AS:
            part = part.replace(f" {phrase} ", f" {same} ")
        for phrase in HARMLESS:
            part = part.replace(f" {phrase} ", " ")
        part_words = part.split()
        for i, word in enumerate(part_words):
            promise = KEYWORDS.get(singular(word))
            if not promise:
                continue
            if promise == "new" and set(part_words[i + 1:i + 3]) & PARTS:
                continue  # "new battery fitted": the battery is new, not the item
            if promise == "flawless":
                if set(part_words[i + 1:i + 2]) & FEATURES:
                    continue  # "excellent noise cancelling" describes the model
                parts = sorted(CONDITION_PARTS & set(part_words[max(0, i - 2):i + 2]))
                if parts:
                    promise = f"flawless {parts[0]}"
            after = part_words[i + 1:i + 4]
            # up to 5 words back: "doesn't come with a charger" splits into
            # doesn / t / come / with / a, so "doesn" is 5 words before
            negated = bool(NEGATIONS & set(part_words[max(0, i - 5):i])) or bool(NEGATED_AFTER & set(after)) \
                or any(w in ("not", "t") and nxt in INCLUDED for w, nxt in zip(after, after[1:]))
            found.setdefault(promise, set()).add("no" if negated else "yes")
    return found


def percentages_in(text):
    """Every percentage in the text, written one way: "87%" and "87.0 per cent" are both "87"."""
    return {f"{Decimal(n).normalize():f}" for n in PERCENT.findall(text)}


def says_new(notes):
    """True if your notes say the item itself is new or unused ("brand new",
    "sealed", "unopened", "never used") and nothing says otherwise. "New battery
    fitted" or "got a new phone" isn't enough."""
    claims = promises_in(notes)
    said = claims.get("new", set()) | claims.get("sealed", set())
    return "yes" in said and "no" not in said and bool(NEW_ITEM.search(" ".join(words(notes))))


def contact_details_in(text):
    text = re.sub(r"(?<=\d)[oO]|[oO](?=\d)", "0", text)  # a letter O typed for a zero: "O7700 900123"
    joined = re.sub(r"(?<=\d)[\s().\-]+(?=\d)", "", text)  # "07700 900-123" -> "07700900123"
    return any(pattern.search(text) for pattern in (LINK, EMAIL, HANDLE, CONTACT_WORDS)) or \
        any(pattern.search(joined) for pattern in (PHONE, LONG_NUMBER))


def canonical(value, allowed, aliases=None):
    """The allowed spelling of a value, ignoring case and punctuation, or None
    if it isn't allowed: "midnight" -> "Midnight", 3000 -> "3000", and with the
    model's short colour names "red" -> "(PRODUCT)RED"."""
    aliases = aliases or {}
    for option in allowed:
        if any(words(str(value)) == words(name) for name in [option, *aliases.get(option, [])]):
            return option
    return None


def names_other_model(text_words, model, catalogue):
    """True if the text names a model other than this one: another catalogue
    model ("iPhone 14"), or this one's name next to a word for a different
    version ("iPhone 13 mini", "WF-1000XM4"). A shorter family name is fine:
    "PS5" on a PS5 Slim."""
    own = [words(alias) for alias in model["aliases"]]
    for other in catalogue:
        if other is model:
            continue
        for alias in other["aliases"]:
            alias_words = words(alias)
            if not any(name[:len(alias_words)] == alias_words for name in own) and contains(text_words, alias_words):
                return True
    for name in own:
        for start in find_phrase(text_words, name):
            end = start + len(name)
            before, after = text_words[max(0, start - 1):start], text_words[end:end + 2]
            if after[:1] == ["plus"] and after[1:] and after[1] in PLUS_MEANS_AND:
                after = []
            if set(before + after[:1]) & set(model["not_if"]):
                return True
    return False


def sources_text(title, description, notes, item):
    """Everything the AI may state: your inputs plus the catalogue's facts."""
    facts = [item.get("brand"), item.get("model"), item.get("storage"), item.get("colour"),
             item.get("network"), *item.get("options", {}).values(), *item.get("specs", {}).values()]
    return " ".join([title or "", description or "", notes or "", *[fact for fact in facts if fact]])


# ── single checks: each returns a list of problems, empty = passed ──────────

def check_allowed(what, value, allowed, aliases=None):
    if canonical(value, allowed, aliases) is None:
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


def check_no_invented_percentages(what, text, notes, sources):
    """A percentage, like battery health, is about this item's condition: it
    must come from your notes, not the seller's words. (One that isn't in any
    input at all is already reported by the numbers check.)"""
    extra = (percentages_in(text) - percentages_in(notes)) & numbers_in(sources)
    if extra:
        return [f"{what} has a percentage your notes don't: {', '.join(f'{p}%' for p in sorted(extra))}"]
    return []


def check_no_invented_promises(what, text, sources, notes):
    """Every claim in the text must be backed, with the same yes or no.
    Condition claims only by your notes. Anything else by your notes if they
    mention it ("no box" beats the seller's "boxed"), otherwise by any input.
    And nothing is flawless when your notes mention a mark."""
    from_inputs, from_notes = promises_in(sources), promises_in(notes)
    unbacked, unbacked_condition = [], []
    for promise, saids in sorted(promises_in(text).items()):
        condition = promise.split()[0] in CONDITION_PROMISES
        backing = from_notes.get(promise) or (set() if condition else from_inputs.get(promise, set()))
        if promise.startswith("flawless "):
            backing = backing | from_notes.get("flawless", set())  # a mint item has a mint screen
        for said in sorted(saids, reverse=True):
            marked = promise == "flawless" and said == "yes" and "yes" in from_notes.get("marks", set())
            if said not in backing or marked:
                (unbacked_condition if condition else unbacked).append(promise if said == "yes" else f"no {promise}")
    problems = []
    if unbacked:
        problems.append(f"{what} says things your inputs don't: {', '.join(unbacked)}")
    if unbacked_condition:
        problems.append(f"{what} says things about the condition your notes don't: {', '.join(unbacked_condition)}")
    return problems


def check_matches_item(what, text, item, catalogue, colour):
    """The text mustn't contradict the item: a different model or version, or a
    colour, storage size or edition it doesn't have. colour is the one settled
    for this item; if nobody knows it (None), no colour may be named."""
    model = next(m for m in catalogue if m["id"] == item["model_id"])
    text_words = words(text, breaks=True)
    problems = []
    if names_other_model(text_words, model, catalogue):
        problems.append(f"{what} names a different model from the {model['model']}")
    named = colours_named(text_words, model)
    own = [colour, *model.get("colour_aliases", {}).get(colour, [])] if colour else []
    covered = {word for name in [*own, *named] for word in words(name)}
    wrong = sorted(named - {colour}) + sorted(c for c in COMMON_COLOURS - covered if item_colour_mentioned(text_words, c))
    if wrong:
        problems.append(f"{what} names a colour that isn't the item's: {', '.join(wrong)}")
    sizes = sizes_in(text_words) & set(model["storage"])
    if sizes - {item.get("storage")}:
        problems.append(f"{what} names a storage size that isn't the item's: {', '.join(sorted(sizes - {item.get('storage')}))}")
    for name, values in options_named(text_words, model).items():
        mine = item.get("options", {}).get(name)
        if values - {mine}:
            problems.append(f"{what} says {', '.join(sorted(values - {mine}))}, "
                            f"but the item's {name.lower()} is {mine or 'not known'}")
    return problems


def check_no_prices(what, text):
    """A listing never states a price: not what you paid, not the seller's asking price."""
    if any(pattern.search(text) for pattern in PRICES[:2]):
        return [f"{what} mentions a price"]
    return []


def check_no_contact_details(what, text):
    if contact_details_in(text):
        return [f"{what} contains a link, email, phone number, handle or long ID number"]
    return []


# ── all checks for one AI answer ────────────────────────────────────────────

def check_listing_answer(answer, item, catalogue, conditions, sources, notes):
    """Every check on the AI's part of a listing. An empty list means it passed.

    answer: what the AI sent back. It has a colour only when code couldn't
        fill one, and that colour may be "unsure": then the colour is for you
    item: what code already filled (fill_from_catalogue)
    catalogue: the models (load_catalogue); conditions: eBay's list for the category
    sources: sources_text(...) for this item; notes: your notes on their own
    """
    required = ANSWER_FIELDS - {"colour"} if item.get("colour") else ANSWER_FIELDS
    if not isinstance(answer, dict) or not required <= set(answer) <= ANSWER_FIELDS:
        return ["the answer isn't in the agreed shape"]
    model = next(m for m in catalogue if m["id"] == item["model_id"])
    aliases = model.get("colour_aliases", {})

    problems = []
    colour = item.get("colour")
    if "colour" in answer and str(answer["colour"]).strip().lower() != UNSURE:
        problems += check_allowed("colour", answer["colour"], model["colours"], aliases)
        picked = canonical(answer["colour"], model["colours"], aliases)
        if colour and picked and picked != colour:
            problems.append(f"colour {picked!r} disagrees with the listing text ({colour!r})")
        colour = colour or picked
    problems += check_allowed("condition", answer["condition_id"], [c["id"] for c in conditions])

    condition = canonical(answer["condition_id"], [c["id"] for c in conditions])
    if condition in NEW_CONDITIONS:
        if not says_new(notes or ""):
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
            problems += check_no_invented_percentages(what, text, notes or "", sources)
            problems += check_no_invented_promises(what, text, sources, notes or "")
            problems += check_matches_item(what, text, item, catalogue, colour)
            problems += check_no_prices(what, text)
            problems += check_no_contact_details(what, text)
    return problems


def pence_or_none(amount):
    """to_pence, or None for an amount that can't be a real price."""
    try:
        return to_pence(amount)
    except ValueError:
        return None


def check_message(message, offer, sources, asking=None):
    """Every check on a drafted message to a seller. offer and asking are in pence.

    The only price it may state is the offer. The asking price may come up
    only as "listed at £200", and that's taken out before the prices are read,
    so a second "£200" can't hide behind it. No claim check: a message asks
    things ("does it come with the box?").
    """
    problems = check_length("message", message, MAX_MESSAGE)
    if problems:
        return problems
    rest = message
    if asking is not None and all(pence_or_none(amount) == asking for amount in ASKING_MENTION.findall(message)):
        rest = ASKING_MENTION.sub(" ", message)
    prices = {pence_or_none(amount) for pattern in PRICES for amount in pattern.findall(rest)}
    if prices != {offer}:
        problems.append(f"the message must offer exactly {pounds(offer)} and no other price")
    problems += check_no_invented_numbers("message", message, f"{sources} {pounds(offer)}")
    problems += check_no_contact_details("message", message)
    return problems
