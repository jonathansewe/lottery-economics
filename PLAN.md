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
