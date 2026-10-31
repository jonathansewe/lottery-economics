"""Estimate tickets sold per draw for jackpot games, two independent ways.

(a) Jackpot growth.  When nobody hits the jackpot, the next draw's *cash* jackpot
    grows by (share of sales funding the jackpot) x (sales). So
        sales ~= (cash_next - cash_now) / share,   tickets = sales / price.
    Needs the share from official game rules. Verified for NY Lotto (40% of sales
    to prizes x 75% to the jackpot = 30%) and Take 5 (50% x 20% = 10%). Not found
    for Powerball / Mega Millions, so method (a) is disabled for them rather than
    run on a guessed constant.
    Caveats: advertised jackpots are forecasts from projected sales; interest and
    rounding move the cash value too.

(b) Winner counts.  Each ticket wins tier i with known probability p_i, so the
    number of winners W_i ~ Poisson(N p_i). The maximum-likelihood estimate of N
    from several tiers at once is
        N_hat = sum(W_i) / sum(p_i)
    with standard error sqrt(sum W_i) / sum(p_i) (Poisson variance = mean).
    Big low tiers (tens of thousands of winners) make this precise.
    Caveat: players don't pick uniformly at random, so a draw of "popular"
    numbers has more winners than average; it averages out over many draws.

Scope: Powerball and Mega Millions winner counts and jackpots are national, so
those estimates are national ticket sales, not New York's. NY Lotto and Take 5
are New York-only games.

Inputs (fill these in once the official sites are reachable; see data/sales/README.md):
  data/sales/jackpots.csv        game,draw_date,jackpot_cash,jackpot_won,source_url
  data/sales/winners.csv         game,draw_date,scope,tier,winners,source_url
  data/sales/official_sales.csv  game,period_start,period_end,scope,sales_dollars,source_url
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from . import rules
from . import math as lm

ROOT = Path(__file__).resolve().parent.parent
SALES_DIR = ROOT / "data" / "sales"

# share of each $ of sales that funds the jackpot: (value or None, verified, source)
JACKPOT_SHARE_OF_SALES = {
    "ny_lotto": (0.40 * 0.75, True, "https://test.nylottery.ny.gov/lotto (40% to prizes; jackpot 75% of that)"),
    "take5": (0.50 * 0.20, True, "https://nylottery.ny.gov/draw-game/?game=take5 (50% to prizes; jackpot 20%)"),
    "powerball": (None, False, "not found in official sources (2026-10-31); method (a) disabled"),
    "mega_millions": (None, False, "not found in official sources (2026-10-31); method (a) disabled"),
}
GAME_SCOPE = {"powerball": "national", "mega_millions": "national", "ny_lotto": "NY", "take5": "NY",
              "millionaire_for_life": "national", "cash4life": "national"}

TEMPLATES = {
    "jackpots.csv": "game,draw_date,jackpot_cash,jackpot_won,source_url\n",
    "winners.csv": "game,draw_date,scope,tier,winners,source_url\n",
    "official_sales.csv": "game,period_start,period_end,scope,sales_dollars,source_url\n",
}


def tier_key(white: int, special) -> str:
    """'3+1', '5+0', or '4' when the special ball doesn't matter."""
    return str(white) if special is None else f"{white}+{special}"


def tier_probabilities(game: str) -> dict[str, float]:
    era = rules.current_era(game)
    return {tier_key(t.white, t.special): float(lm.tier_probability(era, t.white, t.special))
            for t in era.tiers}


# ---------------------------------------------------------------------------
# (a) jackpot growth
# ---------------------------------------------------------------------------
def from_jackpot_growth(game: str, jackpots: pd.DataFrame) -> pd.DataFrame:
    """One estimate per draw that followed a draw with no jackpot winner."""
    share = JACKPOT_SHARE_OF_SALES.get(game, (None,))[0]
    cols = ["game", "draw_date", "method", "scope", "tickets", "ci_low", "ci_high"]
    if share is None:
        return pd.DataFrame(columns=cols)
    price = rules.current_era(game).price
    j = jackpots[jackpots["game"] == game].sort_values("draw_date").reset_index(drop=True)
    out = []
    for prev, cur in zip(j.itertuples(), j.iloc[1:].itertuples()):
        if _truthy(prev.jackpot_won):
            continue  # jackpot reset: growth says nothing about sales
        sales = (cur.jackpot_cash - prev.jackpot_cash) / share
        if sales <= 0:
            continue
        out.append({"game": game, "draw_date": cur.draw_date, "method": "jackpot_growth",
                    "scope": GAME_SCOPE.get(game, "NY"), "tickets": sales / price,
                    "ci_low": None, "ci_high": None})
    return pd.DataFrame(out, columns=cols)


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


# ---------------------------------------------------------------------------
# (b) winner counts
# ---------------------------------------------------------------------------
def pooled_estimate(winners: dict[str, int], probs: dict[str, float]) -> tuple[float, float, float]:
    """MLE of tickets N from Poisson winner counts W_i ~ Poisson(N p_i), with 95% CI."""
    w = sum(winners.values())
    p = sum(probs[k] for k in winners)
    n_hat = w / p
    se = math.sqrt(w) / p
    return n_hat, max(0.0, n_hat - 1.96 * se), n_hat + 1.96 * se


def from_winner_counts(game: str, winners: pd.DataFrame) -> pd.DataFrame:
    """One estimate per (draw, scope). Tiers not in the game's table raise."""
    probs = tier_probabilities(game)
    cols = ["game", "draw_date", "method", "scope", "tickets", "ci_low", "ci_high"]
    w = winners[winners["game"] == game]
    out = []
    for (d, scope), part in w.groupby(["draw_date", "scope"]):
        counts = {str(r.tier): int(r.winners) for r in part.itertuples()}
        unknown = set(counts) - set(probs)
        if unknown:
            raise ValueError(f"{game}: unknown tiers {unknown}; expected {sorted(probs)}")
        if sum(counts.values()) == 0:
            continue
        n, lo, hi = pooled_estimate(counts, probs)
        out.append({"game": game, "draw_date": d, "method": "winner_counts", "scope": scope,
                    "tickets": n, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(out, columns=cols)


# ---------------------------------------------------------------------------
# comparison with official figures
# ---------------------------------------------------------------------------
def compare_with_official(estimates: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Sum per-draw estimates inside each official period (same game, scope and
    method) and report the error against official sales converted to tickets."""
    rows = []
    for o in official.itertuples():
        price = rules.current_era(o.game).price
        official_tickets = o.sales_dollars / price
        mask = ((estimates["game"] == o.game) & (estimates["scope"] == o.scope)
                & (estimates["draw_date"] >= o.period_start) & (estimates["draw_date"] <= o.period_end))
        for method, part in estimates[mask].groupby("method"):
            est = part["tickets"].sum()
            rows.append({"game": o.game, "scope": o.scope, "method": method,
                         "period_start": o.period_start, "period_end": o.period_end,
                         "draws_estimated": int(len(part)), "official_tickets": official_tickets,
                         "estimated_tickets": est,
                         "error_pct": 100 * (est - official_tickets) / official_tickets})
    return pd.DataFrame(rows)


def mape(comparison: pd.DataFrame) -> dict:
    """Mean absolute percentage error per (game, method)."""
    if comparison.empty:
        return {}
    g = comparison.assign(abs_err=comparison["error_pct"].abs()).groupby(["game", "method"])["abs_err"].mean()
    return {f"{game}/{method}": float(v) for (game, method), v in g.items()}


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def ensure_templates(sales_dir: Path = SALES_DIR) -> None:
    sales_dir.mkdir(parents=True, exist_ok=True)
    for name, header in TEMPLATES.items():
        if not (sales_dir / name).exists():
            (sales_dir / name).write_text(header)


def _read(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path) if path.exists() else pd.DataFrame()
    for c in ("draw_date", "period_start", "period_end"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c]).dt.date.astype(str)
    return df


def report(sales_dir: Path = SALES_DIR) -> dict:
    """Everything the site's sales chart needs. Empty inputs -> available False."""
    jackpots = _read(sales_dir / "jackpots.csv")
    winners = _read(sales_dir / "winners.csv")
    official = _read(sales_dir / "official_sales.csv")
    parts = []
    for game in JACKPOT_SHARE_OF_SALES:
        if not jackpots.empty:
            parts.append(from_jackpot_growth(game, jackpots))
        if not winners.empty and game in set(winners["game"]):
            parts.append(from_winner_counts(game, winners))
    parts = [p for p in parts if not p.empty]
    est = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["game", "draw_date", "method", "scope", "tickets", "ci_low", "ci_high"])
    comp = compare_with_official(est, official) if not official.empty and not est.empty else pd.DataFrame()
    return {
        "available": not est.empty,
        "shares": {g: {"share": v[0], "verified": v[1], "source": v[2]} for g, v in JACKPOT_SHARE_OF_SALES.items()},
        "scope": GAME_SCOPE,
        "estimates": est.astype(object).where(est.notna(), None).to_dict("records"),
        "comparisons": comp.to_dict("records") if not comp.empty else [],
        "mape": mape(comp),
        "official_available": not official.empty,
    }
