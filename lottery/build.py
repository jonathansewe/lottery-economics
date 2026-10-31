"""Precompute everything the website shows into docs/data/*.json.

  python -m lottery.build                 # use whatever is in data/ (may be empty)
  python -m lottery.build --ingest        # download fresh data first, then build
  python -m lottery.build --from-dir DIR  # ingest hand-exported files, then build

The site is static: it only ever reads these JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config, export, ingest, rules, sales, states, stats
from . import math as lm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"

# Illustrative scenarios for the EV tables (ticket sales are an assumption, see config.py).
BIG_JACKPOT = 1_000_000_000
BIG_JACKPOT_TICKETS = 200_000_000


def _era_meta(era: rules.Era) -> dict:
    return {
        "era_id": era.era_id, "label": era.label, "matrix": era.matrix, "kind": era.kind,
        "first_draw": str(era.first_draw), "last_draw": str(era.last_draw) if era.last_draw else None,
        "white_pool": era.white_pool, "white_drawn": era.white_drawn, "special_pool": era.special_pool,
        "bonus": era.bonus, "price": era.price, "plays_per_dollar": era.plays_per_dollar,
        "prize_pool_fraction": era.prize_pool_fraction,
        "has_prize_table": bool(era.tiers or era.plays or era.spot_tables),
        "starting_jackpot": era.starting_jackpot,
        "verified": era.verified, "unverified": list(era.unverified),
        "sources": list(era.sources), "notes": era.notes,
    }


def _jsonable(rows):
    return [{k: (float(v) if k == "probability" else v) for k, v in r.items()} for r in rows]


def _odds_payload(era: rules.Era) -> dict:
    out = {key: _jsonable(rows) for key, rows in lm.odds_rows(era).items()}
    if era.kind == "lotto":
        out["overall_one_in"] = float(1 / lm.overall_probability(era))
        out["official_overall_one_in"] = era.official_overall_odds
        out["multiplier"] = [[f, q] for f, q in era.multiplier.items()]
        for r in out["tiers"]:
            if r["prize"] == rules.PARIMUTUEL:
                t = next(t for t in era.tiers if (t.white, t.special) == (r["white"], r["special"]))
                r["typical_prize"] = lm.typical_parimutuel_prize(era, t)
    if era.kind == "keno":
        out["official_overall"] = {f"{k}-spot": v for k, v in era.spot_overall.items()}
        out["overall"] = {key: 1 / sum(r["probability"] for r in rows)
                          for key, rows in out.items() if key.endswith("-spot")}
    return out


def games_json() -> dict:
    out = {}
    for game, eras in rules.GAMES.items():
        cur = rules.current_era(game)
        entry = {"label": rules.GAME_LABELS[game], "kind": cur.kind, "retired": game in rules.RETIRED,
                 "eras": [_era_meta(e) for e in eras], "current_era": cur.era_id,
                 "odds": {e.era_id: _odds_payload(e) for e in eras if e.tiers or e.plays or e.spot_tables}}
        if game not in ("powerball", "mega_millions"):
            entry["ev"] = {mode: lm.game_ev(cur, mode) for mode in config.TAX_MODES}
        if game == "ny_numbers":  # kept for the v1 page code
            entry["plays"] = _jsonable(lm.numbers_odds())
        out[game] = entry
    return out


def ev_json() -> dict:
    tax = {k: {"rate": v["rate"], "verified": v["verified"]} for k, v in config.TAX.items()}
    withholding = {k: {"rate": v["rate"], "verified": v["verified"]} for k, v in config.WITHHOLDING.items()}
    out = {"tax": tax, "withholding": withholding, "withholding_threshold": config.WITHHOLDING_THRESHOLD,
           "combined_tax_rate": config.combined_tax_rate(),
           "tax_modes": {m: dict(zip(("rate", "threshold"), config.tax_params(m))) for m in config.TAX_MODES},
           "tickets_scenarios": config.TICKETS_SOLD_SCENARIOS, "games": {}}
    for game in ("powerball", "mega_millions"):
        era = rules.current_era(game)
        ref = lm.ev_breakdown(era, era.starting_jackpot, tickets_sold=config.REFERENCE_TICKETS_SOLD)
        big = lm.ev_breakdown(era, BIG_JACKPOT, tickets_sold=BIG_JACKPOT_TICKETS)
        split_grid = [{"tickets": n, "p_shared": lm.p_shared(lm.jackpot_probability(era), n),
                       "expected_share": lm.expected_share(lm.jackpot_probability(era), n)}
                      for n in config.TICKETS_SOLD_SCENARIOS]
        out["games"][game] = {
            "label": rules.GAME_LABELS[game], "era_id": era.era_id, "price": era.price,
            "cash_ratio": config.CASH_RATIO[game], "starting_jackpot": era.starting_jackpot,
            # inputs for the in-browser calculator (docs/js/ev.js mirrors lottery/math.py)
            "tiers": [{"white": t.white, "special": t.special, "prize": t.prize,
                       "probability": float(lm.tier_probability(era, t.white, t.special))} for t in era.tiers],
            "multiplier": [[f, q] for f, q in (era.multiplier or {1: 1.0}).items()],
            "reference": {"jackpot": era.starting_jackpot, "tickets": config.REFERENCE_TICKETS_SOLD, **ref},
            "big": {"jackpot": BIG_JACKPOT, "tickets": BIG_JACKPOT_TICKETS, **big},
            "split_grid": split_grid,
            "reference_withholding": lm.ev_breakdown(era, era.starting_jackpot, tax_mode="withholding",
                                                     tickets_sold=config.REFERENCE_TICKETS_SOLD),
            "break_even": {
                "cash_pre_tax": lm.break_even_jackpot(era),
                "cash_after_tax": lm.break_even_jackpot(era, tax_rate=config.combined_tax_rate()),
                "cash_after_withholding": lm.break_even_jackpot(
                    era, tax_rate=config.tax_params("withholding")[0],
                    threshold=config.tax_params("withholding")[1]),
            },
        }
    out["numbers"] = lm.numbers_ev()
    out["headline"] = {
        "powerball": out["games"]["powerball"]["reference"]["with_split"]["total_per_dollar"],
        "mega_millions": out["games"]["mega_millions"]["reference"]["with_split"]["total_per_dollar"],
        "ny_numbers": max(r["after_tax_per_dollar"] for r in out["numbers"]),
    }
    return out


def stats_json(data_dir: Path) -> dict:
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    res = stats.analyze(data_dir)
    return {"data_available": bool(res["tests"]), "manifest": manifest,
            "alpha": stats.ALPHA, **res}


FINDINGS_START, FINDINGS_END = "<!-- findings:start -->", "<!-- findings:end -->"


def findings_markdown(stats_payload: dict, sims: list[dict]) -> str:
    """Plain-English summary of the real-data results, regenerated on every build."""
    if not stats_payload["data_available"]:
        return ("*Real-data results are pending: the draw history has not been ingested in this "
                "build. Run `python -m lottery.build --ingest` and this section rewrites itself.*")
    tests = stats_payload["tests"]
    n = len(tests)
    flagged = [t for t in tests if t["significant"]]
    low = min(tests, key=lambda t: t["p_value"])
    lines = [
        f"- **Fairness tests:** {n} chi-square tests (every game, rule era and ball set, never pooled). "
        f"Bonferroni threshold: p < {stats.ALPHA}/{n} = {stats.ALPHA / n:.2g}. "
        + ("**None** fall below it: the draws are consistent with every ball being equally likely."
           if not flagged else
           f"**{len(flagged)}** fall below it: "
           + ", ".join(f"{t['era_label']} {t['ball_set']} (p = {t['p_value']:.2g})" for t in flagged)
           + ". See the notebook before reading anything into this."),
        f"- Smallest raw p-value: {low['p_value']:.3g} ({low['era_label']}, {low['ball_set']}). "
        f"With {n} tests, the smallest p is expected to be around 1/{n + 1} ≈ {1 / (n + 1):.2f} by chance alone.",
    ]
    for s in sims:
        r = s.get("real")
        if not r:
            continue
        lo, hi = r["fair_persistence_p05_p95"]
        lines.append(
            f"- **{s['era_label']}, {r['n_draws']} draws:** the gap between the most and least drawn white "
            f"ball is {r['spread']}, at the {r['spread_percentile']:.0f}th percentile of fair simulated histories. "
            f"Half-to-half rank correlation of ball counts is {r['persistence']:.3f} (fair 90% range "
            f"{lo:.2f} to {hi:.2f}): the hottest balls of the first half were not hotter in the second "
            f"({r['first_half_hot_second_half_avg']:.1f} draws vs {r['second_half_expected']:.1f} expected).")
    return "\n".join(lines)


def write_findings(readme: Path, text: str) -> None:
    if not readme.exists():
        return
    body = readme.read_text()
    if FINDINGS_START not in body:
        return
    head, rest = body.split(FINDINGS_START, 1)
    _, tail = rest.split(FINDINGS_END, 1)
    readme.write_text(f"{head}{FINDINGS_START}\n{text}\n{FINDINGS_END}{tail}")


def build(out_dir: Path = OUT, data_dir: Path = stats.DATA_DIR, histories: int = 1000,
          readme: Path | None = ROOT / "README.md") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "games.json": games_json(),
        "ev.json": ev_json(),
        "stats.json": stats_json(data_dir),
        "simulation.json": {"simulations": stats.simulation_report(data_dir, histories)},
        "states.json": {"jurisdictions": states.jurisdictions()},
        "sales.json": sales.report(),
    }
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for name, payload in payloads.items():
        payload["generated_at"] = stamp
        (out_dir / name).write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
        print(f"wrote {out_dir / name}")
    draws_index = export.export_draws(data_dir, out_dir / "draws")
    print(f"wrote {out_dir / 'draws'} ({sum(len(g['files']) for g in draws_index.values())} draw files)")
    if readme is not None:
        write_findings(readme, findings_markdown(payloads["stats.json"], payloads["simulation.json"]["simulations"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ingest", action="store_true", help="download data from data.ny.gov first")
    ap.add_argument("--from-dir", type=Path, help="ingest hand-exported files from this folder first")
    args = ap.parse_args(argv)
    if args.ingest or args.from_dir:
        try:
            ingest.run(from_dir=args.from_dir)
        except ingest.IngestError as exc:
            print(f"ingest failed: {exc}", file=sys.stderr)
            return 1
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
