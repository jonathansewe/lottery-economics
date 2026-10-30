"""Frequency counts, goodness-of-fit tests and fair-draw simulations.

Null hypothesis for every test: each draw is a uniformly random draw from the
era's ball pool. We never pool eras (different pools = different nulls).

The chi-square correction
-------------------------
Pearson's chi-square assumes each observation lands in one cell independently
(multinomial). A Powerball draw puts 5 *distinct* balls in 5 cells, so cell
counts are slightly negatively correlated. For k of m without replacement:

    Cov(counts) = (m-k)/(m-1) * Cov(multinomial with the same expected counts)

so the plain statistic X^2 is (m-k)/(m-1) times "too small", and
X^2 * (m-1)/(m-k) ~ chi-square(m-1). For k=1 (Powerball/Mega Ball/digits) the
factor is 1. `chi_square` applies it; `monte_carlo_p` checks it by brute force.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from . import rules

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ALPHA = 0.05
WHITE_COLS = [f"n{i}" for i in range(1, 6)]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_draws(game: str, data_dir: Path = DATA_DIR) -> pd.DataFrame | None:
    path = data_dir / f"{game}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, dtype={"number": str})
    df["draw_date"] = pd.to_datetime(df["draw_date"]).dt.date
    return df


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------
def ball_sets(game: str, df: pd.DataFrame):
    """Yield (era, ball_set_name, labels, counts, n_draws, k, m) for every test.

    labels are the ball numbers (or digit/number strings) in display order.
    """
    for era_id, part in df.groupby("era_id", sort=False):
        era = rules.ERAS[era_id]
        n = len(part)
        if game == "ny_numbers":
            for pos in (1, 2, 3):
                counts = np.bincount(part[f"d{pos}"].to_numpy(int), minlength=10)
                yield era, f"digit_{pos}", list(range(10)), counts, n, 1, 10
            idx = part["number"].astype(int).to_numpy()
            yield era, "number", [f"{i:03d}" for i in range(1000)], np.bincount(idx, minlength=1000), n, 1, 1000
        else:
            whites = part[WHITE_COLS].to_numpy(int).ravel()
            yield (era, "white", list(range(1, era.white_pool + 1)),
                   np.bincount(whites, minlength=era.white_pool + 1)[1:], n, era.white_drawn, era.white_pool)
            yield (era, "special", list(range(1, era.special_pool + 1)),
                   np.bincount(part["special"].to_numpy(int), minlength=era.special_pool + 1)[1:],
                   n, 1, era.special_pool)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def chi_square(counts, n_draws: int, k: int, m: int) -> dict:
    counts = np.asarray(counts, dtype=float)
    expected = n_draws * k / m
    raw = float(((counts - expected) ** 2 / expected).sum())
    factor = (m - 1) / (m - k)
    stat = raw * factor
    df = m - 1
    return {
        "statistic_raw": raw,
        "correction_factor": factor,
        "statistic": stat,
        "df": df,
        "p_value": float(sps.chi2.sf(stat, df)),
        "expected_per_cell": expected,
        "min_expected_ok": expected >= 5,  # usual rule of thumb for the chi-square approximation
    }


def simulate_counts(n_draws: int, k: int, m: int, rng: np.random.Generator) -> np.ndarray:
    """Counts per ball from n fair draws of k distinct balls out of m."""
    if k == 1:
        return rng.multinomial(n_draws, np.full(m, 1 / m))
    picks = rng.random((n_draws, m)).argpartition(k, axis=1)[:, :k]
    return np.bincount(picks.ravel(), minlength=m)


def monte_carlo_p(counts, n_draws: int, k: int, m: int, sims: int = 2000, seed: int = 0) -> float:
    """P-value with no distributional assumption: how often does fair data look
    at least this uneven?  (1 + #hits) / (1 + sims) is the standard unbiased form."""
    rng = np.random.default_rng(seed)
    obs = chi_square(counts, n_draws, k, m)["statistic_raw"]
    hits = sum(chi_square(simulate_counts(n_draws, k, m, rng), n_draws, k, m)["statistic_raw"] >= obs
               for _ in range(sims))
    return (1 + hits) / (1 + sims)


def bonferroni(results: list[dict], alpha: float = ALPHA) -> list[dict]:
    """With T tests, require p < alpha/T for any single one. This caps the chance
    of *any* false alarm at alpha, which matters: run 20 fair tests at 0.05 and
    you expect one 'significant' result by luck alone."""
    t = len(results)
    for r in results:
        r["n_tests"] = t
        r["alpha_bonferroni"] = alpha / t
        r["p_bonferroni"] = min(1.0, r["p_value"] * t)
        r["significant"] = r["p_value"] < alpha / t
    return results


def binomial_band(n_draws: int, k: int, m: int, level: float = 0.95) -> tuple[int, int]:
    """Range a single ball's count falls in with prob `level` under fairness.
    Each ball is in a draw with prob k/m, so its count ~ Binomial(n, k/m)."""
    lo = sps.binom.ppf((1 - level) / 2, n_draws, k / m)
    hi = sps.binom.ppf(1 - (1 - level) / 2, n_draws, k / m)
    return int(lo), int(hi)


def analyze(data_dir: Path = DATA_DIR) -> dict:
    """Frequencies + chi-square for every game/era/ball set with data present."""
    freq, tests = [], []
    for game in rules.GAMES:
        df = load_draws(game, data_dir)
        if df is None or df.empty:
            continue
        for era, name, labels, counts, n, k, m in ball_sets(game, df):
            res = chi_square(counts, n, k, m)
            lo, hi = binomial_band(n, k, m)
            outside = int(((counts < lo) | (counts > hi)).sum())
            freq.append({
                "game": game, "era_id": era.era_id, "era_label": era.label, "ball_set": name,
                "n_draws": int(n), "first_draw": str(min(df.loc[df.era_id == era.era_id, "draw_date"])),
                "last_draw": str(max(df.loc[df.era_id == era.era_id, "draw_date"])),
                "labels": labels, "counts": counts.tolist(), "expected": n * k / m,
                "band95": [lo, hi], "outside_band": outside, "expected_outside": round(0.05 * m, 1),
            })
            tests.append({"game": game, "era_id": era.era_id, "era_label": era.label,
                          "ball_set": name, "n_draws": int(n), **res})
    return {"frequencies": freq, "tests": bonferroni(tests)}


# ---------------------------------------------------------------------------
# Simulation: what "hot" and "cold" look like in perfectly fair data
# ---------------------------------------------------------------------------
def _spearman(a, b) -> float:
    return float(sps.spearmanr(a, b).statistic)


def hot_cold(counts, labels, n: int = 5) -> dict:
    order = np.argsort(counts, kind="stable")
    return {"hot": [labels[i] for i in order[::-1][:n]], "cold": [labels[i] for i in order[:n]]}


def simulate_fair(era: rules.Era, n_draws: int, histories: int = 1000, seed: int = 2026) -> dict:
    """One fair history of `n_draws` draws, plus `histories` independent ones.

    Reports, for fair data:
      - spread: max count - min count across white balls (how 'hot vs cold' it looks)
      - p-values of the chi-square test (should be ~uniform: ~5% below 0.05)
      - persistence: Spearman correlation between first-half and second-half
        counts. If hot numbers stayed hot this would be > 0; for fair draws it's ~0.
    """
    rng = np.random.default_rng(seed)
    m, k = era.white_pool, era.white_drawn
    labels = list(range(1, m + 1))
    one = simulate_counts(n_draws, k, m, rng)
    spreads, pvals, persist = [], [], []
    h1, h2 = n_draws // 2, n_draws - n_draws // 2
    for _ in range(histories):
        a, b = simulate_counts(h1, k, m, rng), simulate_counts(h2, k, m, rng)
        c = a + b
        spreads.append(int(c.max() - c.min()))
        pvals.append(chi_square(c, n_draws, k, m)["p_value"])
        persist.append(_spearman(a, b))
    spreads, pvals, persist = map(np.asarray, (spreads, pvals, persist))
    return {
        "era_id": era.era_id, "era_label": era.label, "n_draws": n_draws, "histories": histories,
        "seed": seed, "expected": n_draws * k / m, "band95": list(binomial_band(n_draws, k, m)),
        "example": {"labels": labels, "counts": one.tolist(), **hot_cold(one, labels),
                    "spread": int(one.max() - one.min()),
                    "p_value": chi_square(one, n_draws, k, m)["p_value"]},
        "spread": {"values_hist": np.bincount(spreads).tolist(),
                   "p05": float(np.percentile(spreads, 5)), "median": float(np.median(spreads)),
                   "p95": float(np.percentile(spreads, 95))},
        "p_values": {"hist10": np.histogram(pvals, bins=10, range=(0, 1))[0].tolist(),
                     "share_below_005": float((pvals < 0.05).mean())},
        "persistence": {"mean": float(persist.mean()), "p05": float(np.percentile(persist, 5)),
                        "p95": float(np.percentile(persist, 95)),
                        "hist": np.histogram(persist, bins=20, range=(-1, 1))[0].tolist()},
    }


def real_vs_simulation(df: pd.DataFrame, sim: dict) -> dict:
    """Put the real data's spread and half-to-half persistence inside the fair distribution."""
    part = df[df["era_id"] == sim["era_id"]].sort_values("draw_date")
    era = rules.ERAS[sim["era_id"]]
    m = era.white_pool
    half = len(part) // 2

    def counts(p):
        return np.bincount(p[WHITE_COLS].to_numpy(int).ravel(), minlength=m + 1)[1:]

    c, a, b = counts(part), counts(part.iloc[:half]), counts(part.iloc[half:])
    rho = _spearman(a, b)
    hist = np.asarray(sim["spread"]["values_hist"])
    spread = int(c.max() - c.min())
    return {
        "n_draws": int(len(part)),
        "spread": spread,
        "spread_percentile": float(hist[:spread + 1].sum() / hist.sum() * 100),
        "persistence": rho,
        "first_half_hot": hot_cold(a, list(range(1, m + 1)), 10)["hot"],
        "first_half_hot_second_half_avg": float(np.mean([b[i - 1] for i in hot_cold(a, list(range(1, m + 1)), 10)["hot"]])),
        "second_half_expected": (len(part) - half) * era.white_drawn / m,
    }


def simulation_report(data_dir: Path = DATA_DIR, histories: int = 1000) -> list[dict]:
    """Simulations for the current Powerball and Mega Millions eras. Uses the real
    number of draws when data exists (so the comparison is like-for-like), else 1,000."""
    out = []
    for game in ("powerball", "mega_millions"):
        era = rules.current_era(game)
        df = load_draws(game, data_dir)
        n_real = int((df["era_id"] == era.era_id).sum()) if df is not None else 0
        sim = simulate_fair(era, max(1000, n_real), histories)
        sim["game"] = game
        sim["real"] = None
        if n_real >= 50:
            # compare like-for-like: re-run the ensemble at the real sample size
            sim_real_n = simulate_fair(era, n_real, histories, seed=7)
            sim["real"] = real_vs_simulation(df, sim_real_n)
            sim["real"]["fair_spread_p05_p95"] = [sim_real_n["spread"]["p05"], sim_real_n["spread"]["p95"]]
            sim["real"]["fair_persistence_p05_p95"] = [sim_real_n["persistence"]["p05"],
                                                       sim_real_n["persistence"]["p95"]]
            # the histograms the real data is plotted against (same number of draws)
            sim["real_ensemble"] = {"n_draws": n_real, "spread": sim_real_n["spread"],
                                    "persistence": sim_real_n["persistence"]}
        out.append(sim)
    return out
