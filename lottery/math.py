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
from .rules import JACKPOT, NUMBERS_PLAYS, Era


# ---------------------------------------------------------------------------
# Odds
# ---------------------------------------------------------------------------
def tier_probability(era: Era, white: int, special: int) -> Fraction:
    m, k, s = era.white_pool, era.white_drawn, era.special_pool
    p_white = Fraction(comb(k, white) * comb(m - k, k - white), comb(m, k))
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
def _taxed(amount: float, rate: float) -> float:
    return amount if amount <= config.TAX_FREE_PRIZE_MAX else amount * (1 - rate)


def fixed_prize_ev(era: Era, tax_rate: float = 0.0) -> float:
    """Expected dollars from all non-jackpot tiers for one play (not per $1).

    Mega Millions' built-in multiplier is applied per multiplier value, because
    multiplying can push a prize over the tax threshold.
    """
    mult = era.multiplier or {1: 1.0}
    total = 0.0
    for t in era.tiers:
        if t.prize == JACKPOT:
            continue
        p = float(tier_probability(era, t.white, t.special))
        total += p * sum(q * _taxed(t.prize * f, tax_rate) for f, q in mult.items())
    return total


def jackpot_probability(era: Era) -> float:
    t = next(t for t in era.tiers if t.prize == JACKPOT)
    return float(tier_probability(era, t.white, t.special))


def ev_breakdown(era: Era, advertised_jackpot: float, cash_ratio: float | None = None,
                 tickets_sold: float = 0, tax_rate: float | None = None) -> dict:
    """Expected return per $1 spent, step by step from the advertised number to reality.

    Steps (each one per $1 of ticket price):
      1. advertised  - annuity jackpot, no tax, no splitting  (what the billboard implies)
      2. cash        - jackpot at its lump-sum cash value
      3. after_tax   - federal + NY State + NYC tax on prizes over the threshold
      4. with_split  - also multiply the jackpot by the expected share (Poisson)
    """
    if cash_ratio is None:
        cash_ratio = config.CASH_RATIO[era.game]
    if tax_rate is None:
        tax_rate = config.combined_tax_rate()
    pj = jackpot_probability(era)
    share = expected_share(pj, tickets_sold)
    fixed_pre = fixed_prize_ev(era, 0.0)
    fixed_post = fixed_prize_ev(era, tax_rate)
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
                       tax_rate: float = 0.0) -> float:
    """Advertised jackpot at which EV per $1 reaches $1, *ignoring* splitting.

    Solves fixed + p * J * cash_ratio * (1 - tax) = price for J. With splitting
    there may be no break-even at all, because bigger jackpots sell more tickets.
    """
    if cash_ratio is None:
        cash_ratio = config.CASH_RATIO[era.game]
    pj = jackpot_probability(era)
    fixed = fixed_prize_ev(era, tax_rate)
    return (era.price - fixed) / (pj * cash_ratio * (1 - tax_rate))


def numbers_ev() -> list[dict]:
    """NY Numbers: expected return per $1 for each play type (fixed prizes, all
    under the tax threshold)."""
    return [
        {"play": p["play"], "label": p["label"], "ev_per_dollar": p["ways"] / 1000 * p["prize"]}
        for p in NUMBERS_PLAYS
    ]
