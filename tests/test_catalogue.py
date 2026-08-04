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
    assert words("it's 23 months, Sony’s box") == ["it", "23", "months", "sony", "box"]  # 's dropped


@pytest.mark.parametrize("title, expected", [
    ("iPhone 13 128GB Midnight Unlocked", "iphone-13"),
    ("IPHONE13 128gb", "iphone-13"),
    ("apple iphone-13 pro 256gb", "iphone-13-pro"),
    ("iPhone 13 Pro Max 256GB", "iphone-13-pro-max"),
    ("iPhone 13 promax 256gb", "iphone-13-pro-max"),
    ("iPhone 13pm", "iphone-13-pro-max"),
    ("iPhone 13 mini", "iphone-13-mini"),
    ("PS5 Slim Disc 1TB", "ps5-slim"),            # longest name wins
    ("PS5 disc edition + 2 controllers", "ps5"),
    ("Sony PlayStation 5 Pro", None),            # not in the catalogue: needs you
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
    assert fill("PS5 disc, original 2020 model")["storage"] == "825GB"


def test_one_possible_value_is_not_filled_when_the_text_disagrees():
    assert fill("Switch OLED 64GB + 128GB SD card")["storage"] is None
    assert fill("AirPods Pro 2 black")["colour"] is None
    assert fill("AirPods Pro 2 with black case")["colour"] == "White"  # the case is black


def test_ps5_slim_comes_in_two_sizes():
    item = fill("PS5 Slim digital 1TB white")
    assert (item["storage"], item["colour"], item["options"]) == ("1TB", "White", {"Edition": "Digital Edition"})
    assert fill("PS5 Slim digital")["storage"] is None


def test_two_options_named_means_unsure():
    item = fill("PS5 2020 model, disc console, digital edition box")
    assert item["options"] == {"Edition": None}
    assert "Edition" in item["missing"]


def test_disc_games_are_not_the_disc_edition():
    assert fill("PS5 digital, 2020 model, with 3 disc games")["options"] == {"Edition": "Digital Edition"}


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
    ("iPhone 14 isn’t unlocked", None),            # the curly apostrophe iPhones type
    ("iPhone 14 never been unlocked", None),
    ("iPhone 14 hasn't been unlocked", None),
    ("iPhone 14 has been unlocked", "Unlocked"),
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


# each of these used to give a confident wrong answer (found by the second check)
def test_its_is_not_a_galaxy_s23():
    assert model_id("phone, it's 23 months old") is None


def test_colour_of_a_case_with_describing_words_doesnt_count():
    assert fill("iPhone 13 128GB pink silicone case")["colour"] is None
    assert fill("iPhone 13 128GB with clear protective blue case")["colour"] is None
    assert fill("iPhone 13 Pink with case")["colour"] == "Pink"          # "with" ends the description
    assert fill("iPhone 15 Pro, original white cable")["colour"] is None  # the cable is white


def test_an_option_that_isnt_there_doesnt_count():
    assert fill("original 2020 PS5 digital, no disc drive")["options"] == {"Edition": "Digital Edition"}
    assert fill("AirPods Pro 2 with USB-C cable")["options"] == {"Connector": None}


def test_ps5_on_its_own_could_be_the_slim():
    # Sony sells the Slim as "PS5 Disc Edition" too, so a bare "PS5" goes to you
    item = fill("PS5 Disc Edition 825GB")
    assert item["model_id"] is None
    assert "original 2020 model" in item["warnings"][0]
    assert fill("PS5 Digital Edition Marvel's Wolverine Battle Yellow 825GB")["model_id"] is None
    assert fill("PS5 disc edition", "original 2020 model")["model_id"] == "ps5"


def test_your_notes_can_name_the_exact_model():
    assert fill("PS5 disc edition", "it's the PS5 Slim")["model_id"] == "ps5-slim"


@pytest.mark.parametrize("title, notes", [
    ("iPhone 13 Pro 128GB unlocked", "checked: it's a regular iPhone 13, seller got the title wrong"),
    ("iPhone 15 Pro 256GB unlocked", "it's actually an iPhone 15, not the pro"),
    ("PS5 Slim Disc Edition", "it's the original PS5 2020 launch model"),
])
def test_notes_naming_another_model_go_to_you(title, notes):
    item = fill(title, notes)
    assert item["model_id"] is None
    assert "the title and your notes name different models" in item["warnings"]


def test_an_edition_that_only_comes_one_way_is_filled():
    item = fill("PS5 Slim Wolverine edition")
    assert (item["colour"], item["storage"], item["options"]) == \
        ("Marvel's Wolverine Battle Yellow", "825GB", {"Edition": "Digital Edition"})
    item = fill("PS5 Slim Battle Yellow disc edition")
    assert item["options"] == {"Edition": None}
    assert item["warnings"] == ["the Marvel's Wolverine Battle Yellow only comes as Digital Edition: check the edition"]


def test_the_sellers_description_can_raise_a_warning():
    item = fill_from_catalogue("iPhone 13 128GB", "", CATALOGUE, description="Face ID doesn't work")
    assert item["warnings"] == ["mentions doesn't work: check the condition before listing"]


def test_nothing_reads_across_a_comma_or_from_title_into_notes():
    assert fill("Switch OLED white", "dock and joy-cons included")["colour"] == "White"
    assert fill("iPhone 13 Midnight, screen perfect")["colour"] == "Midnight"
    assert model_id("iPhone 13 128GB, case included") == "iphone-13"   # the phone, with a case
    assert model_id("iPhone 13 case, black") is None                   # a case


# ── found by the attack agents: reading the item ───────────────────────────

def test_original_controllers_dont_make_it_the_original_ps5():
    assert fill("PS5 Digital Edition with 2 original PS5 controllers")["model_id"] is None


def test_the_wolverine_game_is_not_the_wolverine_edition():
    item = fill("PS5 Slim Digital 825GB with Wolverine")
    assert (item["colour"], item["options"]) == (None, {"Edition": "Digital Edition"})


@pytest.mark.parametrize("title", [
    "PS5 Slim Disc Drive",
    "Apple AirPods Pro 2 Charging Case USB-C",
    "AirPods Pro 2nd Gen Charging Case Lightning (no earbuds)",
    "Nintendo Switch OLED Joy-Cons white",
    "Genuine iPhone 13 screen OLED",
])
def test_parts_are_not_the_item(title):
    assert model_id(title) is None


@pytest.mark.parametrize("title, notes", [
    ("iPhone 13 128GB Blue", "not sure if it's unlocked, need to check"),
    ("iPhone 14 128GB Purple", "unlocked?"),
    ("Samsung Galaxy S23 128GB Cream", "seller says unlocked, will check"),
])
def test_unlocked_with_a_doubt_is_for_you(title, notes):
    assert fill(title, notes)["network"] is None


@pytest.mark.parametrize("title, notes, expected", [
    ("iPhone 13 128GB Midnight unlocked plus charger", "", "iphone-13"),
    ("iPhone 13 128GB Midnight unlocked", "boxed plus original charger", "iphone-13"),
    ("iPhone 13 128GB Midnight unlocked + screen protector", "", "iphone-13"),
    ("iPhone 13 128GB Midnight unlocked", "battery max capacity 86%", "iphone-13"),
    ("Apple AirPods Pro (2nd Generation) USB-C", "", "airpods-pro-2"),
    ("Nintendo Switch (OLED Model) White", "", "switch-oled"),
])
def test_everyday_wording_doesnt_hide_the_model(title, notes, expected):
    assert fill(title, notes)["model_id"] == expected
