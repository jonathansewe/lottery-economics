"""Stats for the v2 games on seeded synthetic fair draws (tmp_path only)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from lottery import ingest, rules, stats


def _write(game, path_or_dir, n, rng, start=date(2020, 1, 1)):
    era = rules.current_era(game)
    rows = []
    for i in range(n):
        d = start + timedelta(days=i)
        if era.kind == "digits":
            x = rng.integers(0, 10, era.white_drawn)
            rows.append({"draw_date": d, "draw_time": "evening", "era_id": era.era_id,
                         "number": "".join(map(str, x)), **{f"d{j + 1}": int(v) for j, v in enumerate(x)}})
            continue
        drawn = rng.choice(np.arange(1, era.white_pool + 1), era.white_drawn + (1 if era.bonus else 0), replace=False)
        w = sorted(drawn[:era.white_drawn])
        row = {"draw_date": d, "era_id": era.era_id, **{f"n{j + 1}": int(x) for j, x in enumerate(w)}}
        if era.bonus:
            row["special"] = int(drawn[-1])
        elif era.special_pool:
            row["special"] = int(rng.integers(1, era.special_pool + 1))
        rows.append(row)
    df = pd.DataFrame(rows)
    if game == "quick_draw":
        ingest.write_tidy("quick_draw", df, path_or_dir)
    else:
        df.to_csv(path_or_dir / f"{game}.csv", index=False)


def test_analyze_covers_every_new_game_kind(tmp_path):
    rng = np.random.default_rng(7)
    for game, n in [("ny_lotto", 300), ("take5", 300), ("pick10", 200), ("win4", 2000), ("quick_draw", 400)]:
        _write(game, tmp_path, n, rng, start=date(2025, 6, 1) if game == "quick_draw" else date(2020, 1, 1))
    out = stats.analyze(tmp_path)
    sets = {(t["game"], t["ball_set"]): t for t in out["tests"]}
    assert set(sets) == {("ny_lotto", "white"), ("ny_lotto", "bonus"), ("take5", "white"),
                         ("pick10", "white"), ("quick_draw", "white"),
                         ("win4", "digit_1"), ("win4", "digit_2"), ("win4", "digit_3"),
                         ("win4", "digit_4"), ("win4", "number")}
    assert sets[("pick10", "white")]["correction_factor"] == pytest.approx(79 / 60)
    assert sets[("ny_lotto", "white")]["correction_factor"] == pytest.approx(58 / 53)
    assert sets[("ny_lotto", "bonus")]["df"] == 58
    assert sets[("quick_draw", "white")]["n_draws"] == 400  # streamed across two year files
    assert not sets[("win4", "number")]["min_expected_ok"]   # 2000 draws / 10,000 cells
    assert all(t["n_tests"] == 10 for t in out["tests"])
    qd = next(f for f in out["frequencies"] if f["game"] == "quick_draw")
    assert sum(qd["counts"]) == 400 * 20


def test_keno_correction_is_calibrated():
    rng = np.random.default_rng(9)
    m, k, n = 80, 20, 150
    stat = [stats.chi_square(stats.simulate_counts(n, k, m, rng), n, k, m)["statistic"] for _ in range(1500)]
    assert np.mean(stat) == pytest.approx(m - 1, rel=0.03)
    ps = [stats.chi_square(stats.simulate_counts(n, k, m, rng), n, k, m)["p_value"] for _ in range(1500)]
    assert np.mean(np.asarray(ps) < 0.05) == pytest.approx(0.05, abs=0.015)


def test_bonus_ball_is_uniform_at_the_margin():
    # The bonus is drawn from the 53 balls left, yet each of the 59 is equally likely
    # to be the bonus (by symmetry): check by simulation.
    rng = np.random.default_rng(11)
    bonus = [rng.choice(59, 7, replace=False)[-1] for _ in range(59_000)]
    counts = np.bincount(bonus, minlength=59)
    assert stats.chi_square(counts, len(bonus), 1, 59)["p_value"] > 0.001
