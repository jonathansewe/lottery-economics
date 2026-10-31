# Lottery Economics — v1 build plan

Goal: an educational static site plus a Python pipeline that shows, with exact
math and real draw data, what US lottery games actually pay, and that "hot
numbers" are noise. **No feature may suggest or predict numbers to play.**

## Constraints discovered before building (2026-10-30)

The build container's network policy blocks `data.ny.gov`, `powerball.com`,
`megamillions.com`, `nylottery.ny.gov`, `irs.gov`, `tax.ny.gov`, and the JS CDNs.
PyPI and the npm registry are reachable. Web *search* works (snippets only).

Consequences:

1. Game rules and tax rates are verified through search snippets restricted to
   official domains. Every fact in `lottery/rules.py` / `config.py` carries the source URL
   and a `verified` flag saying exactly how it was checked.
2. Real draw data cannot be downloaded in this session. `ingest.py` is built and
   tested against a small Socrata-shaped test fixture, and the site renders
   an explicit "data not ingested yet" state. **No fabricated draw data is committed.**
   One command (`python -m lottery.build --ingest`) fills everything in once
   `data.ny.gov` is reachable (or from manually downloaded CSVs via `--from-dir`).
3. The site is tested locally with D3/TopoJSON installed from npm and served
   in place of the CDN URLs; the shipped site uses the CDN.

## Layout

```
lottery-economics/
  PLAN.md  README.md  requirements.txt
  lottery/
    config.py     # tax rates, cash ratio, split-model defaults (with sources)
    rules.py      # game matrices + prize tables with effective date ranges
    math.py       # exact odds, EV, Poisson jackpot-split model
    ingest.py     # Socrata pull -> tidy CSVs in data/, era tagging + validation
    stats.py      # frequencies, chi-square (with without-replacement correction),
                  # Bonferroni, fair-draw simulation
    build.py      # writes docs/data/*.json (the only thing the site reads)
  tests/          # pytest: odds vs official, EV identities, ingest, stats
  notebooks/analysis.ipynb
  docs/           # GitHub Pages root: index.html, css/, js/, data/
  scripts/check_links.py  # verifies state lottery URLs when network allows
```

## Steps (commit after each)

1. **Scaffold + plan** — this file, requirements, package skeleton.
2. **Rules + math engine** — eras for Powerball (3) and Mega Millions (5) and
   NY Numbers; exact odds per tier via hypergeometric counting; EV per $1
   (fixed tiers, jackpot at cash value, after federal+NYS+NYC tax);
   Poisson split model `E[share] = (1 - e^-λ)/λ`. Tests compare every tier
   with officially published odds.
3. **Ingest** — dataset IDs `d6yy-54nr` (Powerball), `5xaw-6ayf` (Mega Millions),
   `hsys-3def` (Numbers/Win-4). Paged SODA requests, header normalisation,
   era tagging by draw date, range validation per era (catches wrong era
   boundaries), idempotent re-runs. Tested on fixtures.
4. **Stats** — per game/era/ball-type frequency; Pearson chi-square with the
   exact (m-1)/(m-k) correction for drawing k of m without replacement,
   cross-checked by Monte Carlo; Bonferroni across all tests; simulation
   of fair histories showing hot/cold spread and zero half-to-half
   persistence. Notebook mirrors this.
5. **Build JSON** — `docs/data/games.json`, `ev.json`, `stats.json`,
   `simulation.json`, `states.json`.
6. **Website** — landing numbers, D3 US map, NY deep-dive panel (games, odds,
   EV, frequency charts, chi-square, simulation), other states panel
   (Powerball/Mega Millions participation + official link, "Deep dive coming
   soon"), EV calculator (JS port of the Python EV, checked against Python
   output in a test). Accessible: keyboard-focusable states, ARIA, list
   fallback for the map, prefers-color-scheme.
7. **Verify + document** — pytest green, Playwright screenshots of every panel
   at desktop and phone width, README (findings, commands, sources,
   assumptions, "How it works, explained").

## Out of scope (v1)

Other states' historical data, school-funding audit, scratch-off EV, AI features,
Power Play / Double Play / Just the Jackpot add-ons (base play only; noted).

---

# v2 plan (2026-10-31): all major NY games, history, number checker, sales

Still offline: data.ny.gov, the lottery sites and GitHub are unreachable. Rules are
checked through official-domain search snippets only; everything else is marked
`unverified` in code and on the site. No real or synthetic draws are committed.

## Research results that change scope

- **Cash4Life ended nationally on 2026-02-21** and NY replaced it with
  **Millionaire for Life** (first draw 2026-02-22, $5, 5/58 + 1/5). Both are added:
  Cash4Life as a retired game (its dataset `kwxv-fwze` is static), Millionaire for
  Life as current (dataset ID unknown: TODO).
- NY Lotto: 6/59 + bonus, $1 buys two plays, 40% of sales to prizes split
  75 / 7.25 / 5.5 / 6.25 / 6 % across tiers (pari-mutuel). A 2026 "odds correction"
  proposal quotes 3rd-prize odds 1 in 144,418.98; exact counting gives
  1 in 144,414.98 (matches the 2020 sheet). Reported, not resolved.
- Take 5: 5/39, $1, 50% of sales to prizes, jackpot 20% of that; match-2 wins a
  free Quick Pick. Lower-tier shares not found (unverified).
- Pick 10 fully verified (20 of 80 drawn, pick 10, $1, $5M top-prize liability cap).
- Quick Draw: 8-spot table verified; other spot tables partly verified (snippets
  from a 2020 PDF and a test subdomain) — unverified amounts flagged.
- Win 4 payouts: no official snippet found — unverified.
- Powerball / Mega Millions share of sales funding the jackpot: not found. Sales
  method (a) is disabled for them (no guessed constant); NY Lotto (30% of sales)
  and Take 5 (10% of sales) have verified shares.

## Steps (commit after each)

0. **Tax fix** — tax *all* prizes in EV ("owed" view, default). Keep a labelled
   "withholding only" view: federal 24% + NYS/NYC top rates on prizes over $5,000
   (IRS W-2G instructions; NYS Pub 140W). JS calculator gets the toggle.
1. **All NY games** — generalise rules (`kind`: lotto / digits / keno, bonus ball,
   pari-mutuel tiers, life prizes valued at cash option, per-value `verified`
   flags). Exact odds for every tier, EV per $1 (pre-tax, owed, withholding),
   tests against every published odds figure found.
2. **Parsers** — dataset registry (IDs or TODO); parsers for NY Lotto, Take 5,
   Win 4, Pick 10, Quick Draw, Cash4Life, Millionaire for Life; realistic sample-row
   tests. Export per-game, per-year JSON (`docs/data/draws/<game>/<year>.json`,
   Quick Draw per month, recent years only + full-history summary counts),
   50 MB hard cap per file, coverage vs. launch date reported, never gap-filled.
3. **Stats** — chi-square per game/era/ball set for every game (keno: 20 of 80
   with the (m-1)/(m-k) correction), Bonferroni across all.
4. **Sales estimator** (`lottery/sales.py`) — (a) Δcash jackpot ÷ jackpot share of
   sales; (b) pooled Poisson MLE `N = ΣW / Σp` from tier winner counts, with CI;
   comparison with official sales (error %, MAPE); scope labels (national vs NY).
   Inputs are CSV templates in `data/sales/` to be filled once online.
5. **Build + site** — games/EV for all games, Draw history tab (per game, sortable,
   searchable, paginated, CSV download, lazy year loading), Number checker
   (validation, exact odds, history hits, popular-pattern warnings), Ticket sales
   chart, tax-view toggle. Chromium check at desktop + phone.
6. **Docs + delivery** — README (findings, explainer for sales + checker), notebook,
   regenerated bundle, list of steps for when network/GitHub work.
