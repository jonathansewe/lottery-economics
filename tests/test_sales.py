"""Sales estimator tests on synthetic draws where the true ticket count is known."""

import numpy as np
import pandas as pd
import pytest

from lottery import sales


def test_tier_keys_cover_lotto_and_take5():
    assert set(sales.tier_probabilities("ny_lotto")) == {"6+0", "5+1", "5+0", "4", "3"}
    assert set(sales.tier_probabilities("take5")) == {"5", "4", "3", "2"}
    assert len(sales.tier_probabilities("powerball")) == 9


def test_winner_count_estimator_is_unbiased_and_ci_covers():
    rng = np.random.default_rng(0)
    probs = sales.tier_probabilities("powerball")
    true_n = 12_000_000
    rows = []
    for i in range(400):
        d = f"2024-{1 + i // 31 % 12:02d}-{1 + i % 28:02d}-{i}"  # unique fake keys
        for tier, p in probs.items():
            rows.append({"game": "powerball", "draw_date": d, "scope": "national",
                         "tier": tier, "winners": rng.poisson(true_n * p)})
    est = sales.from_winner_counts("powerball", pd.DataFrame(rows))
    assert est["tickets"].mean() == pytest.approx(true_n, rel=0.002)
    covered = ((est["ci_low"] <= true_n) & (true_n <= est["ci_high"])).mean()
    assert covered == pytest.approx(0.95, abs=0.03)
    assert set(est["scope"]) == {"national"}


def test_unknown_tier_raises():
    df = pd.DataFrame([{"game": "take5", "draw_date": "2024-01-01", "scope": "NY", "tier": "6", "winners": 1}])
    with pytest.raises(ValueError, match="unknown tiers"):
        sales.from_winner_counts("take5", df)


def test_jackpot_growth_recovers_sales_and_skips_resets():
    share = sales.JACKPOT_SHARE_OF_SALES["ny_lotto"][0]
    price = 0.5
    true_plays = [4e6, 5e6, 6e6]
    cash, rows = 1e6, []
    for i, n in enumerate([None] + true_plays):
        if n is not None:
            cash += n * price * share
        rows.append({"game": "ny_lotto", "draw_date": f"2024-01-0{i + 1}", "jackpot_cash": cash,
                     "jackpot_won": "no"})
    rows.append({"game": "ny_lotto", "draw_date": "2024-01-05", "jackpot_cash": cash, "jackpot_won": "yes"})
    rows.append({"game": "ny_lotto", "draw_date": "2024-01-06", "jackpot_cash": 1e6, "jackpot_won": "no"})
    est = sales.from_jackpot_growth("ny_lotto", pd.DataFrame(rows))
    assert est["tickets"].tolist() == pytest.approx(true_plays)  # zero growth and the reset are skipped
    assert set(est["scope"]) == {"NY"}


def test_jackpot_growth_disabled_without_verified_share():
    df = pd.DataFrame([{"game": "powerball", "draw_date": "2024-01-01", "jackpot_cash": 1e8, "jackpot_won": "no"},
                       {"game": "powerball", "draw_date": "2024-01-03", "jackpot_cash": 1.2e8, "jackpot_won": "no"}])
    assert sales.from_jackpot_growth("powerball", df).empty
    assert sales.JACKPOT_SHARE_OF_SALES["powerball"][1] is False


def test_comparison_and_mape():
    est = pd.DataFrame([
        {"game": "take5", "draw_date": "2024-01-01", "method": "winner_counts", "scope": "NY", "tickets": 1.1e6},
        {"game": "take5", "draw_date": "2024-01-02", "method": "winner_counts", "scope": "NY", "tickets": 0.9e6},
        {"game": "take5", "draw_date": "2024-02-01", "method": "winner_counts", "scope": "NY", "tickets": 1.0e6},
    ])
    off = pd.DataFrame([{"game": "take5", "period_start": "2024-01-01", "period_end": "2024-01-31",
                         "scope": "NY", "sales_dollars": 2.5e6}])
    comp = sales.compare_with_official(est, off)
    assert comp.iloc[0]["draws_estimated"] == 2
    assert comp.iloc[0]["error_pct"] == pytest.approx(-20.0)
    assert sales.mape(comp) == {"take5/winner_counts": pytest.approx(20.0)}


def test_report_on_empty_templates(tmp_path):
    sales.ensure_templates(tmp_path)
    rep = sales.report(tmp_path)
    assert rep["available"] is False and rep["estimates"] == []
    assert rep["scope"]["powerball"] == "national"
    assert rep["shares"]["take5"]["share"] == pytest.approx(0.10)
