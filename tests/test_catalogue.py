import pytest

from flip.catalogue import fill_from_catalogue, find_model, load_catalogue, words

CATALOGUE = load_catalogue()


def model_id(title):
    found = find_model(title, CATALOGUE)
    return found["id"] if found else None


def fill(title, notes=""):
    return fill_from_catalogue(title, notes, CATALOGUE)


def test_words_split_letters_from_numbers():
    assert words("iPhone13 128GB") == ["iphone", "13", "128", "gb"]
    assert words("S23+") == ["s", "23", "plus"]
    assert words("phone + case") == ["phone", "case"]
    assert words("Pokémon") == ["pokemon"]


@pytest.mark.parametrize("title, expected", [
    ("iPhone 13 128GB Midnight Unlocked", "iphone-13"),
    ("IPHONE13 128gb", "iphone-13"),
    ("apple iphone-13 pro 256gb", "iphone-13-pro"),
    ("iPhone 13 Pro Max 256GB", None),            # not in the catalogue: needs you
    ("iPhone 13 promax 256gb", None),
    ("iPhone 13pm", None),
    ("iPhone 13 mini", None),
    ("PS5 Slim Disc 1TB", "ps5-slim"),            # longest name wins
    ("PS5 disc edition + 2 controllers", "ps5"),
    ("Sony PlayStation 5 Pro", None),
    ("Samsung Galaxy S23+ 256GB", None),          # the + means Plus
    ("Samsung Galaxy S23U", None),
    ("Samsung S23 8GB RAM 256GB", "galaxy-s23"),
    ("Sony WH1000XM4 headphones", "sony-wh-1000xm4"),
    ("sony xm5 black", "sony-wh-1000xm5"),
    ("AirPods Pro 2nd generation USB-C", "airpods-pro-2"),
    ("AirPods Pro 1st gen", None),
    ("Nintendo Switch OLED white", "switch-oled"),
    ("Nintendo Switch Lite", None),
    ("iPhone 13 and iPhone 14 bundle", None),     # two models: can't tell
    ("random phone", None),
])
def test_find_model(title, expected):
    assert model_id(title) == expected


# each of these used to give a confident wrong answer (found by the day-1 check)
@pytest.mark.parametrize("title", [
    "Sony WF-1000XM4 wireless earbuds black",     # earbuds, not the WH headphones
    "Sony WF1000XM5 earbuds",
    "Sony PlayStation 5 Console 1TB with disc drive",  # a Slim without the word "slim"
    "PS5 Digital Edition 1TB",
    "PS5 CFI-2016 disc",
    "PS5 DualSense controller",                   # accessories
    "Case for iPhone 13",
    "iPhone 13 case",
    "iPhone 13 box only",
    "Screen protector iPhone 15",
    "Replacement ear pads for XM5",
    "AirPods Pro 2 left earbud",
    "Switch OLED dock only",
    "PS5 games bundle",
    "iPhone 13 with AirPods Pro 2",               # two products in different places
    "WANTED iPhone 14",                           # not selling
    "swap my PS5 for a switch",
])
def test_not_the_item_or_unsure(title):
    assert model_id(title) is None


def test_fills_everything_a_clear_title_says():
    item = fill("iPhone 13 128GB Midnight Unlocked")
    assert item["storage"] == "128GB"
    assert item["colour"] == "Midnight"
    assert item["network"] == "Unlocked"
    assert item["specs"]["Processor"] == "A15 Bionic"
    assert item["missing"] == []
    assert item["warnings"] == []


def test_leaves_gaps_instead_of_guessing():
    item = fill("iPhone 13 boxed")
    assert item["storage"] is None
    assert item["missing"] == ["storage", "colour", "network"]


def test_bare_number_is_not_storage():
    assert fill("iPhone 13 128 £300")["storage"] is None


def test_storage_must_exist_for_that_model():
    assert fill("iPhone 13 1TB")["storage"] is None


def test_ram_is_not_storage():
    assert fill("Samsung S23 8GB RAM 256GB")["storage"] == "256GB"


def test_one_possible_value_is_filled_without_reading():
    item = fill("AirPods Pro 2 USB-C")
    assert item["colour"] == "White"
    assert item["options"] == {"Connector": "USB-C"}
    assert item["missing"] == []
    assert fill("PS5 disc")["storage"] == "825GB"


def test_one_possible_value_is_not_filled_when_the_text_disagrees():
    assert fill("Switch OLED 64GB + 128GB SD card")["storage"] is None
    assert fill("AirPods Pro 2 black")["colour"] is None
    assert fill("AirPods Pro 2 with black case")["colour"] == "White"  # the case is black


def test_ps5_slim_comes_in_two_sizes():
    item = fill("PS5 Slim digital 1TB white")
    assert (item["storage"], item["colour"], item["options"]) == ("1TB", "White", {"Edition": "Digital Edition"})
    assert fill("PS5 Slim digital")["storage"] is None


def test_two_options_named_means_unsure():
    item = fill("PS5 disc console, digital edition box")
    assert item["options"] == {"Edition": None}
    assert "Edition" in item["missing"]


def test_disc_games_are_not_the_disc_edition():
    assert fill("PS5 digital with 3 disc games")["options"] == {"Edition": "Digital Edition"}


def test_two_colours_named_means_unsure():
    # "Midnight" and "Blue" are both iPhone 13 colours: the photo decides
    assert fill("iPhone 13 midnight blue")["colour"] is None


def test_colour_of_something_else_doesnt_count():
    assert fill("iPhone 13 128GB with blue case")["colour"] is None
    assert fill("iPhone 13 pink line on screen")["colour"] is None


def test_short_colour_names():
    assert fill("iPhone 13 Red 128GB")["colour"] == "(PRODUCT)RED"
    assert fill("iPhone 15 Pro Natural 256GB")["colour"] == "Natural Titanium"


def test_your_notes_fill_the_gaps():
    item = fill("iPhone 13", "256gb, unlocked, blue")
    assert (item["storage"], item["colour"], item["network"]) == ("256GB", "Blue", "Unlocked")


def test_model_from_notes_when_title_is_vague():
    assert fill("phone for sale", "it's an iphone 14 128gb")["model_id"] == "iphone-14"


def test_your_notes_can_overrule_the_title():
    assert fill("iPhone 13 128GB", "actually it's the pro")["model_id"] is None
    item = fill("iPhone 13 128GB", "this is an iphone 14")
    assert item["model_id"] is None
    assert item["warnings"] == ["the title and your notes name different models"]


@pytest.mark.parametrize("title, network", [
    ("iPhone 14 unlocked", "Unlocked"),
    ("iPhone 14 sim free", "Unlocked"),
    ("iPhone 14 locked to EE", None),
    ("iPhone 14 not unlocked", None),
    ("iPhone 14 can be unlocked", None),
    ("iPhone 14 128GB sim, free postage", None),
    ("iCloud locked iPhone 14 unlocked", None),
])
def test_network(title, network):
    assert fill(title)["network"] == network


def test_faults_get_a_warning():
    assert fill("iPhone 13 for parts, icloud locked")["warnings"] == \
        ["mentions icloud, for parts: check the condition before listing"]


def test_unknown_model_needs_you():
    item = fill("random phone")
    assert (item["model_id"], item["missing"]) == (None, ["model"])


def test_missing_notes_dont_crash():
    assert fill("random phone", None)["model_id"] is None
    assert fill(None, "iphone 13")["model_id"] == "iphone-13"
