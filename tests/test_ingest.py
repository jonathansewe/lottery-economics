"""Ingest tests run on tiny hand-written fixtures in the two shapes data.ny.gov
serves: SODA API JSON (snake_case fields, ISO dates) and the CSV export (display
headers, MM/DD/YYYY dates). These rows are test inputs only, never written to data/.
"""

import json
from datetime import date

import pandas as pd
import pytest

from lottery import ingest

PB_SODA = [
    # last draw of the 5/59 + 1/35 era and first of 5/69 + 1/26
    {"draw_date": "2015-10-03T00:00:00.000", "winning_numbers": "09 15 23 46 57 35", "multiplier": "2"},
    {"draw_date": "2015-10-07T00:00:00.000", "winning_numbers": "68 18 34 14 43 26", "multiplier": "3"},
    {"draw_date": "2010-02-03T00:00:00.000", "winning_numbers": "17 22 36 37 52 24", "multiplier": "2"},
]

MM_CSV = """Draw Date,Winning Numbers,Mega Ball,Multiplier
09/25/2020,20 36 37 48 67,16,02
10/27/2017,01 02 03 04 75,15,
10/31/2017,05 06 07 08 70,25,03
04/08/2025,10 20 30 40 50,24,
"""

NUM_SODA = [
    {"draw_date": "2026-10-28T00:00:00.000", "midday_daily": "944", "evening_daily": "558",
     "midday_win_4": "1234", "evening_win_4": "5678"},
    {"draw_date": "1980-09-02T00:00:00.000", "evening_daily": "45", "evening_win_4": "0001"},
]


def test_normalize_key():
    assert ingest.normalize_key("Draw Date") == "draw_date"
    assert ingest.normalize_key("Midday Daily #") == "midday_daily"
    assert ingest.normalize_key("Mega Ball") == "mega_ball"


@pytest.mark.parametrize("raw,expected", [
    ("2015-10-07T00:00:00.000", date(2015, 10, 7)),
    ("10/07/2015", date(2015, 10, 7)),
])
def test_parse_date(raw, expected):
    assert ingest.parse_date(raw) == expected


def test_powerball_era_tagging_and_split_of_powerball():
    df = ingest.parse_powerball(ingest.load_rows(PB_SODA))
    assert df["draw_date"].tolist() == [date(2010, 2, 3), date(2015, 10, 3), date(2015, 10, 7)]
    assert df["era_id"].tolist() == ["pb_2009", "pb_2012", "pb_2015"]
    first_new = df.iloc[2]
    assert [first_new[f"n{i}"] for i in range(1, 6)] == [14, 18, 34, 43, 68]  # sorted
    assert first_new["special"] == 26
    assert ingest.validate("powerball", df) == []


def test_mega_millions_from_csv_export(tmp_path):
    p = tmp_path / "mega_millions.csv"
    p.write_text(MM_CSV)
    df = ingest.parse_mega_millions(ingest.read_export(p))
    assert df["era_id"].tolist() == ["mm_2013", "mm_2017", "mm_2017", "mm_2025"]
    assert df["special"].tolist() == [15, 25, 16, 24]
    assert df["multiplier"].isna().tolist() == [True, False, False, True]
    ingest.validate("mega_millions", df)


def test_out_of_range_special_ball_is_rejected():
    # A Mega Ball of 25 is impossible in the 1..24 era: if the era boundary were
    # wrong, real data would trip exactly this check.
    rows = ingest.load_rows([{"draw_date": "2025-04-11T00:00:00.000",
                              "winning_numbers": "01 02 03 04 05", "mega_ball": "25"}])
    df = ingest.parse_mega_millions(rows)
    with pytest.raises(ingest.IngestError, match="special ball outside 1..24"):
        ingest.validate("mega_millions", df)


def test_repeated_white_ball_is_rejected():
    rows = ingest.load_rows([{"draw_date": "2020-01-03T00:00:00.000",
                              "winning_numbers": "01 01 03 04 05", "mega_ball": "2"}])
    with pytest.raises(ingest.IngestError, match="repeated white ball"):
        ingest.validate("mega_millions", ingest.parse_mega_millions(rows))


def test_duplicate_draw_is_rejected():
    rows = ingest.load_rows([PB_SODA[1], PB_SODA[1]])
    with pytest.raises(ingest.IngestError, match="duplicate"):
        ingest.validate("powerball", ingest.parse_powerball(rows))


def test_draw_before_any_era_is_rejected():
    rows = ingest.load_rows([{"draw_date": "1999-01-01T00:00:00.000", "winning_numbers": "1 2 3 4 5 6"}])
    with pytest.raises(ingest.IngestError, match="outside every known era"):
        ingest.validate("powerball", ingest.parse_powerball(rows))


def test_numbers_midday_evening_zero_padding_and_win4_ignored():
    df = ingest.parse_numbers(ingest.load_rows(NUM_SODA))
    assert df[["draw_time", "number"]].values.tolist() == [
        ["evening", "045"], ["evening", "558"], ["midday", "944"]]
    assert df.iloc[0][["d1", "d2", "d3"]].tolist() == [0, 4, 5]
    assert set(df["era_id"]) == {"numbers_1980"}
    ingest.validate("ny_numbers", df)


def test_run_from_dir_is_idempotent(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "powerball.json").write_text(json.dumps(PB_SODA))
    out = tmp_path / "out"
    ingest.run(["powerball"], from_dir=src, out_dir=out)
    first = (out / "powerball.csv").read_text()
    manifest = ingest.run(["powerball"], from_dir=src, out_dir=out)
    assert (out / "powerball.csv").read_text() == first
    assert manifest["powerball"]["rows"] == 3
    assert manifest["powerball"]["dataset_id"] == "d6yy-54nr"
    assert pd.read_csv(out / "powerball.csv")["era_id"].tolist() == ["pb_2009", "pb_2012", "pb_2015"]


def test_fetch_soda_pages_until_short_page(monkeypatch):
    monkeypatch.setattr(ingest, "PAGE", 2)
    pages = [[{"a": 1}, {"a": 2}], [{"a": 3}]]
    calls = []

    class FakeResp:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class FakeSession:
        def get(self, url, params, headers, timeout):
            calls.append(params["$offset"])
            return FakeResp(pages[len(calls) - 1])

    rows = ingest.fetch_soda("d6yy-54nr", session=FakeSession())
    assert rows == [{"a": 1}, {"a": 2}, {"a": 3}]
    assert calls == [0, 2]
