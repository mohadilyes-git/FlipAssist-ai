"""The iPhones the catalogue covers (the ones AlertFlip covers: SE to 17): each
name finds its own model and never a sibling (Pro vs Pro Max, mini, Plus, the
three SEs, X/XS/XR), and an iPhone it doesn't cover goes to you."""

import pytest

from flip.catalogue import fill_from_catalogue, find_model, load_catalogue

CATALOGUE = load_catalogue()
EVERY_NAME = [(alias, model["id"]) for model in CATALOGUE for alias in model["aliases"]]


def model_id(title):
    found = find_model(title, CATALOGUE)
    return found["id"] if found else None


@pytest.mark.parametrize("alias, expected", EVERY_NAME)
def test_every_name_finds_its_own_model(alias, expected):
    assert model_id(alias) == expected
    assert model_id(f"Apple {alias} used, collection only") == expected


def test_the_iphones_alertflip_covers():
    iphones = [m for m in CATALOGUE if m["id"].startswith("iphone")]
    assert len(iphones) == 37
    assert {"iphone-se-1", "iphone-se-2", "iphone-se-3", "iphone-8", "iphone-x", "iphone-xs-max",
            "iphone-16e", "iphone-air", "iphone-17-pro-max"} <= {m["id"] for m in iphones}


@pytest.mark.parametrize("title", [
    "iPhone 7 32GB Jet Black", "iPhone 6s Plus 128GB", "iPhone 5s 16GB", "iPhone 3GS",
    "iPhone 17e 256GB", "iPhone 18 Pro 256GB Burgundy", "iPhone Duo 1TB",
])
def test_an_iphone_it_doesnt_cover_goes_to_you(title):
    # never read as a covered model: "iPhone 17e" isn't an iPhone 17
    assert model_id(title) is None


@pytest.mark.parametrize("title, expected", [
    ("Apple iPhone 13 Pro Max 256GB Sierra Blue Unlocked", "iphone-13-pro-max"),
    ("iPhone 13 Pro 128GB Graphite", "iphone-13-pro"),
    ("iPhone12 Pro Max 128gb", "iphone-12-pro-max"),
    ("iPhone 12 mini 64GB black", "iphone-12-mini"),
    ("IPHONE 11 PRO MAX 64GB", "iphone-11-pro-max"),
    ("iPhone XS Max 256GB gold", "iphone-xs-max"),
    ("iPhone XS 64GB", "iphone-xs"),
    ("iPhone XR 128GB (PRODUCT)RED", "iphone-xr"),
    ("iPhone X 64GB Space Grey", "iphone-x"),
    ("iPhone 10 256GB", "iphone-x"),
    ("iPhone 8 Plus 64GB", "iphone-8-plus"),
    ("iPhone 8 64GB", "iphone-8"),
    ("iPhone SE 2016 32GB", "iphone-se-1"),
    ("iPhone SE 2020 64GB", "iphone-se-2"),
    ("iPhone SE 2nd Gen 128GB", "iphone-se-2"),
    ("iPhone SE (3rd generation) 64GB", "iphone-se-3"),
    ("iPhone SE 2022 5G", "iphone-se-3"),
    ("iPhone SE 64GB", None),                    # three SEs: needs you
    ("iPhone 14 Plus 128GB", "iphone-14-plus"),
    ("iPhone 14+ 128GB", "iphone-14-plus"),
    ("iPhone 15 Pro Max 1TB Natural Titanium", "iphone-15-pro-max"),
    ("iPhone 16e 128GB", "iphone-16e"),
    ("iPhone 16 Pro 256GB Desert Titanium", "iphone-16-pro"),
    ("iPhone 17 Pro Max 2TB Cosmic Orange", "iphone-17-pro-max"),
    ("iPhone Air 512GB Sky Blue", "iphone-air"),
    ("iPhone 17 256GB Sage", "iphone-17"),
    ("iPhone 13 and iPhone 14 bundle", None),    # two models: needs you
])
def test_real_titles(title, expected):
    assert model_id(title) == expected


@pytest.mark.parametrize("title, colour", [
    ("iPhone SE 2016 64GB Rose Gold", "Rose Gold"),   # "gold" inside "rose gold" doesn't count twice
    ("iPhone SE 2016 64GB Gold", "Gold"),
    ("iPhone 15 Pro 256GB Black Titanium", "Black Titanium"),
    ("iPhone 13 Pro 128GB Sierra Blue", "Sierra Blue"),
    ("iPhone 17 Pro 256GB Cosmic Orange", "Cosmic Orange"),
])
def test_colours_that_contain_other_colours(title, colour):
    assert fill_from_catalogue(title, "", CATALOGUE)["colour"] == colour


def test_a_time_isnt_a_pro_max():
    assert fill_from_catalogue("iPhone 13 128GB Midnight", "collect after 5pm", CATALOGUE)["model_id"] == "iphone-13"
