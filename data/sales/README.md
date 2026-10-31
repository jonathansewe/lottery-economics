# Ticket-sales inputs (fill in by hand once the official sites are reachable)

The estimator in `lottery/sales.py` reads these three files. They ship with headers
only: no values were collected yet, and none may be invented. Add one row per fact,
with the page you read it from in `source_url`.

| File | Columns | Where to find it |
|---|---|---|
| `jackpots.csv` | `game,draw_date,jackpot_cash,jackpot_won,source_url` | Cash jackpot per draw and whether it was won: nylottery.ny.gov past results (NY Lotto, Take 5); powerball.com / megamillions.com draw results |
| `winners.csv` | `game,draw_date,scope,tier,winners,source_url` | Winners per prize tier. `scope` = `national` (powerball.com / megamillions.com results) or `NY` (nylottery.ny.gov results). `tier` uses `white+special` keys, e.g. `3+1`, `5+0`; NY Lotto `6+0`, `5+1`, `5+0`, `4`, `3`; Take 5 `5`, `4`, `3`, `2` |
| `official_sales.csv` | `game,period_start,period_end,scope,sales_dollars,source_url` | NY Lottery annual financial reports (sales by game, fiscal year April-March), e.g. https://edit.nylottery.ny.gov/sites/default/files/2025-07/Final_NYSL_FS_2025.pdf |

`game` is one of: `powerball`, `mega_millions`, `ny_lotto`, `take5`.
Dates are `YYYY-MM-DD`. Then run `python -m lottery.build`.
