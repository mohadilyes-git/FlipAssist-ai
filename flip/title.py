"""Build the eBay title from the filled-in fields. Plain code, never AI: the
title is what buyers search for, so it must be exact and the same every time."""

MAX_LENGTH = 80  # eBay's limit


def build_title(item):
    """Brand, model, options, storage, colour, network, skipping anything
    unknown. If it's over 80 characters, parts are dropped from the end.
    No model found means no title: that item is for you."""
    if not item.get("model_id"):
        return None
    parts = [
        item["brand"],
        item["model"],
        *item.get("options", {}).values(),
        item.get("storage"),
        item.get("colour"),
        item.get("network"),
    ]
    parts = [part for part in parts if part]
    while len(" ".join(parts)) > MAX_LENGTH and len(parts) > 2:
        parts.pop()
    return " ".join(parts)[:MAX_LENGTH]
