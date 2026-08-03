from flip.catalogue import load_catalogue
from flip.score import score


def test_fields_that_dont_apply_arent_counted_as_right():
    items = [{"id": "x", "original_title": "PS5 Slim digital 1TB white", "my_notes": "",
              "answer": {"model_id": "ps5-slim", "storage": "1TB", "colour": "White", "network": None,
                         "options": {"Edition": "Digital Edition"}}}]
    totals, wrong = score(items, load_catalogue())
    assert totals["network"] == {"right": 0, "left for you": 0, "wrong": 0, "doesn't apply": 1}
    assert totals["model_id"]["right"] == 1
    assert wrong == []
