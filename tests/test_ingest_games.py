"""Parsers for the v2 games, on realistic sample rows in the shapes data.ny.gov serves
(SODA JSON field names and CSV-export headers). Sample rows are test inputs only.
The NY Lotto row (2020-09-26) is a real draw seen in a data.ny.gov snippet; the rest
are hand-made but follow each game's rules."""

import pandas as pd
import pytest

from lottery import export, ingest

LOTTO_CSV = """Draw Date,Winning Numbers,Bonus #,Extra #
09/26/2020,14 19 20 23 55 57,22,
09/12/2001,01 02 03 04 05 59,40,
"""
TAKE5_SPLIT = [
    {"draw_date": "2026-10-28T00:00:00.000", "midday_winning_numbers": "01 05 12 22 39",
     "evening_winning_numbers": "03 07 18 30 33"},
    {"draw_date": "1992-01-17T00:00:00.000", "evening_winning_numbers": "02 04 06 08 10"},
]
PICK10 = [{"draw_date": "2026-10-28T00:00:00.000",
           "winning_numbers": " ".join(f"{n:02d}" for n in range(1, 81, 4))}]
QD = [{"draw_number": "3000001", "draw_date": "2026-10-28T00:00:00.000", "draw_time": "04:04:00",
       "winning_numbers": " ".join(str(n) for n in range(2, 42, 2)), "extra_multiplier": "1"},
      {"draw_number": "3000002", "draw_date": "2025-01-02T00:00:00.000", "draw_time": "04:08:00",
       "winning_numbers": " ".join(str(n) for n in range(41, 81, 2)), "extra_multiplier": "2"}]
C4L = [{"draw_date": "2026-02-21T00:00:00.000", "winning_numbers": "05 16 33 41 60", "cash_ball": "04"}]
MFL = [{"draw_date": "2026-04-11T00:00:00.000", "winning_numbers": "08 19 27 44 58", "millionaire_ball": "5"}]
DIGITS = [
    {"draw_date": "2026-10-28T00:00:00.000", "midday_daily": "944", "evening_daily": "558",
     "midday_win_4": "1234", "evening_win_4": "5678"},
    {"draw_date": "1980-09-02T00:00:00.000", "evening_daily": "45", "evening_win_4": "1"},
]


def test_ny_lotto_from_csv_export(tmp_path):
    p = tmp_path / "ny_lotto.csv"
    p.write_text(LOTTO_CSV)
    df = ingest.parse_ny_lotto(ingest.read_export(p))
    assert df["era_id"].tolist() == ["lotto_2001", "lotto_2001"]
    last = df.iloc[1]
    assert [last[f"n{i}"] for i in range(1, 7)] == [14, 19, 20, 23, 55, 57] and last["special"] == 22
    ingest.validate("ny_lotto", df)


def test_ny_lotto_bonus_repeating_a_winner_is_rejected():
    rows = ingest.load_rows([{"draw_date": "2020-01-01", "winning_numbers": "1 2 3 4 5 6", "bonus": "6"}])
    with pytest.raises(ingest.IngestError, match="bonus ball repeats"):
        ingest.validate("ny_lotto", ingest.parse_ny_lotto(rows))


def test_take5_midday_and_evening_columns_never_filled():
    df = ingest.parse_take5(ingest.load_rows(TAKE5_SPLIT))
    assert df[["draw_time"]].value_counts().to_dict() == {("evening",): 2, ("midday",): 1}
    assert len(df) == 3  # the 1992 row has no midday draw, and none is invented
    ingest.validate("take5", df)


def test_take5_out_of_range_is_rejected():
    rows = ingest.load_rows([{"draw_date": "2020-01-01", "winning_numbers": "1 2 3 4 40"}])
    with pytest.raises(ingest.IngestError, match="outside 1..39"):
        ingest.validate("take5", ingest.parse_take5(rows))


def test_pick10_and_quick_draw_need_20_distinct_numbers():
    df = ingest.parse_pick10(ingest.load_rows(PICK10))
    assert len(ingest.white_cols(df)) == 20
    ingest.validate("pick10", df)
    qd = ingest.parse_quick_draw(ingest.load_rows(QD))
    assert qd["draw_number"].tolist() == [3000002, 3000001]
    ingest.validate("quick_draw", qd)
    bad = ingest.load_rows([{**QD[0], "winning_numbers": "1 " * 21}])
    with pytest.raises(ingest.IngestError, match="expected 20"):
        ingest.parse_quick_draw(bad)


def test_cash4life_draw_after_retirement_is_rejected():
    df = ingest.parse_cash4life(ingest.load_rows(C4L))
    ingest.validate("cash4life", df)
    late = ingest.load_rows([{**C4L[0], "draw_date": "2026-03-01T00:00:00.000"}])
    with pytest.raises(ingest.IngestError, match="outside every known era"):
        ingest.validate("cash4life", ingest.parse_cash4life(late))


def test_millionaire_for_life_ball_column_or_appended():
    df = ingest.parse_millionaire_for_life(ingest.load_rows(MFL))
    assert df.iloc[0]["special"] == 5
    appended = ingest.load_rows([{"draw_date": "2026-04-11", "winning_numbers": "08 19 27 44 58 05"}])
    assert ingest.parse_millionaire_for_life(appended).iloc[0]["special"] == 5
    ingest.validate("millionaire_for_life", df)


def test_win4_shares_the_numbers_dataset_and_zero_pads():
    df = ingest.parse_win4(ingest.load_rows(DIGITS))
    assert df["number"].tolist() == ["0001", "5678", "1234"]  # same-day order: evening, midday (as v1)
    assert df.iloc[0][["d1", "d2", "d3", "d4"]].tolist() == [0, 0, 0, 1]
    ingest.validate("win4", df)
    nums = ingest.parse_numbers(ingest.load_rows(DIGITS))
    assert nums["number"].tolist() == ["045", "558", "944"]


def test_unknown_dataset_is_skipped_not_faked(tmp_path, capsys):
    ingest.run(["millionaire_for_life"], out_dir=tmp_path)
    assert "dataset ID unknown" in capsys.readouterr().out
    assert not (tmp_path / "millionaire_for_life.csv").exists()


def test_quick_draw_is_written_per_year(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    pd.DataFrame(QD).to_csv(src / "quick_draw.csv", index=False)
    man = ingest.run(["quick_draw"], from_dir=src, out_dir=tmp_path / "data")
    assert sorted(man["quick_draw"]["files"]) == ["quick_draw/2025.csv.gz", "quick_draw/2026.csv.gz"]
    df = export.load_tidy("quick_draw", tmp_path / "data")
    assert len(df) == 2


def test_file_size_cap_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "MAX_FILE_BYTES", 100)
    df = ingest.parse_pick10(ingest.load_rows(PICK10 * 1))
    with pytest.raises(ingest.IngestError, match="limit"):
        ingest.write_tidy("pick10", df, tmp_path)
    assert not (tmp_path / "pick10.csv").exists()
