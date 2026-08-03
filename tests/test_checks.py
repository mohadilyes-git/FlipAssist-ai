"""The safety net, tested before any AI exists: hand-written "AI answers",
one good and many bad, each bad one failing for the right reason."""

import pytest

from flip.catalogue import fill_from_catalogue, load_catalogue, load_conditions
from flip.checks import check_listing_answer, check_message, numbers_in, promises_in, sources_text

CATALOGUE = load_catalogue()
CONDITIONS = load_conditions()

TITLE = "iPhone 13 128GB unlocked"
DESCRIPTION = "Selling my iPhone, works perfectly, screen protector on since day one. Perfect for gaming."
NOTES = "boxed, battery 87%, light scratch on the back"
ITEM = fill_from_catalogue(TITLE, NOTES, CATALOGUE)
SOURCES = sources_text(TITLE, DESCRIPTION, NOTES, ITEM)

GOOD = {
    "colour": "Midnight",
    "condition_id": "3000",
    "condition_note": "Light scratch on the back. Battery health 87%.",
    "description": "Apple iPhone 13 128GB in Midnight, unlocked, boxed. 5G. Screen has had a protector on "
                   "since day one. Battery health 87%. Perfect for a new owner.",
}


def problems(notes=NOTES, sources=SOURCES, **changes):
    return check_listing_answer({**GOOD, **changes}, ITEM, CATALOGUE, CONDITIONS["phones"], sources, notes)


def test_a_good_answer_passes():
    assert problems() == []


def test_wrong_shape_fails():
    for answer in ({"colour": "Midnight"}, "Midnight, used", {**GOOD, "price": "£300"}):
        assert check_listing_answer(answer, ITEM, CATALOGUE, CONDITIONS["phones"], SOURCES, NOTES) == \
            ["the answer isn't in the agreed shape"]


def test_small_slips_in_spelling_are_fine():
    assert problems(colour="midnight", condition_id=3000) == []


def test_colour_must_be_real_for_the_model():
    assert problems(colour="Black", description="iPhone 13") == ["colour 'Black' isn't one of the allowed values"]


def test_colour_must_agree_with_the_listing_text():
    item = fill_from_catalogue("iPhone 13 128GB Pink unlocked", NOTES, CATALOGUE)
    result = check_listing_answer({**GOOD, "description": "iPhone 13"}, item, CATALOGUE, CONDITIONS["phones"], SOURCES, NOTES)
    assert result == ["colour 'Midnight' disagrees with the listing text ('Pink')"]


def test_condition_must_be_on_ebays_list():
    assert problems(condition_id="2010") == ["condition '2010' isn't one of the allowed values"]  # refurbished


def test_new_condition_needs_your_notes_to_say_new():
    assert problems(condition_id="1000", condition_note="") == \
        ["condition is New or Opened, but your notes don't say it's new or unused"]


def test_new_item_has_no_condition_note():
    notes = "brand new sealed, unopened, boxed"
    assert problems(notes=notes, condition_id="1000", condition_note="", description="Boxed iPhone 13, sealed.") == []
    assert problems(notes=notes, condition_id="1000", condition_note="Sealed.", description="Boxed iPhone 13.") == \
        ["condition_note must be empty on a new item: eBay ignores it"]


def test_invented_number_fails():
    assert problems(description="iPhone 13, battery health 90%.") == \
        ["description has numbers that aren't in your inputs: 90"]


def test_numbers_written_as_words_count():
    assert problems(description="iPhone 13 with two cases.") == [
        "description has numbers that aren't in your inputs: 2",
        "description says things your inputs don't: case"]


def test_invented_accessory_fails():
    assert problems(description="iPhone 13 with original charger.") == \
        ["description says things your inputs don't: charger"]


def test_other_words_for_the_same_accessory_count():
    assert problems(description="iPhone 13 with charging cord and chargers.") == \
        ["description says things your inputs don't: cable, charger"]


def test_saying_no_charger_is_still_a_claim():
    assert problems(description="iPhone 13, no charger included.") == \
        ["description says things your inputs don't: no charger"]


def test_your_no_beats_the_drafts_yes():
    # your notes say no box, so a draft saying "boxed" is wrong
    notes = "no box, battery 87%, light scratch on the back"
    assert problems(notes=notes, sources=SOURCES.replace("boxed", "no box"), description="Boxed iPhone 13.") == \
        ["description says things your inputs don't: box"]


def test_doesnt_come_with_is_a_no():
    assert promises_in("doesn't come with a charger") == {"charger": {"no"}}
    assert promises_in("no scratches, comes with box") == {"marks": {"no"}, "box": {"yes"}}
    assert promises_in("no scratches and comes with box") == {"marks": {"no"}, "box": {"yes"}}
    assert promises_in("scratch free") == {"marks": {"no"}}


def test_condition_claims_need_your_notes_not_the_sellers_words():
    # the seller's description says "works perfectly": that doesn't make it flawless
    assert problems(condition_note="Mint condition.") == \
        ["condition_note says things about the condition your notes don't: flawless"]
    assert problems(description="Like new iPhone 13.") == \
        ["description says things about the condition your notes don't: flawless"]


def test_no_scratches_when_your_notes_say_scratch_fails():
    assert problems(condition_note="No scratches.") == \
        ["condition_note says things about the condition your notes don't: no marks"]


def test_harmless_phrases_are_not_claims():
    assert problems(description="iPhone 13, perfect for gaming, ready for its new owner.") == []


def test_claims_your_notes_make_pass():
    assert problems(description="Boxed iPhone 13, unlocked, light scratch on the back.") == []


@pytest.mark.parametrize("text", [
    "Message me on 07700 900123",
    "call 07700-900-123",
    "ring +44 (0) 7700 900123",
    "landline 020 7946 0958",
    "see www.example.com",
    "ebay dot com",
    "email me@example.com",
    "whatsapp me",
    "insta @example_seller",
    "IMEI 123456789012345",
])
def test_contact_details_fail(text):
    assert "description contains a link, email, phone number, handle or long ID number" in problems(description=text)


def test_empty_or_too_long_description_fails():
    assert problems(description="  ") == ["description is empty"]
    assert problems(description="a" * 1501) == ["description is 1501 characters, over the 1500 limit"]


def test_empty_condition_note_is_allowed():
    assert problems(condition_note="") == []


def test_numbers_written_differently_are_the_same():
    assert numbers_in("£1,200.00 and 6.10 inch, two cables") == {"1200", "6.1", "2"}


# ── found by the second check: your notes beat the seller's words ──────────

def test_your_notes_beat_the_sellers_words():
    # the seller's text says boxed (it's in SOURCES), your notes say no box
    notes = "no box, battery 87%, light scratch on the back"
    assert problems(notes=notes, description="Boxed iPhone 13.") == \
        ["description says things your inputs don't: box"]


def test_a_percentage_must_come_from_your_notes():
    sources = SOURCES + " battery health 90%"  # the seller said 90%, you measured 87%
    assert problems(sources=sources, description="iPhone 13, battery health 90%.") == \
        ["description has a percentage your notes don't: 90%"]


def test_a_new_part_doesnt_make_the_item_new():
    notes = "new battery fitted, light scratch on the back"
    assert problems(notes=notes, condition_id="1000", condition_note="", description="iPhone 13.") == \
        ["condition is New or Opened, but your notes don't say it's new or unused"]
    assert problems(notes="opened but never used", condition_id="1500", condition_note="",
                    description="iPhone 13.") == []


@pytest.mark.parametrize("text, expected", [
    ("Box: no, charger - none", {"box": {"no"}, "charger": {"no"}}),
    ("charger not included", {"charger": {"no"}}),
    ("charger isn't included", {"charger": {"no"}}),
    ("original box missing", {"box": {"no"}}),
    ("can't find the box", {"box": {"no"}}),
    ("dent-free", {"marks": {"no"}}),
    ("free from scratches", {"marks": {"no"}}),
    ("fully working, no faults", {"working": {"yes"}}),
    ("faulty speaker", {"working": {"no"}}),
    ("comes with dock and Joy-Cons", {"dock": {"yes"}, "controller": {"yes"}}),
    ("all accessories included", {"accessories": {"yes"}}),
    ("games console", {}),
    ("excellent noise cancelling", {}),
    ("screen perfect", {"flawless screen": {"yes"}}),
    ("new battery fitted", {"battery": {"yes"}}),
])
def test_reading_claims(text, expected):
    assert promises_in(text) == expected


def test_working_claims_need_your_notes():
    # a draft saying Face ID works, when your notes never said so
    assert problems(description="iPhone 13, Face ID works.") == \
        ["description says things about the condition your notes don't: working"]
    assert problems(notes=NOTES + ", fully working", description="iPhone 13, Face ID works.") == []


def test_nothing_is_flawless_when_your_notes_mention_a_mark():
    notes = "screen perfect, light scratch on the back, battery 87%"
    assert problems(notes=notes, description="Flawless iPhone 13.") == \
        ["description says things about the condition your notes don't: flawless"]
    assert problems(notes=notes, description="iPhone 13, screen perfect.") == []


# ── found by the second check: drafts that contradict the item ─────────────

@pytest.mark.parametrize("description, problem", [
    ("Apple iPhone 13 Pro 128GB, unlocked, boxed.", "description names a different model from the iPhone 13"),
    ("Apple iPhone 13 mini 128GB, unlocked, boxed.", "description names a different model from the iPhone 13"),
    ("Apple iPhone 13 128GB in Blue, unlocked, boxed.", "description names a colour that isn't the item's: Blue"),
    ("Apple iPhone 13 128GB in black, unlocked, boxed.", "description names a colour that isn't the item's: black"),
    ("Apple iPhone 13 256GB, unlocked, boxed.", "description names a storage size that isn't the item's: 256GB"),
])
def test_a_draft_that_contradicts_the_item_fails(description, problem):
    assert problem in problems(description=description)


def test_the_reviewers_iphone_13_pro_draft_fails():
    result = problems(description="Apple iPhone 13 Pro 128GB in Midnight, unlocked, boxed. Face ID works.")
    assert "description names a different model from the iPhone 13" in result
    assert "description says things about the condition your notes don't: working" in result


def test_plus_a_case_is_not_the_plus_model():
    assert problems(description="Apple iPhone 13 128GB, unlocked, boxed, plus a case.") == \
        ["description says things your inputs don't: case"]


def test_a_draft_naming_the_other_edition_fails():
    title = "PS5 Slim disc edition 1TB white"
    item = fill_from_catalogue(title, "", CATALOGUE)
    answer = {"condition_id": "3000", "condition_note": "",
              "description": "Sony PlayStation 5 Slim Digital Edition 1TB in White."}
    assert check_listing_answer(answer, item, CATALOGUE, CONDITIONS["consoles"],
                                sources_text(title, "", "", item), "") == \
        ["description says Digital Edition, but the item's edition is Disc Edition"]


def test_short_colour_names_and_unsure_are_allowed():
    plain = "Apple iPhone 13 128GB, unlocked, boxed."
    assert problems(colour="Red", description=plain) == []      # (PRODUCT)RED
    assert problems(colour="unsure", description=plain) == []   # the colour is left for you
    assert problems(colour="unsure", description="Apple iPhone 13 128GB in Midnight.") == \
        ["description names a colour that isn't the item's: Midnight"]


def test_no_colour_needed_when_code_already_knows_it():
    item = fill_from_catalogue("iPhone 13 128GB Midnight unlocked", NOTES, CATALOGUE)
    answer = {key: value for key, value in GOOD.items() if key != "colour"}
    assert check_listing_answer(answer, item, CATALOGUE, CONDITIONS["phones"], SOURCES, NOTES) == []


def test_a_listing_never_states_a_price():
    assert "description mentions a price" in problems(description="Apple iPhone 13 128GB, bought for £220.")


# ── messages ────────────────────────────────────────────────────────────────

LISTING = "PS5 disc edition, 2 controllers, £200"


@pytest.mark.parametrize("message", [
    "Hi, is this still available? Would you take £170 for it?",
    "Hi, does it come with the box? I could do £170.",       # asking about things is fine
    "Could you do 170 cash?",
    "Hi, I know it's listed at £200, would you take £170?",
])
def test_good_messages_pass(message):
    assert check_message(message, 17000, LISTING, asking=20000) == []


@pytest.mark.parametrize("message", [
    "Would you take £160?",
    "£170? or £180 max",
    "Would you take 160 quid?",
    "£170 or £200?",                                         # the asking price as a second offer
    "Is this still available?",                               # no offer at all
])
def test_wrong_price_fails(message):
    assert "the message must offer exactly £170.00 and no other price" in check_message(message, 17000, LISTING, asking=20000)


def test_message_with_a_phone_number_fails():
    assert "message contains a link, email, phone number, handle or long ID number" in \
        check_message("£170? text me on 07700900123", 17000, LISTING)
