"""Exact odds and expected value.

Everything here is closed-form; nothing is simulated.

Odds for a "k of m, plus 1 of s" game (hypergeometric counting):

    P(match j whites, special b) =  C(k, j) * C(m-k, k-j) / C(m, k)
                                  * (1/s if b else (s-1)/s)

C(k, j): choose which j of *your* k numbers are among the winning k.
C(m-k, k-j): your other k-j numbers come from the m-k losing numbers.
C(m, k): all equally likely ways to pick k numbers.

Probabilities are kept as `fractions.Fraction`, so they are exact and the tests
can check them against the published "1 in X" values without float drift.
"""

from __future__ import annotations

import math as _m
from fractions import Fraction
from math import comb

from . import config
from .rules import FREE_PLAY, JACKPOT, NUMBERS_PLAYS, PARIMUTUEL, Era


# ---------------------------------------------------------------------------
# Odds
# ---------------------------------------------------------------------------
def tier_probability(era: Era, white: int, special: int | None) -> Fraction:
    """P(exactly `white` matches, and the special/bonus condition).

    special=None means the special ball doesn't matter for this tier.
    Bonus ball (NY Lotto): drawn from the m-k balls left after the k winners. If you
    matched j, your k-j other numbers are among those m-k, so
    P(bonus is one of yours | j) = (k-j)/(m-k).
    """
    m, k, s = era.white_pool, era.white_drawn, era.special_pool
    p_white = Fraction(comb(k, white) * comb(m - k, k - white), comb(m, k))
    if special is None:
        return p_white
    if era.bonus:
        p_bonus = Fraction(k - white, m - k)
        return p_white * (p_bonus if special else 1 - p_bonus)
    p_special = Fraction(1, s) if special else Fraction(s - 1, s)
    return p_white * p_special


def odds_table(era: Era) -> list[dict]:
    """One row per prize tier: exact probability, '1 in X', published odds."""
    rows = []
    for t in era.tiers:
        p = tier_probability(era, t.white, t.special)
        rows.append({
            "white": t.white,
            "special": t.special,
            "prize": t.prize,
            "probability": p,
            "one_in": float(1 / p),
            "official_one_in": t.official_odds,
        })
    return rows


def overall_probability(era: Era) -> Fraction:
    return sum((tier_probability(era, t.white, t.special) for t in era.tiers), Fraction(0))


def keno_probability(era: Era, spots: int, matches: int) -> Fraction:
    """Keno (Quick Draw, Pick 10): you pick `spots` numbers, the lottery draws d of m.
    P(exactly `matches` of yours drawn) = C(d, matches) C(m-d, spots-matches) / C(m, spots)."""
    m, d = era.white_pool, era.white_drawn
    return Fraction(comb(d, matches) * comb(m - d, spots - matches), comb(m, spots))


def digits_probability(era: Era, ways: int) -> Fraction:
    """Digit games: 10^n equally likely results; a play covering `ways` of them."""
    return Fraction(ways, 10 ** era.white_drawn)


def numbers_odds() -> list[dict]:
    """NY Numbers: 1000 equally likely results; a play covering `ways` of them."""
    return [
        {**p, "probability": Fraction(p["ways"], 1000), "one_in": 1000 / p["ways"]}
        for p in NUMBERS_PLAYS
    ]


# ---------------------------------------------------------------------------
# Jackpot splitting (Poisson model)
# ---------------------------------------------------------------------------
def expected_share(p_jackpot: float, other_tickets: float) -> float:
    """Expected fraction of the jackpot you keep, given that you hit it.

    The number of *other* winning tickets K ~ Binomial(N, p) ~ Poisson(lam),
    lam = N * p (excellent approximation: N is large, p is tiny). If K others
    also win, you get 1/(K+1) of the jackpot, so

        E[1/(K+1)] = sum_k e^-lam lam^k / k! * 1/(k+1)
                   = (e^-lam / lam) * sum_k lam^(k+1)/(k+1)!
                   = (1 - e^-lam) / lam

    Assumes other players pick numbers uniformly at random (true for quick
    picks). Real players over-pick birthdays/patterns, so if *you* pick
    popular numbers your real share is lower than this.
    """
    lam = p_jackpot * other_tickets
    if lam == 0:
        return 1.0
    return -_m.expm1(-lam) / lam


def p_shared(p_jackpot: float, other_tickets: float) -> float:
    """P(at least one other winner) = 1 - e^-lam."""
    return -_m.expm1(-p_jackpot * other_tickets)


# ---------------------------------------------------------------------------
# Expected value
# ---------------------------------------------------------------------------
def _taxed(amount: float, rate: float, threshold: float = 0.0) -> float:
    """Prize after tax. Only the withholding view uses a threshold; tax owed
    applies to every prize (all gambling winnings are taxable income)."""
    return amount if amount <= threshold else amount * (1 - rate)


def fixed_prize_ev(era: Era, tax_rate: float = 0.0, threshold: float = 0.0) -> float:
    """Expected dollars from all non-jackpot tiers for one play (not per $1).

    Mega Millions' built-in multiplier is applied per multiplier value, because
    multiplying can push a prize over the withholding threshold.
    """
    mult = era.multiplier or {1: 1.0}
    total = 0.0
    for t in era.tiers:
        if t.prize == JACKPOT:
            continue
        p = float(tier_probability(era, t.white, t.special))
        total += p * sum(q * _taxed(t.prize * f, tax_rate, threshold) for f, q in mult.items())
    return total


def jackpot_probability(era: Era) -> float:
    t = next(t for t in era.tiers if t.prize == JACKPOT)
    return float(tier_probability(era, t.white, t.special))


def ev_breakdown(era: Era, advertised_jackpot: float, cash_ratio: float | None = None,
                 tickets_sold: float = 0, tax_rate: float | None = None,
                 tax_mode: str = "owed") -> dict:
    """Expected return per $1 spent, step by step from the advertised number to reality.

    Steps (each one per $1 of ticket price):
      1. advertised  - annuity jackpot, no tax, no splitting  (what the billboard implies)
      2. cash        - jackpot at its lump-sum cash value
      3. after_tax   - federal + NY State + NYC tax (tax_mode "owed": on every prize;
                       "withholding": only what is withheld on prizes over $5,000)
      4. with_split  - also multiply the jackpot by the expected share (Poisson)
    An explicit tax_rate overrides the mode's rate but keeps its threshold.
    """
    if cash_ratio is None:
        cash_ratio = config.CASH_RATIO[era.game]
    mode_rate, threshold = config.tax_params(tax_mode)
    if tax_rate is None:
        tax_rate = mode_rate
    pj = jackpot_probability(era)
    share = expected_share(pj, tickets_sold)
    fixed_pre = fixed_prize_ev(era, 0.0)
    fixed_post = fixed_prize_ev(era, tax_rate, threshold)
    cash = advertised_jackpot * cash_ratio

    steps = {
        "advertised": (fixed_pre, pj * advertised_jackpot),
        "cash": (fixed_pre, pj * cash),
        "after_tax": (fixed_post, pj * cash * (1 - tax_rate)),
        "with_split": (fixed_post, pj * cash * (1 - tax_rate) * share),
    }
    out = {
        "price": era.price,
        "advertised_jackpot": advertised_jackpot,
        "cash_ratio": cash_ratio,
        "tax_rate": tax_rate,
        "tax_mode": tax_mode,
        "tax_threshold": threshold,
        "tickets_sold": tickets_sold,
        "p_jackpot": pj,
        "p_shared": p_shared(pj, tickets_sold),
        "expected_share": share,
    }
    for name, (fixed, jack) in steps.items():
        out[name] = {
            "fixed_per_dollar": fixed / era.price,
            "jackpot_per_dollar": jack / era.price,
            "total_per_dollar": (fixed + jack) / era.price,
        }
    return out


def break_even_jackpot(era: Era, cash_ratio: float | None = None,
                       tax_rate: float = 0.0, threshold: float = 0.0) -> float:
    """Advertised jackpot at which EV per $1 reaches $1, *ignoring* splitting.

    Solves fixed + p * J * cash_ratio * (1 - tax) = price for J. With splitting
    there may be no break-even at all, because bigger jackpots sell more tickets.
    """
    if cash_ratio is None:
        cash_ratio = config.CASH_RATIO[era.game]
    pj = jackpot_probability(era)
    fixed = fixed_prize_ev(era, tax_rate, threshold)
    return (era.price - fixed) / (pj * cash_ratio * (1 - tax_rate))


def _row(t, p: Fraction) -> dict:
    return {"white": t.white, "special": t.special, "prize": t.prize, "label": t.label,
            "verified": t.verified, "pool_share": t.pool_share,
            "probability": p, "one_in": float(1 / p), "official_one_in": t.official_odds}


def odds_rows(era: Era) -> dict:
    """Every tier's exact odds for any game kind, keyed by play (one key for most games)."""
    if era.kind == "keno":
        return {f"{spots}-spot": [_row(t, keno_probability(era, spots, t.white)) for t in tiers]
                for spots, tiers in sorted(era.spot_tables.items(), reverse=True)}
    if era.kind == "digits":
        return {"plays": [{**p, "probability": digits_probability(era, p["ways"]),
                           "one_in": 10 ** era.white_drawn / p["ways"],
                           "verified": p.get("verified", True)} for p in era.plays]}
    return {"tiers": [_row(t, tier_probability(era, t.white, t.special)) for t in era.tiers]}


def typical_parimutuel_prize(era: Era, tier) -> float | None:
    """Expected prize per winning play for a pari-mutuel tier, ignoring rollovers.

    Per play, the tier's pool is price * pool_fraction * share and the expected number
    of winners is p, so the prize per winner is price * fraction * share / p.
    Ticket sales cancel out, which is why this works without knowing sales."""
    if tier.pool_share is None or era.prize_pool_fraction is None:
        return None
    p = float(tier_probability(era, tier.white, tier.special))
    return era.price * era.prize_pool_fraction * tier.pool_share / p


def _fixed_tiers_ev(era: Era, rows, rate: float, threshold: float) -> tuple[float, float]:
    pre = sum(float(r["probability"]) * r["prize"] for r in rows)
    post = sum(float(r["probability"]) * _taxed(r["prize"], rate, threshold) for r in rows)
    return pre / era.price, post / era.price


def game_ev(era: Era, tax_mode: str = "owed") -> list[dict]:
    """EV per $1 for games without a rolling jackpot input (everything except
    Powerball / Mega Millions, which use ev_breakdown). One row per play type.

    pari-mutuel games: long-run EV = the share of sales paid as prizes (rollovers only
    move money between draws). After tax, tiers whose typical prize exceeds the
    threshold are taxed; with tax owed the threshold is 0 so everything is.
    """
    rate, threshold = config.tax_params(tax_mode)
    out = []
    if era.kind == "keno":
        for play, rows in odds_rows(era).items():
            pre, post = _fixed_tiers_ev(era, rows, rate, threshold)
            out.append({"play": play, "pre_tax": pre, "after_tax": post,
                        "verified": all(r["verified"] for r in rows)})
    elif era.kind == "digits":
        for r in odds_rows(era)["plays"]:
            pre = float(r["probability"]) * r["prize"] / era.price
            out.append({"play": r["play"], "label": r["label"], "pre_tax": pre,
                        "after_tax": float(r["probability"]) * _taxed(r["prize"], rate, threshold) / era.price,
                        "verified": r["verified"]})
    elif era.prize_pool_fraction is not None:
        pre = era.prize_pool_fraction
        taxed_share = 0.0
        for t in era.tiers:
            typical = era.price if t.prize == FREE_PLAY else typical_parimutuel_prize(era, t)
            # unknown pool share: treated as under the threshold (NY's published estimates are)
            if typical is not None and typical > threshold and t.pool_share is not None:
                taxed_share += t.pool_share
            elif threshold == 0:
                taxed_share = None  # owed: everything is taxed
                break
        post = pre * (1 - rate) if taxed_share is None else pre * (1 - rate * taxed_share)
        out.append({"play": "pari-mutuel", "pre_tax": pre, "after_tax": post,
                    "verified": True, "note": "long-run share of sales paid as prizes"})
    else:
        rows = odds_rows(era)["tiers"]
        pre, post = _fixed_tiers_ev(era, rows, rate, threshold)
        out.append({"play": "base", "pre_tax": pre, "after_tax": post,
                    "verified": all(r["verified"] for r in rows)})
    return out


def numbers_ev(tax_mode: str = "owed") -> list[dict]:
    """NY Numbers: expected return per $1 for each play type, before and after tax."""
    rate, threshold = config.tax_params(tax_mode)
    return [
        {"play": p["play"], "label": p["label"], "ev_per_dollar": p["ways"] / 1000 * p["prize"],
         "after_tax_per_dollar": p["ways"] / 1000 * _taxed(p["prize"], rate, threshold)}
        for p in NUMBERS_PLAYS
    ]
