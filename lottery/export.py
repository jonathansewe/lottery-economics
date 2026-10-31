"""Split tidy draw data into small JSON files the website loads only when needed.

docs/data/draws/index.json            what exists: per game, files, coverage, gaps
docs/data/draws/<game>/<year>.json    every draw of that year
docs/data/draws/quick_draw/<yyyy-mm>.json   Quick Draw: one file per month, recent years only
docs/data/draws/quick_draw/summary.json     Quick Draw: per-year counts per number, full history

Quick Draw runs every few minutes (100k+ draws a year), so shipping every draw
would make the site heavy; recent years are kept in full and older years only as
counts. No file may exceed ingest.MAX_FILE_BYTES. Missing periods are reported
(largest gap, coverage start vs. launch date) and never filled in.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import ingest, rules

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "draws"
QD_RECENT_YEARS = 2


def load_tidy(game: str, data_dir: Path, years: set[int] | None = None) -> pd.DataFrame | None:
    """Read a game's tidy data (Quick Draw: the requested years only)."""
    if game == "quick_draw":
        files = sorted((data_dir / "quick_draw").glob("*.csv.gz"))
        if years is not None:
            files = [f for f in files if int(f.name[:4]) in years]
        if not files:
            return None
        df = pd.concat([pd.read_csv(f, dtype={"number": str}) for f in files], ignore_index=True)
    else:
        path = data_dir / f"{game}.csv"
        if not path.exists():
            return None
        df = pd.read_csv(path, dtype={"number": str})
    df["draw_date"] = pd.to_datetime(df["draw_date"]).dt.date
    return df


def quick_draw_years(data_dir: Path) -> list[int]:
    return sorted(int(f.name[:4]) for f in (data_dir / "quick_draw").glob("*.csv.gz"))


def _rows(df: pd.DataFrame) -> tuple[list[str], list[list]]:
    """Compact rows: [date, time, numbers, special, multiplier, draw_number]."""
    cols = ["date", "time", "numbers", "special", "multiplier", "draw_number"]
    wc = ingest.white_cols(df)

    def val(row, c):
        return None if c not in row or pd.isna(row[c]) else row[c]

    out = []
    for _, r in df.iterrows():
        nums = r["number"] if "number" in df.columns else [int(r[c]) for c in wc]
        out.append([str(r["draw_date"]), val(r, "draw_time"), nums,
                    None if val(r, "special") is None else int(r["special"]),
                    None if val(r, "multiplier") is None else int(r["multiplier"]),
                    None if val(r, "draw_number") is None else int(r["draw_number"])])
    return cols, out


def _write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), allow_nan=False)
    if len(text.encode()) > ingest.MAX_FILE_BYTES:
        raise ingest.IngestError(f"{path} would exceed {ingest.MAX_FILE_BYTES / 1e6:.0f} MB; split it further")
    path.write_text(text)
    return len(text.encode())


def coverage_note(game: str, first_draw: str | None) -> str:
    launch, verified, note = rules.GAME_LAUNCH[game]
    if first_draw is None:
        return "Draw data has not been ingested yet."
    first = date.fromisoformat(first_draw)
    if launch is None:
        return f"NY Open Data starts {first}. The game's launch date was not verified, so earlier draws may exist."
    if first > launch:
        tag = "" if verified else " (unverified)"
        return (f"NY Open Data starts {first}, but the game began {launch}{tag}: {note}. "
                "Earlier draws are not in this dataset and are not shown or estimated.")
    return f"NY Open Data covers the game from its start ({first})."


def _quick_draw_summary(data_dir: Path) -> dict:
    era = rules.current_era("quick_draw")
    out = {}
    for year in quick_draw_years(data_dir):
        df = load_tidy("quick_draw", data_dir, {year})
        whites = df[ingest.white_cols(df)].to_numpy(int).ravel()
        out[str(year)] = {"draws": int(len(df)),
                          "counts": np.bincount(whites, minlength=era.white_pool + 1)[1:].tolist()}
    return out


def export_draws(data_dir: Path = ingest.DATA_DIR, out_dir: Path = OUT,
                 qd_recent_years: int = QD_RECENT_YEARS) -> dict:
    index = {}
    for game in rules.GAMES:
        gdir = out_dir / game
        if gdir.exists():
            shutil.rmtree(gdir)  # rebuild from scratch: no stale years left behind
        entry = {"label": rules.GAME_LABELS[game], "available": False, "files": [],
                 "launch": str(rules.GAME_LAUNCH[game][0]) if rules.GAME_LAUNCH[game][0] else None,
                 "launch_verified": rules.GAME_LAUNCH[game][1], "dataset_id": ingest.DATASETS[game]["id"]}
        if game == "quick_draw":
            years = quick_draw_years(data_dir)
            recent = set(years[-qd_recent_years:]) if years else set()
            df = load_tidy(game, data_dir, recent)
            entry["recent_only"] = True
            entry["recent_years"] = sorted(recent)
            if years:
                entry["summary_file"] = "quick_draw/summary.json"
                _write_json(out_dir / entry["summary_file"],
                            {"game": game, "years": _quick_draw_summary(data_dir)})
                entry["all_years"] = years
        else:
            df = load_tidy(game, data_dir)
        if df is None or df.empty:
            entry["coverage"] = coverage_note(game, None)
            index[game] = entry
            continue
        dts = pd.to_datetime(df["draw_date"])
        groups = df.groupby([dts.dt.year, dts.dt.month]) if game == "quick_draw" else df.groupby(dts.dt.year)
        for key, part in groups:
            name = f"{key[0]}-{key[1]:02d}" if game == "quick_draw" else str(key)
            cols, rows = _rows(part)
            rel = f"{game}/{name}.json"
            size = _write_json(out_dir / rel, {"game": game, "period": name, "columns": cols, "rows": rows})
            entry["files"].append({"period": name, "file": rel, "rows": len(rows), "bytes": size})
        first = str(df["draw_date"].min())
        entry.update(available=True, first_draw=first, last_draw=str(df["draw_date"].max()),
                     rows=int(len(df)), largest_gap_days=ingest.largest_gap_days(df["draw_date"]),
                     coverage=coverage_note(game, first))
        if game == "quick_draw" and entry.get("all_years"):
            first_qd = str(load_tidy(game, data_dir, {entry["all_years"][0]})["draw_date"].min())
            entry["first_draw"] = first_qd
            entry["coverage"] = (coverage_note(game, first_qd)
                                 + f" Every draw is listed for {', '.join(map(str, entry['recent_years']))};"
                                 " earlier years are summarised as per-number counts.")
        index[game] = entry
    _write_json(out_dir / "index.json", {"games": index})
    return index
