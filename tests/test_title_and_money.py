from flip.catalogue import fill_from_catalogue, load_catalogue
from flip.money import offer_price, pounds, profit, to_pence
from flip.title import MAX_LENGTH, build_title

CATALOGUE = load_catalogue()


def title_for(text, notes=""):
    return build_title(fill_from_catalogue(text, notes, CATALOGUE))


def test_title_in_a_fixed_order():
    assert title_for("unlocked midnight iphone13 128gb") == "Apple iPhone 13 128GB Midnight Unlocked"


def test_title_includes_options():
    assert title_for("ps5 slim digital 1tb white") == "Sony PlayStation 5 Slim Digital Edition 1TB White"


def test_no_model_means_no_title():
    assert title_for("random phone") is None


def test_title_skips_what_code_doesnt_know():
    # no storage, colour or network in the text: left out, never guessed
    assert title_for("iPhone 13 boxed") == "Apple iPhone 13"


def test_long_title_drops_parts_from_the_end():
    item = {"model_id": "test", "brand": "Brand", "model": "M" * 60, "storage": "128GB",
            "colour": "Midnight", "network": "Unlocked"}
    title = build_title(item)
    assert len(title) <= MAX_LENGTH
    assert title == "Brand " + "M" * 60 + " 128GB"


def test_pence_and_pounds():
    assert to_pence("12.50") == 1250
    assert to_pence("£1,200") == 120000
    assert to_pence(0.1 + 0.2) == 30  # the float mistake is rounded away
    assert pounds(1250) == "£12.50"
    assert pounds(-305) == "-£3.05"


def test_profit():
    # sold for £200, paid £150, £5 postage, 10% + 30p fees
    result = profit(sale=20000, paid=15000, postage=500, fee_percent=10, fee_fixed=30)
    assert result["fees"] == 2030
    assert result["profit"] == 2470
    assert result["margin_percent"] == 12.4  # 12.35 rounds up, like a person would


def test_profit_can_be_a_loss():
    assert profit(sale=10000, paid=12000)["profit"] == -2000


def test_offer_price_rounds_down_to_tidy_numbers():
    assert offer_price(20000) == 17000                     # £200 -> £170
    assert offer_price(9500) == 8000                       # £95 -> £80.75 -> £80
    assert offer_price(1500) == 1200                       # £15 -> £12.75 -> £12
    assert offer_price(20000, discount_percent=10) == 18000
