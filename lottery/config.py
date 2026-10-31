"""Every tunable assumption lives here, with its source.

`verified` records exactly how a value was checked when this was written
(2026-10-30). The build container could not open the official sites directly,
so "search-snippet" means the value was read from a search-engine snippet of
the official page named in the comment, not from the page itself.
Re-check these before relying on them.
"""

# --- Taxes -------------------------------------------------------------------
# Rates are applied as flat marginal rates to the *whole* prize. For jackpots
# that is almost exact (nearly all of the money sits in the top bracket). For
# mid-size prizes it overstates tax, so post-tax EV here is a slight lower bound.
TAX = {
    "federal": {
        # 37% applies to single filers' taxable income over $640,600 in 2026.
        # https://www.irs.gov/pub/irs-drop/rp-25-32.pdf  (Rev. Proc. 2025-32)
        # https://www.irs.gov/publications/p505          (Pub 505, 2026, Schedule X)
        "rate": 0.37,
        "verified": "search-snippet of irs.gov (Rev. Proc. 2025-32, Pub 505)",
    },
    "ny_state": {
        # 10.90% on NY taxable income over $25,000,000 (10.30% from $5M to $25M).
        # https://www.tax.ny.gov/data/stats/ter/fiscal-year27/personal-income-tax.htm
        "rate": 0.109,
        "verified": "search-snippet of tax.ny.gov tax expenditure report",
    },
    "nyc": {
        # NYC resident top rate 3.876% (base 3.4% + 14% surcharge); unchanged since TY2017.
        # https://www.tax.ny.gov/pdf/memos/income/m10_7i.pdf
        # https://comptroller.nyc.gov/reports/raising-revenues/
        "rate": 0.03876,
        "verified": "search-snippet of tax.ny.gov memo + NYC Comptroller report",
    },
}

# All gambling winnings are taxable income, so the default "owed" view taxes
# every prize. The separate "withholding" view shows only what is withheld when a
# prize is claimed, which is NOT what you owe:
#   federal: 24% on lottery winnings over $5,000
#     https://www.irs.gov/instructions/iw2g  (Instructions for Forms W-2G, Jan 2026)
#   NY State / NYC: withheld at the highest effective rate on proceeds over $5,000
#     https://www.tax.ny.gov/pdf/publications/income/pub140w.pdf
WITHHOLDING_THRESHOLD = 5_000
WITHHOLDING = {
    "federal": {"rate": 0.24, "verified": "search-snippet of irs.gov W-2G instructions"},
    # "highest effective rate" per Pub 140W; the rate itself is TAX["ny_state"/"nyc"]
    "ny_state": {"rate": 0.109, "verified": "search-snippet of tax.ny.gov Pub 140W (rate = NYS top rate)"},
    "nyc": {"rate": 0.03876, "verified": "search-snippet of tax.ny.gov Pub 140W (rate = NYC top rate)"},
}
TAX_MODES = ("owed", "withholding", "none")


def combined_tax_rate(federal=True, state=True, city=True):
    """Sum of the selected marginal rates (state + city taxes are not deductible
    against federal for most winners since the SALT cap, so simple addition is
    the standard approximation)."""
    rate = 0.0
    if federal:
        rate += TAX["federal"]["rate"]
    if state:
        rate += TAX["ny_state"]["rate"]
    if city:
        rate += TAX["nyc"]["rate"]
    return rate


def tax_params(mode: str = "owed") -> tuple[float, float]:
    """(rate, threshold): prizes strictly above `threshold` are taxed at `rate`.

    owed        every prize taxed at the combined top marginal rate (default)
    withholding only prizes over $5,000, at the rates withheld on claim
    none        no tax
    """
    if mode == "owed":
        return combined_tax_rate(), 0.0
    if mode == "withholding":
        return sum(v["rate"] for v in WITHHOLDING.values()), float(WITHHOLDING_THRESHOLD)
    if mode == "none":
        return 0.0, 0.0
    raise ValueError(f"unknown tax mode {mode!r}; expected one of {TAX_MODES}")


# --- Cash value vs advertised (annuity) jackpot ------------------------------
# The advertised jackpot is a 30-payment annuity; the lump sum ("cash value")
# is what the prize pool actually holds. The ratio moves with interest rates.
# Observed official pairs (search-snippets):
#   Powerball $600M -> $252.7M cash (0.421), powerball.com home page, Oct 2026
#   Mega Millions $50M -> $21.5M cash (0.430), megamillions.com news, Jul 2026
#   Powerball $20M -> $9.3M cash (0.465), powerball.com news, ~Mar 2025
CASH_RATIO = {
    "powerball": 0.421,
    "mega_millions": 0.430,
}

# --- Jackpot-split model -----------------------------------------------------
# Tickets sold per draw are not published by the lotteries in a single
# machine-readable place, so the split model takes ticket sales as an input.
# These are illustrative scenarios, not data.  ASSUMPTION.
TICKETS_SOLD_SCENARIOS = [10_000_000, 50_000_000, 150_000_000, 400_000_000]

# Reference scenario for the landing page's headline number:
# starting jackpot, a quiet draw.
REFERENCE_TICKETS_SOLD = 10_000_000
