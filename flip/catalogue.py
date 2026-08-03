"""Find the model in a messy listing title and fill in every fact the catalogue
knows, so the AI only does what code can't. Anything code isn't sure about is
left empty and listed under "missing": a gap is better than a wrong guess."""

import json
import re
import unicodedata
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# a listing that's about parts or accessories, or isn't selling anything
NOT_THE_ITEM = ["box only", "case only", "dock only", "charger only", "screen only", "left earbud",
                "right earbud", "left airpod", "right airpod", "ear pads", "earpads", "replacement",
                "protector", "faceplate", "faceplates", "skin", "skins", "sticker", "stickers",
                "housing", "wanted", "swap"]
# a word right before a model's name means the listing is for something else: "case FOR iPhone 13"
ACCESSORY_BEFORE = {"for", "fits", "compatible"}
# a word right after it means the same: "iPhone 13 CASE", "PS5 CONTROLLER"
ACCESSORY_AFTER = {"case", "cases", "cover", "covers", "controller", "controllers", "dualsense", "pad", "pads",
                   "headset", "game", "games", "charger", "cable", "stand", "dock", "remote",
                   "camera", "box", "strap", "mount", "holder", "grip", "grips", "stylus"}
# a colour right before one of these is describing something else: "blue CASE", "pink LINE"
NOT_ITEM_COLOUR = {"case", "cases", "cover", "bumper", "skin", "strap", "line", "lines", "spot",
                   "spots", "tint", "mark", "marks", "screen", "display", "light", "cable", "cables",
                   "charger", "lead", "box", "controller", "controllers", "pad", "pads", "dock", "stand",
                   "sleeve", "pouch", "bag"}
# words that can sit between a colour and what it describes: "pink SILICONE case"
DESCRIBING_WORDS = {"silicone", "leather", "clear", "protective", "phone", "rubber", "magsafe", "plastic",
                    "hard", "soft", "glitter", "wallet", "flip", "official", "apple", "genuine", "original",
                    "matching", "carry", "carrying", "travel", "usb", "c"}
# an option word right before one of these is about something else: "disc GAMES", "USB-C CABLE"
NOT_AN_OPTION = {"game", "games", "code", "codes", "film", "films", "movie", "movies", "copy", "copies",
                 "cable", "cables", "lead", "leads", "charger", "chargers", "adapter", "adaptor", "plug", "wire"}
# an option word just after one of these isn't there: "NO disc drive"
NOT_THERE = {"no", "not", "without", "non"}
COMMON_COLOURS = {"black", "white", "grey", "gray", "silver", "gold", "blue", "red", "pink", "green",
                  "purple", "yellow", "orange", "midnight", "starlight", "graphite", "cream", "lavender"}
# worth a warning: the listing may be locked or faulty
FAULT_WORDS = ["icloud", "activation lock", "blacklisted", "barred", "for parts", "spares",
               "faulty", "not working", "doesn't work", "won't turn on", "water damage", "broken"]


def load_catalogue():
    return json.loads((DATA / "catalogue.json").read_text(encoding="utf-8"))["models"]


def load_conditions():
    data = json.loads((DATA / "conditions.json").read_text(encoding="utf-8"))
    del data["about"]
    return data


def words(text):
    """Cut text into lowercase words, splitting letters from numbers.

    "iPhone13 128GB" -> ["iphone", "13", "128", "gb"], so "iphone13",
    "iPhone 13" and "IPHONE-13" all look the same. Accents are dropped
    ("Pokémon" -> "pokemon"). A "+" stuck to a name ("S23+") becomes "plus";
    a "+" on its own ("phone + case") is dropped. "'s" is dropped, so
    "it's 23 months" can't read as an S23.
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"(?<=[a-z0-9])['’ʼ]s\b", "", text)
    text = re.sub(r"(?<=[a-z0-9])\+", " plus ", text)
    return re.findall(r"[a-z]+|\d+", text)


def find_phrase(text_words, phrase_words):
    """Every position where phrase_words appear side by side, in order, in text_words."""
    n = len(phrase_words)
    return [i for i in range(len(text_words) - n + 1) if text_words[i:i + n] == phrase_words]


def contains(text_words, phrase_words):
    return bool(find_phrase(text_words, phrase_words))


def mentioned(text_words, phrase, not_followed_by=(), skipping=(), not_after=()):
    """True if phrase appears at least once in a way that counts:
    - it isn't describing something else: the next word isn't one of
      not_followed_by ("blue CASE"), even with up to 3 skipping words in
      between ("pink silicone CASE");
    - it isn't ruled out by one of the 2 words before it ("NO disc drive")."""
    phrase_words = words(phrase)
    for start in find_phrase(text_words, phrase_words):
        end = start + len(phrase_words)
        skipped = 0
        while end < len(text_words) and text_words[end] in skipping and skipped < 3:
            end, skipped = end + 1, skipped + 1
        if end < len(text_words) and text_words[end] in not_followed_by:
            continue
        if set(text_words[max(0, start - 2):start]) & set(not_after):
            continue
        return True
    return False


def find_model(text, catalogue):
    """The catalogue model the text is about, or None if unsure.

    1. A listing for parts or accessories, or a wanted/swap post, isn't the item.
    2. A name with "for" right before it, or "case" right after it, is an
       accessory listing, so that match doesn't count.
    3. A longer name beats a shorter one only where they overlap ("ps 5 slim"
       beats the "ps 5" inside it).
    4. A model is ruled out if any of its not_if words appear ("pro" rules out
       the iPhone 13), but its name still counts as "something was named here":
       "iPhone 13 Pro Max" is a product we don't have, not nothing.
    5. The answer is a model only if it's the one thing left. Two products
       named in different places, or one we ruled out, means we can't tell.
    """
    text_words = words(text)
    if any(contains(text_words, words(phrase)) for phrase in NOT_THE_ITEM):
        return None
    matches = []  # (start, end, model, ruled_out)
    for model in catalogue:
        ruled_out = any(word in text_words for word in model["not_if"])
        for alias in model["aliases"]:
            alias_words = words(alias)
            for start in find_phrase(text_words, alias_words):
                end = start + len(alias_words)
                before = text_words[start - 1] if start > 0 else ""
                after = text_words[end] if end < len(text_words) else ""
                if before not in ACCESSORY_BEFORE and after not in ACCESSORY_AFTER:
                    matches.append((start, end, model, ruled_out))
    # drop a match that sits inside a longer one
    kept = [m for m in matches
            if not any(o[0] <= m[0] and m[1] <= o[1] and o[1] - o[0] > m[1] - m[0] for o in matches)]
    if any(ruled_out for *_, ruled_out in kept) or len({m[2]["id"] for m in kept}) != 1:
        return None
    return kept[0][2]


def sizes_in(text_words):
    """Every '<number> gb/tb' in the text: "128 gb" -> "128GB". A bare "128"
    could be a price, so it doesn't count."""
    return {number + unit.upper() for number, unit in zip(text_words, text_words[1:])
            if unit in ("gb", "tb") and number.isdigit()}


def find_storage(text_words, model):
    """The storage size, if the model only comes in one or the text names
    exactly one real size for it."""
    allowed = model["storage"]
    stated = sizes_in(text_words)
    if len(allowed) == 1:
        # only one size exists. If the text names a different one too ("+ 128GB
        # SD card"), something's off: leave it for you
        return allowed[0] if stated <= set(allowed) else None
    real = stated & set(allowed)  # ignores RAM ("8GB RAM 256GB")
    return real.pop() if len(real) == 1 else None


def item_colour_mentioned(text_words, name):
    """True if the text uses this colour name for the item itself, not for a
    case, cable or mark ("blue case", "pink silicone case", "pink line")."""
    return mentioned(text_words, name, NOT_ITEM_COLOUR, DESCRIBING_WORDS)


def colours_named(text_words, model):
    """The model's colours the text names, by full or short name."""
    aliases = model.get("colour_aliases", {})
    return {colour for colour in model["colours"]
            if any(item_colour_mentioned(text_words, name) for name in [colour, *aliases.get(colour, [])])}


def find_colour(text_words, model):
    """The colour, if the model only comes in one or the text names exactly one."""
    allowed = model["colours"]
    if len(allowed) == 1:
        # only one colour exists. If the text names another, leave it for you
        own = set(words(allowed[0]))
        others = [c for c in COMMON_COLOURS - own if item_colour_mentioned(text_words, c)]
        return None if others else allowed[0]
    named = colours_named(text_words, model)
    return named.pop() if len(named) == 1 else None


def options_named(text_words, model):
    """For each option (Edition, Connector), every value the text names."""
    return {name: {value for value, keywords in values.items()
                   if any(mentioned(text_words, k, NOT_AN_OPTION, not_after=NOT_THERE) for k in keywords)}
            for name, values in model["options"].items()}


def find_options(text_words, model):
    """Each option (Disc/Digital, Lightning/USB-C) the text clearly names."""
    return {name: next(iter(named)) if len(named) == 1 else None
            for name, named in options_named(text_words, model).items()}


def find_network(text):
    """'Unlocked' only when the text plainly says so. "Not unlocked", "never been
    unlocked", "can be unlocked", a lock or iCloud anywhere: that's for you to
    check. Curly apostrophes (iPhone keyboards type "isn’t") count as straight."""
    text = re.sub(r"[’‘ʼ]", "'", text.lower())
    if re.search(r"\b(?:not|never|isn'?t|hasn'?t|wasn'?t|cannot|can'?t|could|be)\s+(?:been\s+|be\s+)?unlocked\b",
                 text):
        return None
    if re.search(r"\b(locked|icloud|blacklisted|barred)\b", text):
        return None
    if re.search(r"\bunlocked\b|\bsim[ -]?free\b", text):
        return "Unlocked"
    return None


def family_of(general, specific):
    """True if one of general's names starts one of specific's: "PS5" is the
    family name of the "PS5 Slim", "iPhone 13" of the "iPhone 13 Pro"."""
    return any(words(long)[:len(words(short))] == words(short)
               for short in general["aliases"] for long in specific["aliases"])


def edition_value(found, only, edition, what, warnings):
    """An edition that only comes one way: fill that value, or leave it for you
    if the text says something else."""
    if found in (None, only):
        return only
    warnings.append(f"the {edition} only comes as {only}: check the {what}")
    return None


def warnings_for(text_words):
    found = [phrase for phrase in FAULT_WORDS if contains(text_words, words(phrase))]
    return [f"mentions {', '.join(found)}: check the condition before listing"] if found else []


def fill_from_catalogue(title, notes, catalogue, description=""):
    """Everything code can fill for one item, plus what it couldn't ("missing")
    and anything you should look at ("warnings").

    The model comes from the title, or your notes if the title doesn't say. If
    the two name different models, or your notes rule the model out ("it's the
    pro"), it's left for you; a family name and an exact one ("PS5" and "PS5
    Slim") count as the exact one. A name that fits two models needs a word that
    settles it ("PS5" alone could be the Slim). Everything else is read from
    both together. The seller's description is read for warnings only
    ("faulty", "iCloud"): it's too chatty to fill facts from.
    """
    title, notes = title or "", notes or ""
    text = f"{title} {notes}"
    text_words = words(text)
    warnings = warnings_for(words(f"{text} {description or ''}"))

    from_title = find_model(title, catalogue)
    from_notes = find_model(notes, catalogue)
    model = from_title or from_notes
    if from_title and from_notes and from_title is not from_notes:
        if family_of(from_title, from_notes):
            model = from_notes  # "PS5" in the title, "PS5 Slim" in your notes: the Slim
        elif family_of(from_notes, from_title):
            model = from_title
        else:
            model = None
            warnings.append("the title and your notes name different models")
    if model and any(word in text_words for word in model["not_if"]):
        model = None
    if model and model.get("confirm_with") and \
            not any(contains(text_words, words(phrase)) for phrase in model["confirm_with"]):
        warnings.append(model["confirm_why"])  # "PS5" alone could be the Slim
        model = None
    if model is None:
        return {"model_id": None, "missing": ["model"], "warnings": warnings}

    filled = {
        "model_id": model["id"],
        "category": model["category"],
        "brand": model["brand"],
        "model": model["model"],
        "storage": find_storage(text_words, model) if model["storage"] else None,
        "colour": find_colour(text_words, model),
        "options": find_options(text_words, model),
        "network": find_network(text) if model["category"] == "phones" else None,
        "specs": dict(model["specs"]),
    }
    # some editions only come one way: the Wolverine PS5 is Digital Edition, 825GB
    rule = model.get("colour_rules", {}).get(filled["colour"])
    if rule:
        filled["storage"] = edition_value(filled["storage"], rule["storage"], filled["colour"], "storage", warnings)
        for name, value in rule["options"].items():
            filled["options"][name] = edition_value(filled["options"][name], value, filled["colour"],
                                                    name.lower(), warnings)
    missing = []
    if model["storage"] and filled["storage"] is None:
        missing.append("storage")
    if filled["colour"] is None:
        missing.append("colour")  # the AI looks at the photo for this one
    missing += [name for name, value in filled["options"].items() if value is None]
    if model["category"] == "phones" and filled["network"] is None:
        missing.append("network")
    filled["missing"] = missing
    filled["warnings"] = warnings
    return filled
