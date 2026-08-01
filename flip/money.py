"""Money in plain code: profit and the offer price. Every amount is whole pence
(£12.50 is 1250), because computers store 0.1 + 0.2 as 0.30000000000000004 and
whole numbers never have that problem."""

from decimal import ROUND_HALF_UP, Decimal


def to_pence(pounds):
    """'12.50', '£1,200' or 12.5 -> 1250, 120000, 1250"""
    text = str(pounds).replace("£", "").replace(",", "").strip()
    return int((Decimal(text) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def pounds(pence):
    """1250 -> '£12.50'"""
    sign = "-" if pence < 0 else ""
    pence = abs(pence)
    return f"{sign}£{pence // 100:,}.{pence % 100:02d}"


def percent_of(pence, percent):
    """percent of an amount, rounded to the nearest penny"""
    return int((Decimal(pence) * Decimal(str(percent)) / 100).quantize(Decimal("1"), ROUND_HALF_UP))


def profit(sale, paid, postage=0, fee_percent=0, fee_fixed=0, other_costs=0):
    """What's left after a sale. All amounts in pence.

    sale: everything the buyer pays (item + any postage they pay)
    postage: what you pay to send it
    fee_percent, fee_fixed: your eBay selling fees. They depend on your account
    and eBay changes them, so they're settings, not baked in. On 28 Oct 2026
    eBay UK charged private sellers no final value fee (the buyer pays a
    protection fee); business sellers pay a percentage plus a per-order fee
    """
    fees = percent_of(sale, fee_percent) + fee_fixed if sale else 0
    left = sale - paid - postage - fees - other_costs
    margin = (Decimal(left * 100) / sale).quantize(Decimal("0.1"), ROUND_HALF_UP) if sale else Decimal("0.0")
    return {"fees": fees, "profit": left, "margin_percent": float(margin)}


def offer_price(asking, discount_percent=15):
    """Your opening offer: the asking price minus your discount, rounded down
    to a tidy number (whole pounds under £20, £5 steps from £20)."""
    offer = asking - percent_of(asking, discount_percent)
    step = 500 if offer >= 2000 else 100
    rounded = offer - offer % step
    return rounded if rounded > 0 else offer
