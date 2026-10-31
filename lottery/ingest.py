"""Download NY Open Data lottery results and write tidy, era-tagged CSVs to data/.

Datasets (data.ny.gov, Socrata). IDs come from the dataset pages (seen via search);
None = not found yet (TODO), and that game is skipped with a message.

  Powerball             d6yy-54nr  Lottery Powerball Winning Numbers: Beginning 2010
  Mega Millions         5xaw-6ayf  Lottery Mega Millions Winning Numbers: Beginning 2002
  Numbers + Win 4       hsys-3def  Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980
  NY Lotto              6nbc-h7bj  Lottery NY Lotto Winning Numbers: Beginning 2001
  Take 5                dg63-4siq  Lottery Take 5 Winning Numbers: Beginning 1992
  Pick 10               bycu-cw7c  Lottery Pick 10 Winning Numbers: Beginning 1987
  Quick Draw            7sqk-ycpk  Lottery Quick Draw Winning Numbers: Beginning 2013
  Cash4Life             kwxv-fwze  Lottery Cash 4 Life Winning Numbers: 2014 - 2026 (Retired Game)
  Millionaire for Life  TODO       (no dataset found as of 2026-10-31)

Column names for the newer datasets were not visible from the build machine, so
the parsers locate columns by normalised name (e.g. "Bonus #" -> "bonus") and fail
loudly with the columns they did find. Check them on the first real run.

Usage:
  python -m lottery.ingest                      # download everything, rewrite data/
  python -m lottery.ingest --games take5 pick10 # some games only
  python -m lottery.ingest --qd-since 2024      # Quick Draw from 2024 on (it is huge)
  python -m lottery.ingest --from-dir ~/Downloads
      # files exported by hand from data.ny.gov, named <game>.csv or <game>.json

Re-running is safe: each run rebuilds a game's files from the full source.
Quick Draw is stored per year (data/quick_draw/<year>.csv.gz); every other game
in one file (data/<game>.csv). No output file may exceed MAX_FILE_BYTES.
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
MAX_FILE_BYTES = 50 * 1024 * 1024   # never write (and so never commit) a file over 50 MB

SODA_BASE = "https://data.ny.gov/resource/{id}.json"
DATASETS = {
    "powerball": {"id": "d6yy-54nr", "title": "Lottery Powerball Winning Numbers: Beginning 2010"},
    "mega_millions": {"id": "5xaw-6ayf", "title": "Lottery Mega Millions Winning Numbers: Beginning 2002"},
    "ny_numbers": {"id": "hsys-3def", "title": "Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980"},
    "win4": {"id": "hsys-3def", "title": "Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980"},
    "ny_lotto": {"id": "6nbc-h7bj", "title": "Lottery NY Lotto Winning Numbers: Beginning 2001"},
    "take5": {"id": "dg63-4siq", "title": "Lottery Take 5 Winning Numbers: Beginning 1992"},
    "pick10": {"id": "bycu-cw7c", "title": "Lottery Pick 10 Winning Numbers: Beginning 1987"},
    "quick_draw": {"id": "7sqk-ycpk", "title": "Lottery Quick Draw Winning Numbers: Beginning 2013"},
    "cash4life": {"id": "kwxv-fwze", "title": "Lottery Cash 4 Life Winning Numbers: 2014 - 2026 (Retired Game)"},
    "millionaire_for_life": {"id": None, "title": "TODO: dataset not found on data.ny.gov yet"},
}
PAGE = 50_000


class IngestError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def fetch_soda(dataset_id: str, session: requests.Session | None = None,
               retries: int = 4, where: str | None = None) -> list[dict]:
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
        if where:
            params["$where"] = where
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
# Parsing helpers
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


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan")


def _require(df: pd.DataFrame, *cols: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise IngestError(f"Missing columns {missing}; got {list(df.columns)}")


def _find(df: pd.DataFrame, *must: str, exclude: tuple = ()) -> str | None:
    """First column whose name contains every word in `must` and none in `exclude`."""
    for c in df.columns:
        if all(w in c for w in must) and not any(w in c for w in exclude):
            return c
    return None


def _multiplier(v):
    if _blank(v):
        return pd.NA
    return int(_ints(v)[0])


# ---------------------------------------------------------------------------
# Lotto-style games (k distinct numbers, optional special/bonus ball)
# ---------------------------------------------------------------------------
def _wide(records: list[dict], game: str) -> pd.DataFrame:
    rows = []
    for r in records:
        era = rules.era_for(game, r["draw_date"])
        row = {"draw_date": r["draw_date"]}
        for extra in ("draw_time", "draw_number"):
            if extra in r:
                row[extra] = r[extra]
        row["era_id"] = era.era_id if era else None
        row.update({f"n{i + 1}": n for i, n in enumerate(sorted(r["whites"]))})
        if "special" in r:
            row["special"] = r["special"]
        if "multiplier" in r:
            row["multiplier"] = r["multiplier"]
        rows.append(row)
    df = pd.DataFrame(rows)
    sort = [c for c in ("draw_date", "draw_time", "draw_number") if c in df.columns]
    df = df.sort_values(sort).reset_index(drop=True)
    if "multiplier" in df.columns:
        df["multiplier"] = df["multiplier"].astype("Int64")
    return df


def parse_lotto(df: pd.DataFrame, game: str, k: int, special_col: str | None = None,
                special_in_numbers: bool = False, keep_multiplier: bool = False) -> pd.DataFrame:
    """Generic parser: `winning_numbers` holds k numbers (k+1 if the special ball is
    appended to it), or the special ball is in `special_col`."""
    _require(df, "draw_date", "winning_numbers")
    out = []
    for _, row in df.iterrows():
        nums = _ints(row["winning_numbers"])
        expected = k + 1 if special_in_numbers else k
        if len(nums) != expected:
            raise IngestError(f"{game} {row['draw_date']}: expected {expected} numbers, got {nums}")
        rec = {"draw_date": parse_date(row["draw_date"]), "whites": nums[:k]}
        if special_in_numbers:
            rec["special"] = nums[k]
        elif special_col:
            if _blank(row.get(special_col)):
                raise IngestError(f"{game} {row['draw_date']}: missing {special_col}")
            rec["special"] = int(_ints(row[special_col])[0])
        if keep_multiplier:
            rec["multiplier"] = _multiplier(row.get("multiplier"))
        out.append(rec)
    return _wide(out, game)


def parse_powerball(df: pd.DataFrame) -> pd.DataFrame:
    # winning_numbers holds 6 numbers: 5 white balls then the Powerball.
    return parse_lotto(df, "powerball", 5, special_in_numbers=True, keep_multiplier=True)


def parse_mega_millions(df: pd.DataFrame) -> pd.DataFrame:
    # winning_numbers holds the 5 white balls; the Mega Ball is its own column.
    _require(df, "draw_date", "winning_numbers", "mega_ball")
    return parse_lotto(df, "mega_millions", 5, special_col="mega_ball", keep_multiplier=True)


def parse_ny_lotto(df: pd.DataFrame) -> pd.DataFrame:
    # "Draw Date, Winning Numbers, Bonus #, Extra #" (Extra only 2007-2010; ignored).
    bonus = _find(df, "bonus")
    if bonus is None:
        raise IngestError(f"NY Lotto: no bonus column; got {list(df.columns)}")
    return parse_lotto(df, "ny_lotto", 6, special_col=bonus)


def parse_cash4life(df: pd.DataFrame) -> pd.DataFrame:
    col = _find(df, "cash", "ball")
    if col is None:
        raise IngestError(f"Cash4Life: no Cash Ball column; got {list(df.columns)}")
    return parse_lotto(df, "cash4life", 5, special_col=col)


def parse_millionaire_for_life(df: pd.DataFrame) -> pd.DataFrame:
    col = _find(df, "millionaire", "ball") or _find(df, "ball", exclude=("winning",))
    if col is not None:
        return parse_lotto(df, "millionaire_for_life", 5, special_col=col)
    return parse_lotto(df, "millionaire_for_life", 5, special_in_numbers=True)


def parse_take5(df: pd.DataFrame) -> pd.DataFrame:
    """Take 5 is drawn twice a day. Accepts either one 'winning_numbers' column (with
    an optional draw-time column) or separate midday/evening number columns."""
    _require(df, "draw_date")
    cols = {when: _find(df, when, "winning") or _find(df, when, "number")
            for when in ("midday", "evening")}
    cols = {k: v for k, v in cols.items() if v}
    out = []
    if cols:
        for _, row in df.iterrows():
            for when, col in cols.items():
                if _blank(row.get(col)):
                    continue  # e.g. no midday draw in the early years: never filled in
                out.append({"draw_date": parse_date(row["draw_date"]), "draw_time": when,
                            "whites": _ints(row[col])})
    else:
        _require(df, "winning_numbers")
        tcol = _find(df, "draw", "time")
        for _, row in df.iterrows():
            out.append({"draw_date": parse_date(row["draw_date"]),
                        "draw_time": str(row[tcol]).strip().lower() if tcol else "evening",
                        "whites": _ints(row["winning_numbers"])})
    for r in out:
        if len(r["whites"]) != 5:
            raise IngestError(f"take5 {r['draw_date']} {r['draw_time']}: expected 5 numbers, got {r['whites']}")
    return _wide(out, "take5")


def _keno(df: pd.DataFrame, game: str) -> pd.DataFrame:
    _require(df, "draw_date", "winning_numbers")
    num_col, time_col = _find(df, "draw", "number"), _find(df, "draw", "time")
    out = []
    for _, row in df.iterrows():
        nums = _ints(row["winning_numbers"])
        if len(nums) != 20:
            raise IngestError(f"{game} {row['draw_date']}: expected 20 numbers, got {len(nums)}")
        rec = {"draw_date": parse_date(row["draw_date"]), "whites": nums}
        if num_col:
            rec["draw_number"] = int(_ints(row[num_col])[0])
        if time_col:
            rec["draw_time"] = str(row[time_col]).strip()
        out.append(rec)
    return _wide(out, game)


def parse_pick10(df: pd.DataFrame) -> pd.DataFrame:
    return _keno(df, "pick10")


def parse_quick_draw(df: pd.DataFrame) -> pd.DataFrame:
    return _keno(df, "quick_draw")


# ---------------------------------------------------------------------------
# Digit games (Numbers = 3 digits, Win 4 = 4 digits), same source dataset
# ---------------------------------------------------------------------------
def _digit_columns(df: pd.DataFrame, game: str) -> dict:
    """{draw_time: column}. The dataset calls Numbers 'Daily' and Win 4 'Win 4'."""
    if game == "ny_numbers":
        cand = [c for c in df.columns if "daily" in c and "win" not in c]
    else:
        cand = [c for c in df.columns if "win_4" in c or "win4" in c]
    found = {when: next(c for c in cand if when in c)
             for when in ("midday", "evening") if any(when in c for c in cand)}
    if not found and len(cand) == 1:
        found["evening"] = cand[0]
    if not found:
        raise IngestError(f"No {game} column found; got {list(df.columns)}")
    return found


def _parse_digits(df: pd.DataFrame, game: str, n: int) -> pd.DataFrame:
    _require(df, "draw_date")
    era = rules.current_era(game)
    rows = []
    for _, row in df.iterrows():
        d = parse_date(row["draw_date"])
        for when, col in _digit_columns(df, game).items():
            v = row.get(col)
            if _blank(v):
                continue  # no draw recorded: left out, never filled in
            digits = re.sub(r"\D", "", str(v).split(".")[0]).zfill(n)
            if len(digits) != n:
                raise IngestError(f"{game} {d} {when}: bad value {v!r}")
            rows.append({"draw_date": d, "draw_time": when,
                         "era_id": era.era_id if era.contains(d) else None,
                         "number": digits, **{f"d{i + 1}": int(digits[i]) for i in range(n)}})
    return pd.DataFrame(rows).sort_values(["draw_date", "draw_time"]).reset_index(drop=True)


def _numbers_columns(df: pd.DataFrame) -> dict:
    return _digit_columns(df, "ny_numbers")


def parse_numbers(df: pd.DataFrame) -> pd.DataFrame:
    return _parse_digits(df, "ny_numbers", 3)


def parse_win4(df: pd.DataFrame) -> pd.DataFrame:
    return _parse_digits(df, "win4", 4)


PARSERS = {
    "powerball": parse_powerball, "mega_millions": parse_mega_millions, "ny_numbers": parse_numbers,
    "win4": parse_win4, "ny_lotto": parse_ny_lotto, "take5": parse_take5, "pick10": parse_pick10,
    "quick_draw": parse_quick_draw, "cash4life": parse_cash4life,
    "millionaire_for_life": parse_millionaire_for_life,
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def white_cols(df: pd.DataFrame) -> list[str]:
    return sorted((c for c in df.columns if re.fullmatch(r"n\d+", c)), key=lambda c: int(c[1:]))


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
    key = [c for c in ("draw_date", "draw_time", "draw_number") if c in df.columns]
    dups = df[df.duplicated(key, keep=False)]
    if len(dups):
        errors.append(f"duplicate draws: {dups[key].head(5).to_dict('records')}")

    if rules.current_era(game).kind != "digits":
        cols = white_cols(df)
        for era_id, part in df.dropna(subset=["era_id"]).groupby("era_id"):
            era = rules.ERAS[era_id]
            w = part[cols]
            if len(cols) != era.white_drawn:
                errors.append(f"{era_id}: {len(cols)} numbers per draw, expected {era.white_drawn}")
                continue
            if ((w < 1) | (w > era.white_pool)).any().any():
                errors.append(f"{era_id}: white ball outside 1..{era.white_pool}")
            if (w.nunique(axis=1) != era.white_drawn).any():
                errors.append(f"{era_id}: repeated white ball within a draw")
            if "special" in part.columns and (era.special_pool or era.bonus):
                s = part["special"]
                top = era.white_pool if era.bonus else era.special_pool
                if ((s < 1) | (s > top)).any():
                    bad = part.loc[(s < 1) | (s > top), ["draw_date", "special"]].head(3)
                    errors.append(f"{era_id}: special ball outside 1..{top}: {bad.to_dict('records')}")
                if era.bonus and (w.values == s.values[:, None]).any():
                    errors.append(f"{era_id}: bonus ball repeats a winning number")
                if len(part) >= 100 and s.max() != top:
                    warnings.append(f"{era_id}: highest special ball {top} never drawn in {len(part)} draws")
            if len(part) >= 100 and w.max().max() != era.white_pool:
                warnings.append(f"{era_id}: highest white ball {era.white_pool} never drawn in {len(part)} draws")
    if errors:
        raise IngestError(f"{game}: " + "; ".join(errors))
    return warnings


def largest_gap_days(dates) -> int:
    """Longest stretch between consecutive draw dates (reported, never filled)."""
    d = pd.Series(sorted(set(pd.to_datetime(pd.Series(list(dates))))))
    return int(d.diff().max().days) if len(d) > 1 else 0


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _guarded_write(df: pd.DataFrame, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        path.unlink()
        raise IngestError(f"{path.name} would be {size / 1e6:.0f} MB (> {MAX_FILE_BYTES / 1e6:.0f} MB limit); "
                          "split it further before writing")
    return size


def write_tidy(game: str, tidy: pd.DataFrame, out_dir: Path = DATA_DIR) -> list[str]:
    if game == "quick_draw":
        written = []
        years = pd.to_datetime(tidy["draw_date"]).dt.year
        for year, part in tidy.groupby(years):
            p = out_dir / "quick_draw" / f"{year}.csv.gz"
            _guarded_write(part, p)
            written.append(str(p.relative_to(out_dir)))
        return written
    p = out_dir / f"{game}.csv"
    _guarded_write(tidy, p)
    return [p.name]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def ingest_game(game: str, raw: pd.DataFrame, out_dir: Path = DATA_DIR) -> dict:
    tidy = PARSERS[game](raw)
    warnings = validate(game, tidy)
    files = write_tidy(game, tidy, out_dir)
    return {
        "dataset_id": DATASETS[game]["id"],
        "dataset_title": DATASETS[game]["title"],
        "rows": int(len(tidy)),
        "first_draw": str(tidy["draw_date"].min()),
        "last_draw": str(tidy["draw_date"].max()),
        "largest_gap_days": largest_gap_days(tidy["draw_date"]),
        "draws_per_era": {k: int(v) for k, v in tidy["era_id"].value_counts().sort_index().items()},
        "files": files,
        "warnings": warnings,
    }


def run(games=None, from_dir: Path | None = None, out_dir: Path = DATA_DIR,
        qd_since: int | None = None) -> dict:
    games = games or list(DATASETS)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    cache: dict[str, pd.DataFrame] = {}   # Numbers and Win 4 share one dataset
    for game in games:
        ds = DATASETS[game]
        if from_dir:
            src = next((from_dir / f"{game}{ext}" for ext in (".csv", ".json")
                        if (from_dir / f"{game}{ext}").exists()), None)
            if src is None and game == "win4":
                src = next((from_dir / f"ny_numbers{ext}" for ext in (".csv", ".json")
                            if (from_dir / f"ny_numbers{ext}").exists()), None)
            if src is None:
                print(f"{game}: no {game}.csv/.json in {from_dir}; skipped")
                continue
            raw, origin = read_export(src), str(src)
        else:
            if ds["id"] is None:
                print(f"{game}: dataset ID unknown (TODO in ingest.DATASETS); skipped")
                continue
            if ds["id"] not in cache:
                where = f"draw_date >= '{qd_since}-01-01'" if game == "quick_draw" and qd_since else None
                cache[ds["id"]] = load_rows(fetch_soda(ds["id"], where=where))
            raw, origin = cache[ds["id"]], SODA_BASE.format(id=ds["id"])
        info = ingest_game(game, raw, out_dir)
        info["source"] = origin
        info["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        manifest[game] = info
        print(f"{game}: {info['rows']} draws {info['first_draw']}..{info['last_draw']} {info['draws_per_era']}")
        for w in info["warnings"]:
            print(f"  warning: {w}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", nargs="+", choices=list(DATASETS))
    ap.add_argument("--from-dir", type=Path, help="read hand-exported CSV/JSON files instead of the API")
    ap.add_argument("--qd-since", type=int, help="only download Quick Draw draws from this year on")
    args = ap.parse_args(argv)
    try:
        run(args.games, args.from_dir, qd_since=args.qd_since)
    except IngestError as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
