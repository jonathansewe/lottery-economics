from fractions import Fraction
from math import comb, exp, factorial

import pytest

from lottery import math as lm
from lottery import rules
from lottery.rules import JACKPOT

PRIZED_ERAS = [e for e in rules.ERAS.values() if e.tiers]


def _matches_published(one_in: float, published: float) -> bool:
    """Published odds are rounded: Powerball to 2 decimals, others to integers."""
    if published != int(published):
        return abs(one_in - published) < 0.005 + 1e-9
    return round(one_in) == published


@pytest.mark.parametrize("era", PRIZED_ERAS, ids=lambda e: e.era_id)
def test_every_tier_matches_official_odds(era):
    for row in lm.odds_table(era):
        assert _matches_published(row["one_in"], row["official_one_in"]), (
            era.era_id, row["white"], row["special"], row["one_in"], row["official_one_in"])


@pytest.mark.parametrize("era", PRIZED_ERAS, ids=lambda e: e.era_id)
def test_overall_odds_match_official(era):
    one_in = float(1 / lm.overall_probability(era))
    assert _matches_published(one_in, era.official_overall_odds), one_in


def test_mm_2013_overall_odds_one_in_15():
    # The 2013 release quotes overall odds of 1 in 15. That era's prize table is
    # not in rules.py, but its structure was the same 9 tiers, so check the matrix.
    era = rules.ERAS["mm_2013"]
    tiers = [(5, 1), (5, 0), (4, 1), (4, 0), (3, 1), (3, 0), (2, 1), (1, 1), (0, 1)]
    p = sum(lm.tier_probability(era, w, s) for w, s in tiers)
    assert round(float(1 / p)) == 15


@pytest.mark.parametrize("era", [e for e in rules.ERAS.values() if e.special_pool], ids=lambda e: e.era_id)
def test_all_outcomes_sum_to_one(era):
    total = sum(lm.tier_probability(era, w, s)
                for w in range(era.white_drawn + 1) for s in (0, 1))
    assert total == 1


def test_jackpot_is_one_combination():
    era = rules.current_era("powerball")
    assert lm.jackpot_probability(era) == pytest.approx(1 / (comb(69, 5) * 26))
    assert comb(69, 5) * 26 == 292_201_338


def test_numbers_odds_and_ev():
    odds = {r["play"]: r for r in lm.numbers_odds()}
    for r in odds.values():
        assert round(r["one_in"]) == r["official_odds"]
    ev = {r["play"]: r["ev_per_dollar"] for r in lm.numbers_ev()}
    assert ev == pytest.approx({"straight": 0.50, "box_3way": 0.48, "box_6way": 0.48})


def test_mm_multiplier_distribution():
    mult = rules.current_era("mega_millions").multiplier
    assert sum(mult.values()) == pytest.approx(1.0)
    assert sum(f * q for f, q in mult.items()) == pytest.approx(3.0)
    # Matches the published "1 in" values: 2.13, 3.2, 8, 16, 32
    published = {2: 2.13, 3: 3.2, 4: 8, 5: 16, 10: 32}
    for f, one_in in published.items():
        assert 1 / mult[f] == pytest.approx(one_in, abs=0.01)


# --- split model -----------------------------------------------------------
@pytest.mark.parametrize("lam", [1e-6, 0.01, 0.5, 1.0, 3.0, 10.0])
def test_expected_share_closed_form_matches_series(lam):
    series = sum(exp(-lam) * lam**k / factorial(k) / (k + 1) for k in range(80))
    assert lm.expected_share(lam, 1) == pytest.approx(series, rel=1e-12)


def test_expected_share_limits():
    assert lm.expected_share(1e-9, 0) == 1.0
    assert lm.p_shared(1e-9, 0) == 0.0
    # lam = 1: you keep (1 - 1/e) ~ 63.2% on average; P(shared) = 1 - 1/e
    assert lm.expected_share(1.0, 1) == pytest.approx(1 - exp(-1))
    assert lm.p_shared(1.0, 1) == pytest.approx(1 - exp(-1))


def test_expected_share_against_monte_carlo():
    import numpy as np
    rng = np.random.default_rng(0)
    p, n = 1 / 292_201_338, 300_000_000
    others = rng.binomial(n, p, size=400_000)
    assert np.mean(1 / (others + 1)) == pytest.approx(lm.expected_share(p, n), rel=0.01)


# --- EV ---------------------------------------------------------------------
@pytest.mark.parametrize("game", ["powerball", "mega_millions"])
def test_ev_steps_only_go_down(game):
    era = rules.current_era(game)
    ev = lm.ev_breakdown(era, 1_000_000_000, tickets_sold=200_000_000)
    totals = [ev[s]["total_per_dollar"] for s in ("advertised", "cash", "after_tax", "with_split")]
    assert totals == sorted(totals, reverse=True)
    assert 0 < ev["expected_share"] < 1


def test_powerball_fixed_prize_ev_by_hand():
    era = rules.current_era("powerball")
    N = comb(69, 5) * 26
    # number of tickets (out of N) that hit each fixed tier
    ways = {
        (5, 0): comb(5, 5) * comb(64, 0) * 25, (4, 1): comb(5, 4) * comb(64, 1) * 1,
        (4, 0): comb(5, 4) * comb(64, 1) * 25, (3, 1): comb(5, 3) * comb(64, 2) * 1,
        (3, 0): comb(5, 3) * comb(64, 2) * 25, (2, 1): comb(5, 2) * comb(64, 3) * 1,
        (1, 1): comb(5, 1) * comb(64, 4) * 1, (0, 1): comb(64, 5) * 1,
    }
    prizes = {(t.white, t.special): t.prize for t in era.tiers if t.prize != JACKPOT}
    by_hand = Fraction(sum(ways[k] * prizes[k] for k in ways), N)
    assert lm.fixed_prize_ev(era) == pytest.approx(float(by_hand))


def test_mega_millions_fixed_ev_is_three_times_base():
    era = rules.current_era("mega_millions")
    base = sum(float(lm.tier_probability(era, t.white, t.special)) * t.prize
               for t in era.tiers if t.prize != JACKPOT)
    assert lm.fixed_prize_ev(era) == pytest.approx(3 * base)


def test_after_tax_only_touches_prizes_over_threshold():
    era = rules.current_era("powerball")
    full = lm.fixed_prize_ev(era, 0.5)
    untaxed = lm.fixed_prize_ev(era, 0.0)
    big = sum(float(lm.tier_probability(era, t.white, t.special)) * t.prize
              for t in era.tiers if t.prize != JACKPOT and t.prize > 5000)
    assert untaxed - full == pytest.approx(0.5 * big)


@pytest.mark.parametrize("game", ["powerball", "mega_millions"])
def test_break_even_jackpot_gives_one_dollar(game):
    era = rules.current_era(game)
    j = lm.break_even_jackpot(era, tax_rate=0.4)
    ev = lm.ev_breakdown(era, j, tax_rate=0.4, tickets_sold=0)
    assert ev["after_tax"]["total_per_dollar"] == pytest.approx(1.0)
