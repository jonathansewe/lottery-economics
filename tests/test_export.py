"""Per-year JSON export. Synthetic fair draws are generated into tmp_path only."""

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from lottery import export, ingest, rules


def _lotto(path, game, dates, rng):
    era = rules.current_era(game)
    rows = []
    for d in dates:
        w = sorted(rng.choice(np.arange(1, era.white_pool + 1), era.white_drawn, replace=False))
        row = {"draw_date": d, "era_id": rules.era_for(game, d).era_id, **{f"n{i + 1}": int(x) for i, x in enumerate(w)}}
        if era.special_pool:
            row["special"] = int(rng.integers(1, era.special_pool + 1))
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_per_year_files_index_and_coverage(tmp_path):
    rng = np.random.default_rng(0)
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    # Take 5 with a deliberate hole: 2019 is missing entirely
    dates = [date(2018, 1, 1) + timedelta(days=i) for i in range(10)] + \
            [date(2020, 1, 1) + timedelta(days=i) for i in range(5)]
    _lotto(data / "take5.csv", "take5", dates, rng)
    # Powerball starts after NY's (unverified) 2010 join date in this fake data
    _lotto(data / "powerball.csv", "powerball", [date(2016, 1, 2), date(2016, 1, 6)], rng)
    idx = export.export_draws(data, out)

    t5 = idx["take5"]
    assert [f["period"] for f in t5["files"]] == ["2018", "2020"]   # no 2019 file invented
    assert t5["largest_gap_days"] > 365
    rows = json.loads((out / "take5/2020.json").read_text())["rows"]
    assert len(rows) == 5 and len(rows[0][2]) == 5
    pb = idx["powerball"]
    assert "Earlier draws are not in this dataset" in pb["coverage"] and "unverified" in pb["coverage"]
    assert not idx["pick10"]["available"] and "not been ingested" in idx["pick10"]["coverage"]
    assert set(json.loads((out / "index.json").read_text())["games"]) == set(rules.GAMES)


def test_quick_draw_recent_months_and_full_summary(tmp_path):
    rng = np.random.default_rng(1)
    data, out = tmp_path / "data", tmp_path / "out"
    era = rules.current_era("quick_draw")
    for year in (2013, 2024, 2025, 2026):
        rows = []
        for i in range(6):
            d = date(year, 1 + i, 3)
            w = sorted(rng.choice(np.arange(1, 81), 20, replace=False))
            rows.append({"draw_date": d, "draw_number": year * 100 + i, "era_id": era.era_id,
                         **{f"n{j + 1}": int(x) for j, x in enumerate(w)}})
        ingest.write_tidy("quick_draw", pd.DataFrame(rows), data)
    idx = export.export_draws(data, out, qd_recent_years=2)["quick_draw"]
    assert idx["recent_years"] == [2025, 2026]
    assert {f["period"][:4] for f in idx["files"]} == {"2025", "2026"}
    assert len(idx["files"]) == 12  # one per month present
    summ = json.loads((out / idx["summary_file"]).read_text())["years"]
    assert set(summ) == {"2013", "2024", "2025", "2026"}
    assert all(sum(v["counts"]) == v["draws"] * 20 for v in summ.values())
    assert "summarised as per-number counts" in idx["coverage"]


def test_export_respects_size_cap(tmp_path, monkeypatch):
    rng = np.random.default_rng(2)
    data = tmp_path / "data"
    data.mkdir()
    _lotto(data / "take5.csv", "take5", [date(2020, 1, 1) + timedelta(days=i) for i in range(50)], rng)
    monkeypatch.setattr(ingest, "MAX_FILE_BYTES", 500)
    with pytest.raises(ingest.IngestError, match="exceed"):
        export.export_draws(data, tmp_path / "out")


def test_rerun_removes_stale_files(tmp_path):
    rng = np.random.default_rng(3)
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    _lotto(data / "take5.csv", "take5", [date(2018, 5, 1), date(2019, 5, 1)], rng)
    export.export_draws(data, out)
    _lotto(data / "take5.csv", "take5", [date(2019, 5, 1)], rng)
    export.export_draws(data, out)
    assert sorted(p.name for p in (out / "take5").iterdir()) == ["2019.json"]
