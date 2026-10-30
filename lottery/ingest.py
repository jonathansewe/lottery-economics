"""Download NY Open Data lottery results and write tidy, era-tagged CSVs to data/.

Datasets (data.ny.gov, Socrata), IDs confirmed from the dataset pages:
  Powerball      d6yy-54nr  https://data.ny.gov/Government-Finance/Lottery-Powerball-Winning-Numbers-Beginning-2010/d6yy-54nr
  Mega Millions  5xaw-6ayf  https://data.ny.gov/Government-Finance/Lottery-Mega-Millions-Winning-Numbers-Beginning-20/5xaw-6ayf
  Numbers/Win-4  hsys-3def  https://data.ny.gov/d/hsys-3def

Usage:
  python -m lottery.ingest                     # download all three, rewrite data/*.csv
  python -m lottery.ingest --games powerball   # just one
  python -m lottery.ingest --from-dir ~/Downloads
      # use files you exported by hand from data.ny.gov ("Export" -> CSV),
      # named powerball.csv, mega_millions.csv, ny_numbers.csv

Re-running is safe: each run rebuilds the CSVs from the full dataset, so the
output only ever reflects the source (no appending, no duplicates).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from . import rules

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

SODA_BASE = "https://data.ny.gov/resource/{id}.json"
DATASETS = {
    "powerball": {"id": "d6yy-54nr", "title": "Lottery Powerball Winning Numbers: Beginning 2010"},
    "mega_millions": {"id": "5xaw-6ayf", "title": "Lottery Mega Millions Winning Numbers: Beginning 2002"},
    "ny_numbers": {"id": "hsys-3def", "title": "Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980"},
}
PAGE = 50_000


class IngestError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def fetch_soda(dataset_id: str, session: requests.Session | None = None,
               retries: int = 4) -> list[dict]:
    """Page through a Socrata dataset. `$order=:id` makes paging stable.

    Set SOCRATA_APP_TOKEN to avoid anonymous rate limits (optional).
    """
    session = session or requests.Session()
    headers = {}
    if os.environ.get("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]
    rows, offset = [], 0
    while True:
        params = {"$limit": PAGE, "$offset": offset, "$order": ":id"}
        for attempt in range(retries + 1):
            try:
                r = session.get(SODA_BASE.format(id=dataset_id), params=params,
                                headers=headers, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == retries:
                    raise IngestError(
                        f"Could not download {dataset_id} from data.ny.gov: {exc}\n"
                        "If you are behind a restrictive network, export the dataset as CSV "
                        "from its data.ny.gov page and use --from-dir.") from exc
                time.sleep(2 ** (attempt + 1))
        page = r.json()
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def normalize_key(key: str) -> str:
    """'Draw Date' -> 'draw_date', 'Midday Daily #' -> 'midday_daily'.

    API field names and CSV-export headers both normalise to the same keys,
    so the parsers below work on either source.
    """
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def load_rows(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)
    df.columns = [normalize_key(c) for c in df.columns]
    return df


def read_export(path: Path) -> pd.DataFrame:
    if path.suffix == ".json":
        return load_rows(json.loads(path.read_text()))
    return load_rows(pd.read_csv(path, dtype=str).to_dict("records"))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_date(value) -> date:
    s = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise IngestError(f"Unrecognised date: {value!r}")


def _ints(text) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", str(text))]


def _require(df: pd.DataFrame, *cols: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise IngestError(f"Missing columns {missing}; got {list(df.columns)}")


def parse_powerball(df: pd.DataFrame) -> pd.DataFrame:
    # winning_numbers holds 6 numbers: 5 white balls then the Powerball.
    _require(df, "draw_date", "winning_numbers")
    out = []
    for _, row in df.iterrows():
        nums = _ints(row["winning_numbers"])
        if len(nums) != 6:
            raise IngestError(f"Powerball {row['draw_date']}: expected 6 numbers, got {nums}")
        out.append({"draw_date": parse_date(row["draw_date"]), "whites": nums[:5], "special": nums[5],
                    "multiplier": _multiplier(row.get("multiplier"))})
    return _wide(out, "powerball")


def parse_mega_millions(df: pd.DataFrame) -> pd.DataFrame:
    # winning_numbers holds the 5 white balls; the Mega Ball is its own column.
    _require(df, "draw_date", "winning_numbers", "mega_ball")
    out = []
    for _, row in df.iterrows():
        nums = _ints(row["winning_numbers"])
        if len(nums) != 5:
            raise IngestError(f"Mega Millions {row['draw_date']}: expected 5 numbers, got {nums}")
        out.append({"draw_date": parse_date(row["draw_date"]), "whites": nums,
                    "special": int(row["mega_ball"]), "multiplier": _multiplier(row.get("multiplier"))})
    return _wide(out, "mega_millions")


def _multiplier(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan"):
        return pd.NA
    return int(_ints(v)[0])


def _wide(records: list[dict], game: str) -> pd.DataFrame:
    rows = []
    for r in records:
        era = rules.era_for(game, r["draw_date"])
        rows.append({
            "draw_date": r["draw_date"],
            "era_id": era.era_id if era else None,
            **{f"n{i + 1}": n for i, n in enumerate(sorted(r["whites"]))},
            "special": r["special"],
            "multiplier": r["multiplier"],
        })
    df = pd.DataFrame(rows).sort_values("draw_date").reset_index(drop=True)
    df["multiplier"] = df["multiplier"].astype("Int64")
    return df


def _numbers_columns(df: pd.DataFrame) -> dict:
    """Find the 3-digit Numbers columns, which the dataset calls 'Daily'.

    Returns {draw_time: column}; Win-4 columns are ignored (out of scope).
    """
    daily = [c for c in df.columns if "daily" in c and "win" not in c]
    found = {}
    for when in ("midday", "evening"):
        cols = [c for c in daily if when in c]
        if cols:
            found[when] = cols[0]
    if not found and len(daily) == 1:
        found["evening"] = daily[0]
    if not found:
        raise IngestError(f"No Numbers ('daily') column found; got {list(df.columns)}")
    return found


def parse_numbers(df: pd.DataFrame) -> pd.DataFrame:
    _require(df, "draw_date")
    cols = _numbers_columns(df)
    rows = []
    for _, row in df.iterrows():
        d = parse_date(row["draw_date"])
        for when, col in cols.items():
            v = row.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan"):
                continue  # e.g. no midday draw in the early years
            digits = re.sub(r"\D", "", str(v).split(".")[0]).zfill(3)
            if len(digits) != 3:
                raise IngestError(f"Numbers {d} {when}: bad value {v!r}")
            rows.append({"draw_date": d, "draw_time": when,
                         "era_id": rules.NUMBERS_ERA.era_id if rules.NUMBERS_ERA.contains(d) else None,
                         "number": digits, "d1": int(digits[0]), "d2": int(digits[1]), "d3": int(digits[2])})
    return pd.DataFrame(rows).sort_values(["draw_date", "draw_time"]).reset_index(drop=True)


PARSERS = {"powerball": parse_powerball, "mega_millions": parse_mega_millions, "ny_numbers": parse_numbers}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate(game: str, df: pd.DataFrame) -> list[str]:
    """Raise on impossible data; return warnings for suspicious-but-possible data.

    The range checks double as a test of the era boundaries in rules.py: if a
    boundary date were wrong, draws from the new matrix (e.g. Mega Ball 25)
    would land in the old era (Mega Ball 1-15) and fail here.
    """
    errors, warnings = [], []
    if df["era_id"].isna().any():
        bad = df.loc[df["era_id"].isna(), "draw_date"].head(5).tolist()
        errors.append(f"draws outside every known era: {bad}")
    key = ["draw_date", "draw_time"] if game == "ny_numbers" else ["draw_date"]
    dups = df[df.duplicated(key, keep=False)]
    if len(dups):
        errors.append(f"duplicate draws: {dups[key].head(5).to_dict('records')}")

    if game != "ny_numbers":
        whites = df[[f"n{i}" for i in range(1, 6)]]
        for era_id, part in df.groupby("era_id"):
            era = rules.ERAS[era_id]
            w = whites.loc[part.index]
            if ((w < 1) | (w > era.white_pool)).any().any():
                errors.append(f"{era_id}: white ball outside 1..{era.white_pool}")
            if (w.nunique(axis=1) != 5).any():
                errors.append(f"{era_id}: repeated white ball within a draw")
            s = part["special"]
            if ((s < 1) | (s > era.special_pool)).any():
                bad = part.loc[(s < 1) | (s > era.special_pool), ["draw_date", "special"]].head(3)
                errors.append(f"{era_id}: special ball outside 1..{era.special_pool}: {bad.to_dict('records')}")
            # With enough draws the top ball should have appeared at least once.
            if len(part) >= 100 and w.max().max() != era.white_pool:
                warnings.append(f"{era_id}: highest white ball {era.white_pool} never drawn in {len(part)} draws")
            if len(part) >= 100 and s.max() != era.special_pool:
                warnings.append(f"{era_id}: highest special ball {era.special_pool} never drawn in {len(part)} draws")
    if errors:
        raise IngestError(f"{game}: " + "; ".join(errors))
    return warnings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def ingest_game(game: str, raw: pd.DataFrame, out_dir: Path = DATA_DIR) -> dict:
    tidy = PARSERS[game](raw)
    warnings = validate(game, tidy)
    out_dir.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(out_dir / f"{game}.csv", index=False)
    return {
        "dataset_id": DATASETS[game]["id"],
        "dataset_title": DATASETS[game]["title"],
        "rows": int(len(tidy)),
        "first_draw": str(tidy["draw_date"].min()),
        "last_draw": str(tidy["draw_date"].max()),
        "draws_per_era": {k: int(v) for k, v in tidy["era_id"].value_counts().sort_index().items()},
        "warnings": warnings,
    }


def run(games=None, from_dir: Path | None = None, out_dir: Path = DATA_DIR) -> dict:
    games = games or list(DATASETS)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for game in games:
        if from_dir:
            src = next((from_dir / f"{game}{ext}" for ext in (".csv", ".json")
                        if (from_dir / f"{game}{ext}").exists()), None)
            if src is None:
                raise IngestError(f"{from_dir} has no {game}.csv or {game}.json")
            raw, origin = read_export(src), str(src)
        else:
            raw, origin = load_rows(fetch_soda(DATASETS[game]["id"])), SODA_BASE.format(id=DATASETS[game]["id"])
        info = ingest_game(game, raw, out_dir)
        info["source"] = origin
        info["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        manifest[game] = info
        print(f"{game}: {info['rows']} draws {info['first_draw']}..{info['last_draw']} {info['draws_per_era']}")
        for w in info["warnings"]:
            print(f"  warning: {w}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", nargs="+", choices=list(DATASETS))
    ap.add_argument("--from-dir", type=Path, help="read hand-exported CSV/JSON files instead of the API")
    args = ap.parse_args(argv)
    try:
        run(args.games, args.from_dir)
    except IngestError as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
