"""Stats tests. Synthetic draws are generated inside each test from a seeded
fair (or deliberately biased) RNG and only ever written to pytest's tmp_path."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from lottery import rules, stats


def test_uniform_counts_give_zero_statistic():
    r = stats.chi_square([10] * 50, n_draws=100, k=5, m=50)
    assert r["statistic"] == 0 and r["p_value"] == 1.0


def test_without_replacement_correction_is_calibrated():
    # Under the null the corrected statistic should be chi-square(m-1): mean m-1,
    # and ~5% of p-values below 0.05. The *uncorrected* one has mean m-k.
    rng = np.random.default_rng(1)
    m, k, n = 20, 5, 300
    raw, ps = [], []
    for _ in range(4000):
        r = stats.chi_square(stats.simulate_counts(n, k, m, rng), n, k, m)
        raw.append(r["statistic_raw"])
        ps.append(r["p_value"])
    assert np.mean(raw) == pytest.approx(m - k, rel=0.03)
    assert np.mean(np.asarray(raw) * (m - 1) / (m - k)) == pytest.approx(m - 1, rel=0.03)
    assert np.mean(np.asarray(ps) < 0.05) == pytest.approx(0.05, abs=0.012)


def test_monte_carlo_p_agrees_with_corrected_chi_square():
    counts = np.array([30] * 10 + [20] * 10)  # 20 balls, k=5 -> 500 slots = 100 draws
    analytic = stats.chi_square(counts, 100, 5, 20)["p_value"]
    mc = stats.monte_carlo_p(counts, 100, 5, 20, sims=3000, seed=3)
    assert mc == pytest.approx(analytic, abs=0.02)


def test_detects_a_biased_machine():
    rng = np.random.default_rng(5)
    w = np.ones(26)
    w[0] = 2.0  # ball 1 twice as likely
    counts = np.bincount(rng.choice(26, size=3000, p=w / w.sum()), minlength=26)
    assert stats.chi_square(counts, 3000, 1, 26)["p_value"] < 1e-6


def test_bonferroni():
    res = stats.bonferroni([{"p_value": 0.01}, {"p_value": 0.02}, {"p_value": 0.5}, {"p_value": 0.013}])
    assert [r["significant"] for r in res] == [True, False, False, False]
    assert res[0]["alpha_bonferroni"] == 0.0125
    assert res[2]["p_bonferroni"] == 1.0


def test_binomial_band_covers_95_percent():
    lo, hi = stats.binomial_band(1000, 5, 69)
    p = 5 / 69
    cover = sps.binom.cdf(hi, 1000, p) - sps.binom.cdf(lo - 1, 1000, p)
    assert cover >= 0.95


def _fake_lotto_csv(path, era, n, rng, start):
    rows = []
    for i in range(n):
        whites = sorted(rng.choice(np.arange(1, era.white_pool + 1), 5, replace=False))
        rows.append({"draw_date": start + timedelta(days=3 * i), "era_id": era.era_id,
                     **{f"n{j + 1}": int(x) for j, x in enumerate(whites)},
                     "special": int(rng.integers(1, era.special_pool + 1)), "multiplier": ""})
    pd.DataFrame(rows).to_csv(path, index=False)


def _fake_numbers_csv(path, n, rng):
    rows = []
    for i in range(n):
        d = rng.integers(0, 10, 3)
        rows.append({"draw_date": date(2000, 1, 1) + timedelta(days=i), "draw_time": "evening",
                     "era_id": "numbers_1980", "number": "".join(map(str, d)),
                     "d1": d[0], "d2": d[1], "d3": d[2]})
    pd.DataFrame(rows).to_csv(path, index=False)


def test_analyze_and_simulation_report_on_fair_synthetic_data(tmp_path):
    rng = np.random.default_rng(11)
    _fake_lotto_csv(tmp_path / "powerball.csv", rules.ERAS["pb_2015"], 600, rng, date(2016, 1, 2))
    _fake_numbers_csv(tmp_path / "ny_numbers.csv", 3000, rng)
    out = stats.analyze(tmp_path)
    sets = {(t["game"], t["ball_set"]) for t in out["tests"]}
    assert sets == {("powerball", "white"), ("powerball", "special"),
                    ("ny_numbers", "digit_1"), ("ny_numbers", "digit_2"),
                    ("ny_numbers", "digit_3"), ("ny_numbers", "number")}
    assert all(t["n_tests"] == 6 for t in out["tests"])
    pb_white = next(f for f in out["frequencies"] if f["ball_set"] == "white")
    assert sum(pb_white["counts"]) == 600 * 5 and len(pb_white["counts"]) == 69
    # numbers keeps leading zeros through the CSV round trip
    num = next(f for f in out["frequencies"] if f["ball_set"] == "number")
    assert sum(num["counts"]) == 3000 and num["labels"][7] == "007"

    rep = stats.simulation_report(tmp_path, histories=200)
    pb = next(r for r in rep if r["game"] == "powerball")
    assert pb["n_draws"] == 1000 and pb["real"]["n_draws"] == 600
    assert 0 <= pb["real"]["spread_percentile"] <= 100
    mm = next(r for r in rep if r["game"] == "mega_millions")
    assert mm["real"] is None  # no data -> simulation only


def test_fair_simulation_properties():
    sim = stats.simulate_fair(rules.current_era("powerball"), 1000, histories=1000, seed=4)
    # every fair history still has 'hot' and 'cold' balls far apart
    assert sim["spread"]["p05"] > 20
    assert sim["p_values"]["share_below_005"] == pytest.approx(0.05, abs=0.02)
    assert abs(sim["persistence"]["mean"]) < 0.02
    assert sum(sim["example"]["counts"]) == 5000
