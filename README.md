# Lottery Economics

An educational static website plus a Python analysis pipeline that shows what US lottery games
really pay back. It uses exact combinatorial odds and real NY Open Data draw history. It never
suggests or "predicts" numbers. The whole point is that you can't.

- **Python** (`lottery/`) computes every number: odds, expected value, statistics, simulations.
- **The website** (`docs/`) is plain HTML/CSS/JS + D3. It only reads JSON files that Python
  precomputed, so it needs no backend and deploys to GitHub Pages straight from `docs/`.

> **Status of this build (2026-10-30).** The container that built v1 could not reach
> `data.ny.gov` or the official lottery sites, because its network policy blocked them. As a result:
> 1. Game rules and tax rates were checked through search-engine snippets of the official
>    pages. Every value records how it was checked (see `lottery/rules.py`, `lottery/config.py`).
> 2. **No real draw data is included yet.** The draw-frequency and fairness-test panels show a
>    "data not ingested" notice until you run `python -m lottery.build --ingest` on a normal
>    connection (see [How to run it](#how-to-run-it)). Nothing in this repo is made-up draw data.

---

## Key findings

### From the math (exact, independent of draw data)

| Per $1 spent | Powerball ($2) | Mega Millions ($5) | NY Numbers ($1 straight) |
|---|---|---|---|
| Starting jackpot ($20M / $50M), as advertised | $0.19 | $0.26 | — |
| …at cash value, after tax owed on every prize (federal + NYS + NYC) | **$0.08** | **$0.11** | **$0.24** |
| …same, but only the tax *withheld* on prizes over $5,000 (not your final bill) | $0.14 | $0.21 | $0.50 |
| $1 billion jackpot, as advertised | $1.87 | $0.91 | — |
| …cash, after tax owed, with jackpot splitting (200M other tickets, assumed) | **$0.33** | **$0.21** | — |
| Break-even advertised jackpot, cash, before tax, no splitting | $1.17 billion | $2.62 billion | never |
| …after tax owed | $2.66 billion | $6.25 billion | never |

- **The "positive EV" billion-dollar jackpot is an illusion.** At $1B, Powerball's advertised
  number suggests $1.87 back per $1. Three corrections bring it to about $0.33: the cash option
  (42% of the advertised amount), 51.8% top-bracket tax for an NYC resident, and a roughly 50%
  chance someone else also wins (when 200M other tickets are sold).
- **Small prizes are a fixed rebate.** Powerball's non-jackpot tiers return $0.16 per $1 (about
  $0.08 after tax owed). Mega Millions' built-in multiplier averages exactly ×3, so its fixed tiers
  return $0.22 per $1. That's why Mega Millions beats Powerball at small jackpots despite the
  $5 price.
- **NY Numbers is the "best" of the three at 50 cents on the dollar before tax** (24 cents after
  tax owed), and it never changes, because every prize is fixed.
- All 30 published "1 in X" odds (27 prize tiers across Powerball and the Mega Millions 2017 and 2025 eras,
  plus 3 NY Numbers plays) match the exact combinatorial values. The tests check this.

### From the draw data

<!-- findings:start -->
*Real-data results are pending: the draw history has not been ingested in this build. Run `python -m lottery.build --ingest` and this section rewrites itself.*
<!-- findings:end -->

The simulation already shows the main point without any real data. In 1,000 perfectly fair
Powerball draws, the most-drawn and least-drawn white balls differ by 31–48 draws in 90% of
fair histories. "Hot" and "cold" numbers are what fairness looks like. And the counts in the
first half of a history are uncorrelated with the second half (mean rank correlation ≈ 0.00),
so past frequency tells you nothing.

---

## How to run it

Requires Python 3.11+.

```bash
cd lottery-economics
python -m venv .venv && source .venv/bin/activate   # isolated environment (Windows: .venv\Scripts\activate)
pip install -r requirements.txt                     # pandas, numpy, scipy, requests, pytest (+ notebook tools)

python -m pytest                                    # 60 tests: odds vs official, EV, ingest, stats, JS parity
python -m lottery.build --ingest                    # download draws from data.ny.gov -> data/*.csv,
                                                    # then write docs/data/*.json and refresh the README findings
python -m http.server 8000 -d docs                  # serve the site; open http://localhost:8000
```

What each command does:

| Command | What it does |
|---|---|
| `python -m lottery.ingest` | Pages through the three Socrata datasets and writes tidy, era-tagged `data/powerball.csv`, `data/mega_millions.csv`, `data/ny_numbers.csv` plus `data/manifest.json` (row counts, dates, warnings). Safe to re-run: it rebuilds from the full source every time. Set `SOCRATA_APP_TOKEN` to avoid anonymous rate limits. |
| `python -m lottery.ingest --games powerball` | Same, one game only. |
| `python -m lottery.ingest --from-dir ~/Downloads` | Use files you exported by hand from data.ny.gov ("Export" → CSV) named `powerball.csv`, `mega_millions.csv`, `ny_numbers.csv`. Useful behind a restrictive network. |
| `python -m lottery.build` | Recompute everything into `docs/data/*.json` from whatever is in `data/`, and rewrite the findings section above. |
| `python -m lottery.build --ingest` | Ingest, then build. **This is the one command for updating the site.** |
| `python scripts/make_notebook.py` then `jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb` | Regenerate and execute the notebook (run from `lottery-economics/`). |
| `python scripts/check_links.py` | Request every state-lottery URL and rule source. Run before publishing (these links were not verified at build time). |
| `python -m http.server 8000 -d docs` | The site uses `fetch()` for its JSON, which browsers block on `file://`, so serve it over HTTP. |

## Project layout

```
lottery/
  config.py   tax rates, cash-value ratios, ticket-sales scenarios: every assumption, with sources
  rules.py    game matrices + prize tables per era (effective dates, source URLs, how verified)
  math.py     exact odds, EV per $1, Poisson jackpot-split model, break-even jackpot
  ingest.py   Socrata download → tidy CSV, era tagging, validation
  stats.py    frequencies, chi-square (+ without-replacement correction), Bonferroni, simulations
  states.py   which jurisdictions sell Powerball / Mega Millions + lottery website links
  build.py    writes docs/data/*.json and the README findings section
tests/        pytest suite (60 tests)
notebooks/analysis.ipynb
docs/         the website (GitHub Pages root): index.html, css/, js/{ev,charts,app}.js, data/*.json
scripts/      notebook generator, link checker
```

## Data sources

| What | Source | ID / URL |
|---|---|---|
| Powerball draws (2010–) | NY Open Data, *Lottery Powerball Winning Numbers: Beginning 2010* | `d6yy-54nr`, https://data.ny.gov/Government-Finance/Lottery-Powerball-Winning-Numbers-Beginning-2010/d6yy-54nr |
| Mega Millions draws (2002–) | NY Open Data, *Lottery Mega Millions Winning Numbers: Beginning 2002* | `5xaw-6ayf`, https://data.ny.gov/Government-Finance/Lottery-Mega-Millions-Winning-Numbers-Beginning-20/5xaw-6ayf |
| NY Numbers draws (1980–) | NY Open Data, *Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980* | `hsys-3def`, https://data.ny.gov/d/hsys-3def |
| Powerball rules, prizes, odds | powerball.com prize chart & media center; NY Lottery odds sheet | URLs in `lottery/rules.py` |
| Mega Millions rules, prizes, odds, multiplier | megamillions.com how-to-play, new prize matrix, 2013/2017/2025 announcements | URLs in `lottery/rules.py` |
| NY Numbers payouts | NY Lottery *Numbers Odds and Prizes* PDF | URL in `lottery/rules.py` |
| Tax rates | IRS Rev. Proc. 2025-32 & Pub 505 (2026); tax.ny.gov; NYC Comptroller | URLs in `lottery/config.py` |
| Participating jurisdictions | powerball.com, megamillions.com/Where-to-Play | URLs in `lottery/states.py` |
| Map geometry | `us-atlas@3.0.1` TopoJSON (US Census cartographic boundaries) via jsDelivr | |

## Assumptions and limits

- **Base plays only.** Power Play, Double Play, Just the Jackpot and Powerball's UK lower-tier
  prize structure (from July 2026) are out of scope.
- **Prize tables only where verified.** The current Powerball era, the 2017–2025 and 2025+ Mega
  Millions eras, and NY Numbers have prize tables. Older eras (Powerball 2009/2012, Mega
  Millions 2002/2005/2013) carry only their ball pools, which is all the frequency analysis
  needs. Some of their boundary dates are from memory. `ingest.py` rejects any draw whose
  numbers don't fit its era's pools, so a wrong boundary fails loudly on real data.
- **Draws are without replacement** within a Powerball/Mega Millions draw (5 distinct white
  balls), and **with replacement** across NY Numbers digits (each digit has its own 0–9 machine).
  The math and the chi-square correction account for this.
- **Game eras are never mixed.** Frequencies and tests run per game, per era, per ball set.
- **Cash value** is a fixed ratio of the advertised jackpot (Powerball 0.421, Mega Millions 0.430,
  from recent official jackpot/cash pairs). In reality it moves with interest rates. The
  calculator lets you change it.
- **Taxes.** All gambling winnings are taxable income, so the default view taxes **every prize**
  at flat top marginal rates (federal 37%, NYS 10.9%, NYC 3.876%). That's accurate for jackpots
  and pessimistic for small prizes won by people in lower brackets. A separate, clearly
  labelled **withholding-only view** shows what is withheld when a prize is claimed: 24% federal
  (IRS W-2G rules) plus NYS and NYC at their top rates (NYS Pub 140W), on prizes over $5,000
  only. $5,000 is a withholding threshold, not an exemption, so that view understates what you
  finally owe. (v1 wrongly treated prizes under $5,000 as tax-free; fixed in v2.)
  Out-of-state winners pay different state tax.
- **Ticket sales** per draw aren't published in one machine-readable place, so the split model
  takes ticket counts as an input. Scenarios are labelled as assumptions. The model assumes
  other players pick uniformly at random. Real players over-pick birthdays and patterns, so
  someone playing popular numbers has a *worse* split risk than shown.
- **Pari-mutuel cases** (California's prize rules, rare high-liability draws) are ignored.
- **State lottery website URLs** were not reachable from the build machine. They are marked
  "link not yet verified" on the site until checked with `scripts/check_links.py`.

---

## How it works, explained

Written so you can explain every part in an interview.

### 1. Exact odds: counting, not estimating

A Powerball ticket picks 5 white balls from 69 and 1 red ball from 26. The number of distinct
tickets is

    C(69, 5) × 26 = 11,238,513 × 26 = 292,201,338

where `C(n, k) = n! / (k!(n−k)!)` counts ways to choose k items from n when order doesn't
matter. Exactly one of those wins the jackpot, so P(jackpot) = 1/292,201,338.

For partial matches you count how many tickets match *exactly* j white balls. Of your 5
numbers, j must come from the 5 winning numbers and 5−j from the 64 losing ones:

    P(j white) = C(5, j) · C(64, 5−j) / C(69, 5)

This is the **hypergeometric distribution**: sampling without replacement from a population
with two kinds of items (winning and losing numbers). Multiply by 1/26 if the Powerball must
match, or 25/26 if it must not. `lottery/math.py::tier_probability` does exactly this with
Python's `fractions.Fraction`, so the result is an exact rational number with no floating-point
error. The tests compare all of them with the official "1 in X" figures.

Example: "4 white + Powerball" = C(5,4)·C(64,1)/C(69,5) · 1/26 = 320/292,201,338 = 1 in
913,129.18, which matches the published chart to the cent.

**NY Numbers** is simpler. Three digits each drawn independently from 0–9 gives 10³ = 1,000
equally likely results. A *straight* bet covers 1 of them. A *6-way box* (three different
digits, any order) covers 3! = 6 permutations. A *3-way box* (two digits alike) covers
3!/2! = 3.

### 2. Expected value (EV)

EV is the probability-weighted average payout:

    EV = Σ over tiers  P(tier) × prize(tier)

Divide by the ticket price to get **return per $1**. The key property is *linearity of
expectation*: the EV of the whole ticket is the sum of each tier's EV, so you can add the
fixed prizes and the jackpot separately. That's why the site shows a "fixed prizes" part and a
"jackpot" part.

Mega Millions multiplies every non-jackpot prize by a random 2×/3×/4×/5×/10×. The published
odds (1 in 2.13, 3.2, 8, 16, 32) are exactly 15/32, 10/32, 4/32, 2/32 and 1/32, so
E[multiplier] = (2·15 + 3·10 + 4·4 + 5·2 + 10·1)/32 = 96/32 = **3.0**. By linearity, the fixed
prize EV is exactly three times the base table's EV. A test checks that.

The site walks EV down in four steps, each one more realistic than the last:

1. **Advertised.** The jackpot is the billboard number. That figure is the total of a 30-payment
   annuity, not money that exists today.
2. **Cash value.** The lump sum, about 42–43% of the advertised figure right now. It's the
   present value of the annuity, so it depends on interest rates.
3. **After tax.** Every prize is taxable income, so a top-bracket NYC resident loses
   37% + 10.9% + 3.876% = 51.776% of each one. The calculator's *withholding only* view applies
   only what the lottery withholds on claim (24% + 10.9% + 3.876%, on prizes over $5,000).
   That is a cash-flow number, not your tax bill.
4. **With splitting.** If other tickets also hit, the jackpot is divided (section 3).

**Break-even jackpot** solves `fixed + P(jackpot) · J · cash_ratio · (1 − tax) = price` for J.
It's the advertised jackpot at which EV reaches $1. Even this ignores splitting, and splitting
gets worse exactly when jackpots get big.

### 3. The jackpot-split model (Poisson)

Suppose N other tickets are sold, each a random pick, each winning with p = 1/292,201,338. The
number of other winners K is Binomial(N, p). When N is large and p is tiny, that is extremely
well approximated by a **Poisson distribution** with mean λ = N·p:

    P(K = k) = e^(−λ) λ^k / k!

If you win and K others do too, you get 1/(K+1) of the jackpot. Your expected share is

    E[1/(K+1)] = Σ_k e^(−λ) λ^k / k! · 1/(k+1)
               = (e^(−λ)/λ) · Σ_k λ^(k+1)/(k+1)!
               = (e^(−λ)/λ) · (e^λ − 1)
               = (1 − e^(−λ)) / λ

and P(you must share) = P(K ≥ 1) = 1 − e^(−λ). With 200M other tickets, λ ≈ 0.68, so
P(share) ≈ 50% and the expected share is ≈ 72%. The tests check the closed form against the
infinite series and against a Monte Carlo simulation of the binomial. In code, `-expm1(-λ)/λ`
is used instead of `(1-exp(-λ))/λ` because it stays accurate when λ is tiny. Plain `1 - exp(-λ)`
loses precision through *catastrophic cancellation*.

### 4. Is the lottery fair? Chi-square goodness of fit

**Null hypothesis H₀:** every ball is equally likely. Over n draws of k balls from m, each ball
is expected E = n·k/m times. Pearson's statistic measures how far the observed counts O_i are
from that:

    X² = Σ (O_i − E)² / E

Under H₀, X² approximately follows a **chi-square distribution with m − 1 degrees of freedom**.
The degrees of freedom are m − 1, not m, because the counts must sum to n·k, so once you know
m − 1 of them the last one is fixed. The **p-value** is P(a fair lottery produces an X² at least
this large). A small p-value means "this unevenness would be surprising if the draws were fair".

**The subtle part (the one most write-ups get wrong).** Pearson's test assumes each observation
lands in a cell independently. A Powerball draw puts 5 *different* balls in 5 cells, so if ball
7 is drawn, ball 8 is slightly less likely in the same draw. The counts are negatively
correlated. Working out the covariance of the indicator variables gives:

    Var(count_i) = n·p(1−p),   Cov(count_i, count_j) = −n·p(m−k) / (m(m−1)),   p = k/m

This is exactly (m−k)/(m−1) times the multinomial covariance with the same expected counts.
So the plain X² is too small by that factor, and the correct statistic is

    X²_corrected = X² · (m−1)/(m−k)      (68/64 ≈ 1.06 for Powerball)

The fix matters: without it, the test is too lenient and would under-report real bias.
`tests/test_stats.py` shows it empirically. Under simulated fair draws the raw statistic
averages m−k, the corrected one averages m−1, and exactly ~5% of corrected p-values fall below
0.05, which is what a well-calibrated test must do. A Monte Carlo p-value (simulate thousands
of fair histories and count how often they look at least this uneven) agrees with the analytic
one. For the single special ball and for Numbers digits, k = 1 and the factor is 1.

**Rule of thumb:** the chi-square approximation needs E ≥ 5 per cell. Tests below that are
flagged "small sample".

### 5. Multiple comparisons: Bonferroni

Each game × era × ball set is a separate test (around 20 in total). If you run 20 tests at
α = 0.05 on perfectly fair data, you expect about one "significant" result by luck. That's
how people "discover" biased lotteries. **Bonferroni** fixes it by requiring p < α/T for T
tests. By the union bound, P(any false alarm) ≤ T · (α/T) = α. It's conservative (it's allowed
to miss real effects) but simple and assumption-free, which suits this question.

### 6. Simulation: hot and cold numbers in fair data

`stats.simulate_fair` draws 1,000+ fair Powerball draws with a seeded RNG (k distinct balls
per draw via `argpartition` on random keys, which is a uniform random k-subset), then repeats
this for 1,000 independent histories and records:

- **Spread:** the most-drawn minus the least-drawn ball's count. In fair data this is
  routinely 30–50 draws. Every fair history has "hot" and "cold" numbers, and they're
  different every time.
- **95% band:** each ball's count is Binomial(n, k/m), so the site shades the range a single
  ball lands in 95% of the time. About 5% of bars poke out of it even in fair data.
- **Persistence:** split a history into halves and compute the Spearman rank correlation
  between first-half and second-half counts. If "hot numbers stay hot", it would be positive.
  For fair draws it centres on 0. The real data is placed inside this distribution.

This is the gambler's fallacy, made measurable: draws are independent, so a ball's past count
carries no information about its next appearance. That's also why the site has no
"suggest numbers" feature. The best you can do is avoid *popular* combinations, which only
changes how many people you would split with, not your chance of winning.

### 7. Data pipeline

`ingest.py` calls the **Socrata Open Data API** (`/resource/<id>.json`) with `$limit`/`$offset`
paging and a stable `$order=:id`. API field names (`draw_date`) and CSV-export headers
("Draw Date") both normalise to the same snake_case keys, so one parser handles either. Each
draw is tagged with its rule era by date. Validation then rejects:

- draws outside any era
- duplicates
- repeated white balls within a draw
- any ball outside its era's pool

That last check doubles as a test of the era boundary dates. Each run rebuilds the CSVs from
scratch (*idempotent*), so re-running never creates duplicates.

### 8. Front end

Python precomputes everything into `docs/data/*.json`, and the browser only renders it, so
there's no server and the site deploys anywhere static. D3 projects us-atlas TopoJSON with
`geoAlbersUsa` (which also insets Alaska and Hawaii). Each state is a keyboard-focusable SVG
button, and there's an equivalent plain list. The EV calculator needs live math, so `docs/js/ev.js` is a
line-for-line port of `lottery/math.py`. `tests/test_js_parity.py` runs it under Node and
asserts it matches Python to 12 significant digits, so the two can't drift apart.

### 9. Testing strategy

- **Against an external oracle:** every tier's odds vs the lottery's published odds.
- **Against independent methods:** closed form vs series vs Monte Carlo (split model);
  analytic vs Monte Carlo p-values; EV by explicit ticket counting.
- **Statistical calibration:** a correct test must reject ~5% of fair data at α = 0.05.
- **Invariants:** probabilities over all outcomes sum to exactly 1; each EV step can only go
  down; at the break-even jackpot, EV = $1.
- **Ingest on fixtures** in both source formats, including deliberately broken rows.

---

## Deploying to GitHub Pages

The site is the `docs/` folder at the repository root. Settings → Pages → *Deploy from a
branch* → `main` / `/docs`. Re-run `python -m lottery.build --ingest`, commit `data/` and
`docs/data/`, and push to update it.

---

Not affiliated with any lottery. Educational only. Data: NY Open Data.
