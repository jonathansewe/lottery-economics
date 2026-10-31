"""Odds and EV for every NY game beyond Powerball / Mega Millions.

Published figures come from rules.py (each with a source). Where no official odds
were found the exact value is still tested against an independent hand count."""

from fractions import Fraction
from math import comb

import pytest

from lottery import config, rules
from lottery import math as lm
from lottery.rules import FREE_PLAY, PARIMUTUEL


def _close(one_in, published):
    if published != int(published):
        return abs(one_in - published) < 0.005 + 1e-9
    return round(one_in) == published


# --- NY Lotto (bonus ball) ----------------------------------------------------
def test_lotto_tiers_by_hand():
    era = rules.ERAS["lotto_2001"]
    N = comb(59, 6)
    assert N == 45_057_474
    hand = {(6, 0): Fraction(1, N), (5, 1): Fraction(6, N), (5, 0): Fraction(6 * 52, N),
            (4, None): Fraction(comb(6, 4) * comb(53, 2), N), (3, None): Fraction(comb(6, 3) * comb(53, 3), N)}
    for t in era.tiers:
        assert lm.tier_probability(era, t.white, t.special) == hand[(t.white, t.special)]


def test_lotto_third_prize_published_odds_conflict():
    # 2020 sheet: 1 in 144,414.98 (matches counting). A 2026 proposed correction says
    # 144,418.98. Exact value settles it in favour of the 2020 sheet.
    era = rules.ERAS["lotto_2001"]
    one_in = float(1 / lm.tier_probability(era, 5, 0))
    assert one_in == pytest.approx(144_414.98, abs=0.005)
    assert abs(one_in - 144_418.98) > 3


def test_lotto_bonus_outcomes_sum_to_one_and_overall_odds():
    era = rules.ERAS["lotto_2001"]
    assert sum(lm.tier_probability(era, w, b) for w in range(7) for b in (0, 1)) == 1
    per_play = float(1 / lm.overall_probability(era))
    assert round(per_play, 2) == 92.05
    assert round(per_play / era.plays_per_dollar, 2) == 46.02  # NY's "per $1" figure


def test_lotto_pool_shares_sum_to_one_and_ev_is_40_percent():
    era = rules.ERAS["lotto_2001"]
    assert sum(t.pool_share for t in era.tiers) == pytest.approx(1.0)
    (ev,) = lm.game_ev(era, "none")
    assert ev["pre_tax"] == pytest.approx(0.40)
    (owed,) = lm.game_ev(era, "owed")
    assert owed["after_tax"] == pytest.approx(0.40 * (1 - config.combined_tax_rate()))


def test_lotto_typical_prizes():
    era = rules.ERAS["lotto_2001"]
    by_tier = {(t.white, t.special): lm.typical_parimutuel_prize(era, t) for t in era.tiers}
    # 5th prize: $0.50 * 40% * 6% * 96.17 = ~$1.15 per winning play
    assert by_tier[(3, None)] == pytest.approx(0.5 * 0.4 * 0.06 * 45_057_474 / 468_520)
    # withholding view taxes only tiers whose typical prize exceeds $5,000 (jackpot, 2nd)
    (w,) = lm.game_ev(era, "withholding")
    rate = config.tax_params("withholding")[0]
    assert by_tier[(5, 0)] < 5000 < by_tier[(5, 1)]
    assert w["after_tax"] == pytest.approx(0.40 * (1 - rate * (0.75 + 0.0725)))


# --- Take 5 ---------------------------------------------------------------------
def test_take5_odds():
    era = rules.ERAS["take5_1992"]
    for row in lm.odds_rows(era)["tiers"]:
        assert _close(row["one_in"], row["official_one_in"]), row
    # NY's page says overall 1 in 8.7; exact counting gives 8.77 (documented discrepancy)
    assert float(1 / lm.overall_probability(era)) == pytest.approx(8.774, abs=0.001)
    (ev,) = lm.game_ev(era, "none")
    assert ev["pre_tax"] == pytest.approx(0.50)
    assert [t.prize for t in era.tiers] == [PARIMUTUEL] * 3 + [FREE_PLAY]


# --- digits -------------------------------------------------------------------
def test_win4_odds_and_ev():
    era = rules.ERAS["win4_1980"]
    rows = {r["play"]: r for r in lm.odds_rows(era)["plays"]}
    assert {k: round(r["one_in"]) for k, r in rows.items()} == {
        "straight": 10000, "box_24way": 417, "box_12way": 833, "box_6way": 1667, "box_4way": 2500}
    # each box size really has that many distinct orderings
    from itertools import permutations
    for digits, ways in [("1234", 24), ("1123", 12), ("1122", 6), ("1112", 4)]:
        assert len(set(permutations(digits))) == ways
    evs = {r["play"]: r["pre_tax"] for r in lm.game_ev(era, "none")}
    assert evs == pytest.approx({"straight": 0.5, "box_24way": 0.48, "box_12way": 0.48,
                                 "box_6way": 0.48, "box_4way": 0.48})
    assert not any(r["verified"] for r in lm.game_ev(era))  # payouts unverified -> flagged


def test_numbers_era_is_digits_kind_and_matches_old_function():
    era = rules.ERAS["numbers_1980"]
    assert era.kind == "digits"
    new = {r["play"]: r["pre_tax"] for r in lm.game_ev(era, "none")}
    old = {r["play"]: r["ev_per_dollar"] for r in lm.numbers_ev()}
    assert new == pytest.approx(old)


# --- keno ---------------------------------------------------------------------
def test_pick10_every_tier_and_overall():
    era = rules.ERAS["pick10_1987"]
    rows = lm.odds_rows(era)["10-spot"]
    for r in rows:
        assert _close(r["one_in"], r["official_one_in"]), r
    overall = 1 / sum(float(r["probability"]) for r in rows)
    # Published overall is 1 in 17.00; every tier matches but the exact overall is
    # 16.94 (documented discrepancy in rules.py and the README).
    assert round(overall, 2) == 16.94
    assert comb(80, 10) // comb(20, 10) == 8_911_711


@pytest.mark.parametrize("spots", range(1, 11))
def test_quick_draw_overall_odds_per_spot_game(spots):
    # Checks each spot table's *structure* (which match counts pay) against the
    # published overall odds, since per-tier odds weren't published in what we found.
    era = rules.ERAS["qd_2013"]
    rows = lm.odds_rows(era)[f"{spots}-spot"]
    overall = 1 / sum(float(r["probability"]) for r in rows)
    assert round(overall, 2) == era.spot_overall[spots]


def test_keno_probabilities_sum_to_one():
    era = rules.ERAS["qd_2013"]
    for spots in range(1, 11):
        assert sum(lm.keno_probability(era, spots, k) for k in range(spots + 1)) == 1


def test_quick_draw_ev_below_one_and_unverified_flagged():
    era = rules.ERAS["qd_2013"]
    evs = {r["play"]: r for r in lm.game_ev(era, "none")}
    assert all(0.4 < r["pre_tax"] < 0.7 for r in evs.values()), evs
    assert evs["8-spot"]["verified"] and not evs["10-spot"]["verified"]


# --- Cash4Life / Millionaire for Life ---------------------------------------------
@pytest.mark.parametrize("era_id", ["c4l_2014", "mfl_2026"])
def test_life_games_odds(era_id):
    era = rules.ERAS[era_id]
    for r in lm.odds_rows(era)["tiers"]:
        if r["official_one_in"] is not None:
            assert _close(r["one_in"], r["official_one_in"]), r
    (ev,) = lm.game_ev(era, "none")
    assert 0 < ev["pre_tax"] < 1


def test_cash4life_is_retired_and_unverified_values_flagged():
    era = rules.current_era("cash4life")
    assert era.last_draw is not None
    assert not lm.game_ev(era)[0]["verified"]
    assert "cash4life" in rules.RETIRED


# --- registry hygiene ---------------------------------------------------------------
def test_every_era_documents_how_it_was_verified():
    for era in rules.ERAS.values():
        assert era.verified, era.era_id
        assert era.kind in ("lotto", "digits", "keno")


def test_every_game_has_ev_under_one_dollar():
    for game in rules.GAMES:
        era = rules.current_era(game)
        if game in ("powerball", "mega_millions"):
            continue  # depends on the jackpot; covered in test_math
        for row in lm.game_ev(era, "none"):
            assert row["pre_tax"] < 1, (game, row)
