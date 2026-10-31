"""Game rules ("matrices") with effective date ranges.

A *matrix* is the shape of a draw: pick `white_drawn` balls from 1..`white_pool`
without replacement, plus one special ball from 1..`special_pool`. Rules change
over time, so every rule set is an *era* with a first and last draw date, and
every historical draw is tagged with the era it belongs to (see ingest.py).
Statistics are never computed across eras: a ball numbered 70 can't appear in
a 1..56 era, so pooling eras would make the counts meaningless.

Verification legend (`verified` field), as of 2026-10-30:
  "search-snippet"  value read from a search snippet of the official URL listed
                    (the official sites themselves were blocked from the
                    build container — see PLAN.md)
  "memory"          from general knowledge; NOT verified in this build
  "derived"         follows mathematically from verified facts
Prize tables are only filled in where the amounts were verified. Older eras
carry the matrix (needed to validate and analyse draws) but no prize table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

JACKPOT = "JACKPOT"          # Powerball / Mega Millions: rolling jackpot (EV needs a jackpot input)
PARIMUTUEL = "PARIMUTUEL"    # prize = a share of the draw's prize pool (NY Lotto, Take 5)
FREE_PLAY = "FREE_PLAY"      # prize is a free ticket worth the play price (Take 5 match 2)


@dataclass(frozen=True)
class Tier:
    white: int            # white balls (or keno numbers) matched
    special: int | None   # 1/0: special or bonus ball matched or not; None = doesn't matter
    prize: object         # dollars (cash value for "for life" prizes), JACKPOT, PARIMUTUEL or FREE_PLAY
    official_odds: float | None  # "1 in X" as published; None = not found in an official source
    verified: bool = True        # False = prize amount not confirmed from an official page
    label: str = ""              # display text when the prize isn't a plain dollar amount
    pool_share: float | None = None  # pari-mutuel: share of the prize pool (None = unknown)


@dataclass(frozen=True)
class Era:
    game: str
    era_id: str
    label: str
    first_draw: date
    last_draw: date | None      # None = still current
    white_pool: int
    white_drawn: int
    special_pool: int | None
    price: float
    tiers: tuple = ()           # empty when the prize table is not verified
    multiplier: dict = field(default_factory=dict)  # {factor: probability}
    starting_jackpot: float | None = None
    official_overall_odds: float | None = None
    sources: tuple = ()
    verified: str = "memory"
    notes: str = ""
    kind: str = "lotto"                 # lotto | digits | keno
    bonus: bool = False                 # special ball drawn from the same pool (NY Lotto)
    prize_pool_fraction: float | None = None  # pari-mutuel games: share of sales paid as prizes
    plays: tuple = ()                   # digits games: play types
    spot_tables: dict = field(default_factory=dict)  # keno: {spots: (Tier(matches, None, prize, odds), ...)}
    spot_overall: dict = field(default_factory=dict)  # keno: {spots: official overall "1 in X"}
    plays_per_dollar: float = 1.0       # NY Lotto: $1 buys two plays
    unverified: tuple = ()              # names of fields NOT confirmed from an official page

    def contains(self, d: date) -> bool:
        return d >= self.first_draw and (self.last_draw is None or d <= self.last_draw)

    @property
    def matrix(self) -> str:
        if self.kind == "digits":
            return f"{self.white_drawn} digits 0-9"
        if self.kind == "keno":
            return f"{self.white_drawn} of 1-{self.white_pool} drawn"
        if self.bonus:
            return f"{self.white_drawn}/{self.white_pool} + bonus"
        if self.special_pool is None:
            return f"{self.white_drawn}/{self.white_pool}"
        return f"{self.white_drawn}/{self.white_pool} + 1/{self.special_pool}"


# ---------------------------------------------------------------------------
# Powerball
# ---------------------------------------------------------------------------
POWERBALL_ERAS = (
    Era(
        game="powerball", era_id="pb_2009", label="Powerball 5/59 + 1/39 ($1)",
        first_draw=date(2009, 1, 7), last_draw=date(2012, 1, 14),
        white_pool=59, white_drawn=5, special_pool=39, price=1.0,
        verified="memory",
        notes="Only the matrix is used (to validate and analyse 2010-2012 draws). "
              "NY Open Data starts at 2010-02-03.",
    ),
    Era(
        game="powerball", era_id="pb_2012", label="Powerball 5/59 + 1/35 ($2)",
        first_draw=date(2012, 1, 15), last_draw=date(2015, 10, 6),
        white_pool=59, white_drawn=5, special_pool=35, price=2.0,
        sources=("https://www.powerball.com/draw-result?gc=powerball&date=2012-01-25",),
        verified="memory (Powerball numbers 25 and 5 on Jan 2012 result pages are consistent with 1-35)",
    ),
    Era(
        game="powerball", era_id="pb_2015", label="Powerball 5/69 + 1/26 ($2)",
        # "The current game matrix (5/69 + 1/26) debuted on Oct. 7, 2015"
        # https://www.powerball.com/media-center
        # Prize chart + odds: https://www.powerball.com/powerball-prize-chart
        # NY sheet: https://edit.nylottery.ny.gov/sites/default/files/2020-03/Powerball_Odds_and_Prizes_0.pdf
        # US price/matrix unchanged by the July 2026 UK expansion:
        # https://www.powerball.com/powerball-launch-set-in-the-uk-for-july-21-first-drawing-to-follow
        first_draw=date(2015, 10, 7), last_draw=None,
        white_pool=69, white_drawn=5, special_pool=26, price=2.0,
        tiers=(
            Tier(5, 1, JACKPOT, 292_201_338.00),
            Tier(5, 0, 1_000_000, 11_688_053.52),
            Tier(4, 1, 50_000, 913_129.18),
            Tier(4, 0, 100, 36_525.17),
            Tier(3, 1, 100, 14_494.11),
            Tier(3, 0, 7, 579.76),
            Tier(2, 1, 7, 701.33),
            Tier(1, 1, 4, 91.98),
            Tier(0, 1, 4, 38.32),
        ),
        starting_jackpot=20_000_000,
        official_overall_odds=24.87,
        sources=(
            "https://www.powerball.com/powerball-prize-chart",
            "https://www.powerball.com/media-center",
            "https://edit.nylottery.ny.gov/sites/default/files/2020-03/Powerball_Odds_and_Prizes_0.pdf",
        ),
        verified="search-snippet: matrix, start date, $2 price, prize amounts, odds for "
                 "jackpot, 5+0, 4+1, 4+0, 3+1, 0+1 tiers and overall 1 in 24.87. "
                 "Odds for 3+0, 2+1, 1+1 tiers from memory; the tests prove all of "
                 "them equal the exact combinatorial values. Starting jackpot $20M seen "
                 "in a ~2025 powerball.com release, not a rules page.",
        notes="Base $2 play only. Power Play, Double Play and the UK lower-tier "
              "prize structure are out of scope. Non-jackpot prizes can become "
              "pari-mutuel in rare high-liability draws, and California pays all "
              "prizes pari-mutuel; both are ignored here.",
    ),
)

# ---------------------------------------------------------------------------
# Mega Millions
# ---------------------------------------------------------------------------
# Mega Millions draws on Tuesdays and Fridays. Rule-change announcements give the
# date *sales* started (often a Saturday); the era boundary only has to fall
# between the last old-format draw and the first new-format draw, and ingest.py
# rejects any draw whose numbers fall outside its era's pools.
MEGA_MILLIONS_ERAS = (
    Era(
        game="mega_millions", era_id="mm_2002", label="Mega Millions 5/52 + 1/52 ($1)",
        first_draw=date(2002, 5, 17), last_draw=date(2005, 6, 21),
        white_pool=52, white_drawn=5, special_pool=52, price=1.0,
        verified="memory (first draw 2002-05-17 matches the NY Open Data coverage start)",
    ),
    Era(
        game="mega_millions", era_id="mm_2005", label="Mega Millions 5/56 + 1/46 ($1)",
        first_draw=date(2005, 6, 22), last_draw=date(2013, 10, 18),
        white_pool=56, white_drawn=5, special_pool=46, price=1.0,
        verified="memory",
    ),
    Era(
        game="mega_millions", era_id="mm_2013", label="Mega Millions 5/75 + 1/15 ($1)",
        # "white balls will increase to 75 and ... Mega Ball will decrease to 15";
        # new matrix from the October 22, 2013 drawing.
        # https://www.megamillions.com/news/2013/mega-millions-to-become-even-more-mega-beginning.aspx
        first_draw=date(2013, 10, 19), last_draw=date(2017, 10, 27),
        white_pool=75, white_drawn=5, special_pool=15, price=1.0,
        official_overall_odds=15,
        sources=("https://www.megamillions.com/news/2013/mega-millions-to-become-even-more-mega-beginning.aspx",),
        verified="search-snippet: matrix and Oct 2013 start",
    ),
    Era(
        game="mega_millions", era_id="mm_2017", label="Mega Millions 5/70 + 1/25 ($2)",
        # "$1 to $2 ... five numbers from 1 to 70, and one Mega Ball number from 1 to 25",
        # changes begin Oct. 28, 2017 (sales); first draw under it Tue Oct 31, 2017.
        # https://www.megamillions.com/news/2017/mega-millions-enhanced-starting-jackpots-increase.aspx
        # Prize/odds sheet (this era): https://edit.nylottery.ny.gov/sites/default/files/2020-03/Mega_Millions_Odds_and_Prizes_0.pdf
        # Last draw before the 2025 game: Fri Apr 4, 2025 (trivia page: "through April 4, 2025")
        # https://www.megamillions.com/About/Mega-Millions-Trivia.aspx
        first_draw=date(2017, 10, 28), last_draw=date(2025, 4, 7),
        white_pool=70, white_drawn=5, special_pool=25, price=2.0,
        tiers=(
            Tier(5, 1, JACKPOT, 302_575_350),
            Tier(5, 0, 1_000_000, 12_607_306),
            Tier(4, 1, 10_000, 931_001),
            Tier(4, 0, 500, 38_792),
            Tier(3, 1, 200, 14_547),
            Tier(3, 0, 10, 606),
            Tier(2, 1, 10, 693),
            Tier(1, 1, 4, 89),
            Tier(0, 1, 2, 37),
        ),
        official_overall_odds=24,
        sources=(
            "https://www.megamillions.com/news/2017/mega-millions-enhanced-starting-jackpots-increase.aspx",
            "https://edit.nylottery.ny.gov/sites/default/files/2020-03/Mega_Millions_Odds_and_Prizes_0.pdf",
        ),
        verified="search-snippet: matrix, $2 price, start, overall 1 in 24, 4+1 odds 1 in 931,001. "
                 "Other prize amounts/odds from memory (odds proven exact by the tests).",
        notes="Historical era; shown for comparison. Megaplier add-on ignored.",
    ),
    Era(
        game="mega_millions", era_id="mm_2025", label="Mega Millions 5/70 + 1/24 ($5)",
        # https://www.megamillions.com/how-to-play.aspx
        # https://www.megamillions.com/Media-Center/MegaMillions_New_Prize_Matrix.aspx
        # https://www.megamillions.com/News/2025/New-Mega-Millions%C2%AE-arrives-in-April.aspx
        # "entered service on April 8, 2025"; starting jackpot $50M:
        # https://www.megamillions.com/News/2025/Enhanced-Mega-Millions-Delivers-First-Jackpot-Win.aspx
        first_draw=date(2025, 4, 8), last_draw=None,
        white_pool=70, white_drawn=5, special_pool=24, price=5.0,
        tiers=(
            Tier(5, 1, JACKPOT, 290_472_336),
            Tier(5, 0, 1_000_000, 12_629_232),
            Tier(4, 1, 10_000, 893_761),
            Tier(4, 0, 500, 38_859),
            Tier(3, 1, 200, 13_965),
            Tier(3, 0, 10, 607),
            Tier(2, 1, 10, 665),
            Tier(1, 1, 7, 86),
            Tier(0, 1, 5, 35),
        ),
        # Built-in multiplier on every non-jackpot prize. Published odds:
        # 2X 1 in 2.13, 3X 1 in 3.2, 4X 1 in 8, 5X 1 in 16, 10X 1 in 32.
        # Those are exactly 15/32, 10/32, 4/32, 2/32, 1/32 (sum = 1), so we use
        # the exact fractions. Expected multiplier = 96/32 = 3.0.
        multiplier={2: 15 / 32, 3: 10 / 32, 4: 4 / 32, 5: 2 / 32, 10: 1 / 32},
        starting_jackpot=50_000_000,
        official_overall_odds=23,
        sources=(
            "https://www.megamillions.com/how-to-play.aspx",
            "https://www.megamillions.com/Media-Center/MegaMillions_New_Prize_Matrix.aspx",
            "https://www.megamillions.com/News/2025/New-Mega-Millions%C2%AE-arrives-in-April.aspx",
        ),
        verified="search-snippet: $5 price, 1-24 Mega Ball, April 8 2025 start, all base "
                 "prize amounts, jackpot/4+1/3+0/2+1 odds, overall 1 in 23, multiplier odds, "
                 "$50M starting jackpot. Remaining tier odds proven exact by the tests.",
        notes="Megaplier removed; multiplier is built in to every $5 play.",
    ),
)

# ---------------------------------------------------------------------------
# NY Numbers (3 digits, each 0-9, drawn independently = with replacement)
# ---------------------------------------------------------------------------
# https://edit.nylottery.ny.gov/sites/default/files/2020-03/Numbers_Odds_and_Prizes.pdf
# Per $1 play: Straight $500 (1 in 1,000); 3-way box $160 (1 in 333);
# 6-way box $80 (1 in 167).  verified: search-snippet of that NY Lottery PDF.
NUMBERS_ERA = Era(
    game="ny_numbers", era_id="numbers_1980", label="NY Numbers 000-999",
    first_draw=date(1980, 9, 2), last_draw=None,
    white_pool=10, white_drawn=3, special_pool=None, price=1.0,
    sources=("https://edit.nylottery.ny.gov/sites/default/files/2020-03/Numbers_Odds_and_Prizes.pdf",),
    verified="search-snippet of the NY Lottery Numbers odds & prizes PDF (2020)",
    notes="Digits are drawn with replacement, so every 3-digit result 000-999 has "
          "probability 1/1000. $0.50 plays pay half.",
)

NUMBERS_PLAYS = (
    # name, ways (permutations covered), prize per $1, official "1 in"
    {"play": "straight", "label": "Straight (exact order)", "ways": 1, "prize": 500, "official_odds": 1000},
    {"play": "box_3way", "label": "3-way box (two digits alike, any order)", "ways": 3, "prize": 160, "official_odds": 333},
    {"play": "box_6way", "label": "6-way box (three different digits, any order)", "ways": 6, "prize": 80, "official_odds": 167},
)

# ---------------------------------------------------------------------------
# Win 4 (4 digits, with replacement). Same NY Open Data dataset as Numbers.
# ---------------------------------------------------------------------------
# No official Win 4 odds/prize sheet was found by search: payouts are UNVERIFIED
# (general knowledge). The odds themselves are exact counting and need no source.
WIN4_PLAYS = (
    {"play": "straight", "label": "Straight (exact order)", "ways": 1, "prize": 5000, "official_odds": None, "verified": False},
    {"play": "box_24way", "label": "24-way box (four different digits)", "ways": 24, "prize": 200, "official_odds": None, "verified": False},
    {"play": "box_12way", "label": "12-way box (one pair)", "ways": 12, "prize": 400, "official_odds": None, "verified": False},
    {"play": "box_6way", "label": "6-way box (two pairs)", "ways": 6, "prize": 800, "official_odds": None, "verified": False},
    {"play": "box_4way", "label": "4-way box (three alike)", "ways": 4, "prize": 1200, "official_odds": None, "verified": False},
)
WIN4_ERA = Era(
    game="win4", era_id="win4_1980", label="Win 4 0000-9999",
    first_draw=date(1980, 9, 2), last_draw=None,
    white_pool=10, white_drawn=4, special_pool=None, price=1.0, kind="digits", plays=WIN4_PLAYS,
    sources=("https://nylottery.ny.gov/draw-games/?game=win4",),
    verified="game listed on nylottery.ny.gov; payouts NOT verified",
    unverified=("first_draw", "prizes"),
    notes="Era start is the dataset start (Numbers/Win-4 share one dataset); Win 4's own "
          "launch date was not verified. $0.50 plays pay half.",
)
NUMBERS_ERA = Era(**{**NUMBERS_ERA.__dict__, "kind": "digits", "plays": NUMBERS_PLAYS})

# ---------------------------------------------------------------------------
# NY Lotto: 6 of 59 + a bonus ball drawn from the remaining 53. $1 = two plays.
# ---------------------------------------------------------------------------
# https://edit.nylottery.ny.gov/sites/default/files/2020-03/Lotto_Odds_and_Prizes.pdf
# https://test.nylottery.ny.gov/lotto  ("40% of sales ... allocated as prize money. The Jackpot is 75%")
# Tier shares 75 / 7.25 / 5.5 / 6.25 / 6 % of the pool:
# https://gaming.ny.gov/system/files/documents/2026/06/2026-06-03-lotto-published-odds-correction-proposed-consensus.pdf
# That 2026 proposal "corrects" the 3rd-prize odds to 1 in 144,418.98; exact counting
# gives 312 / C(59,6) = 1 in 144,414.98, which matches the 2020 sheet. Unresolved.
LOTTO_ERA = Era(
    game="ny_lotto", era_id="lotto_2001", label="NY Lotto 6/59 + bonus",
    first_draw=date(2001, 9, 12), last_draw=None,
    white_pool=59, white_drawn=6, special_pool=59, bonus=True, price=0.5, plays_per_dollar=2,
    prize_pool_fraction=0.40,
    tiers=(
        Tier(6, 0, PARIMUTUEL, 45_057_474, label="Jackpot (pari-mutuel)", pool_share=0.75),
        Tier(5, 1, PARIMUTUEL, 7_509_579, label="2nd prize (pari-mutuel)", pool_share=0.0725),
        Tier(5, 0, PARIMUTUEL, 144_414.98, label="3rd prize (pari-mutuel)", pool_share=0.055),
        Tier(4, None, PARIMUTUEL, None, label="4th prize (pari-mutuel)", pool_share=0.0625),
        Tier(3, None, PARIMUTUEL, 96.17, label="5th prize (pari-mutuel)", pool_share=0.06),
    ),
    official_overall_odds=92.05,
    sources=("https://edit.nylottery.ny.gov/sites/default/files/2020-03/Lotto_Odds_and_Prizes.pdf",
             "https://test.nylottery.ny.gov/lotto",
             "https://gaming.ny.gov/system/files/documents/2026/06/2026-06-03-lotto-published-odds-correction-proposed-consensus.pdf"),
    verified="search-snippet: matrix + bonus rule, 40% prize pool, tier shares, odds for jackpot, "
             "3rd, 5th, overall 1 in 92.05 per play (46.02 per $1). 2nd/4th odds exact counting.",
    unverified=("first_draw",),
    notes="Data and matrix since 2001-09-12 (the 6/59 format). NY Lotto itself is older; earlier "
          "formats are not in NY Open Data. The 'Extra' feature (2007-2010) is ignored.",
)

# ---------------------------------------------------------------------------
# Take 5: 5 of 39, $1, drawn twice daily. 50% of sales to prizes, jackpot 20% of that.
# ---------------------------------------------------------------------------
# https://nylottery.ny.gov/draw-game/?game=take5
# https://edit.nylottery.ny.gov/sites/default/files/2020-01/Take5_Odds_and_Prizes.pdf
TAKE5_ERA = Era(
    game="take5", era_id="take5_1992", label="Take 5 5/39",
    first_draw=date(1992, 1, 17), last_draw=None,
    white_pool=39, white_drawn=5, special_pool=None, price=1.0, prize_pool_fraction=0.50,
    tiers=(
        Tier(5, None, PARIMUTUEL, 575_757, label="Jackpot (pari-mutuel)", pool_share=0.20),
        Tier(4, None, PARIMUTUEL, 3_386.81, label="2nd prize (pari-mutuel, ~$500)"),
        Tier(3, None, PARIMUTUEL, 102.63, label="3rd prize (pari-mutuel, ~$25)"),
        Tier(2, None, FREE_PLAY, 9.62, label="Free Quick Pick ($1)"),
    ),
    official_overall_odds=None,
    sources=("https://nylottery.ny.gov/draw-game/?game=take5",
             "https://edit.nylottery.ny.gov/sites/default/files/2020-01/Take5_Odds_and_Prizes.pdf"),
    verified="search-snippet: 50% prize pool, jackpot 20% of pool, odds per tier, free play for 2.",
    unverified=("first_draw", "pool shares of 2nd/3rd prizes", "draw times"),
    notes="NY's page gives overall odds 1 in 8.7; exact counting gives 1 in 8.77 (reported). "
          "The 1-39 matrix is assumed for the whole dataset; ingest rejects any draw outside it.",
)

# ---------------------------------------------------------------------------
# Pick 10: player picks 10 of 80; 20 drawn. Fixed prizes. $1.
# ---------------------------------------------------------------------------
# https://nylottery.ny.gov/pick-10 ; https://edit.nylottery.ny.gov/sites/default/files/2020-01/Pick10_Odds_and_Prizes.pdf
PICK10_ERA = Era(
    game="pick10", era_id="pick10_1987", label="Pick 10 (20 of 80 drawn)",
    first_draw=date(1987, 1, 12), last_draw=None,
    white_pool=80, white_drawn=20, special_pool=None, price=1.0, kind="keno",
    spot_tables={10: (
        Tier(10, None, 500_000, 8_911_711), Tier(9, None, 6_000, 163_381), Tier(8, None, 300, 7_384),
        Tier(7, None, 40, 621), Tier(6, None, 10, 87), Tier(0, None, 4, 22),
    )},
    spot_overall={10: 17.00},
    sources=("https://nylottery.ny.gov/pick-10",
             "https://edit.nylottery.ny.gov/sites/default/files/2020-01/Pick10_Odds_and_Prizes.pdf"),
    verified="search-snippet: every prize, every tier's odds, overall 1 in 17.00, $1, 1-80.",
    unverified=("first_draw",),
    notes="Top prize has a $5,000,000 liability cap (shared if more than 10 winners); ignored in EV. "
          "Every tier matches the published odds, but the published overall '1 in 17.00' is off: "
          "the exact overall is 1 in 16.94.",
)

# ---------------------------------------------------------------------------
# Quick Draw (keno): 20 of 80 every few minutes; player picks 1-10 spots. $1 base play.
# ---------------------------------------------------------------------------
# https://edit.nylottery.ny.gov/sites/default/files/2020-03/QuickDraw_Odds_and_Prizes_0.pdf
# https://test.nylottery.ny.gov/quick-draw   (test subdomain; same figures)
_u = dict(verified=False)
QUICKDRAW_ERA = Era(
    game="quick_draw", era_id="qd_2013", label="Quick Draw (20 of 80 drawn)",
    first_draw=date(2013, 1, 1), last_draw=None,
    white_pool=80, white_drawn=20, special_pool=None, price=1.0, kind="keno",
    spot_tables={
        10: (Tier(10, None, 100_000, None), Tier(9, None, 5_000, None), Tier(8, None, 300, None),
             Tier(7, None, 45, None, **_u), Tier(6, None, 10, None, **_u), Tier(5, None, 2, None, **_u),
             Tier(0, None, 5, None)),
        9: (Tier(9, None, 30_000, None), Tier(8, None, 3_000, None), Tier(7, None, 125, None, **_u),
            Tier(6, None, 20, None, **_u), Tier(5, None, 5, None, **_u), Tier(0, None, 2, None)),
        8: (Tier(8, None, 10_000, None), Tier(7, None, 550, None), Tier(6, None, 75, None),
            Tier(5, None, 6, None), Tier(0, None, 2, None)),
        7: (Tier(7, None, 5_000, None), Tier(6, None, 100, None), Tier(5, None, 20, None),
            Tier(4, None, 2, None), Tier(0, None, 1, None)),
        6: (Tier(6, None, 1_000, None), Tier(5, None, 55, None), Tier(4, None, 6, None), Tier(3, None, 1, None)),
        5: (Tier(5, None, 300, None), Tier(4, None, 20, None), Tier(3, None, 2, None)),
        4: (Tier(4, None, 55, None), Tier(3, None, 5, None), Tier(2, None, 1, None)),
        3: (Tier(3, None, 23, None, **_u), Tier(2, None, 2, None, **_u)),
        2: (Tier(2, None, 10, None, **_u),),
        1: (Tier(1, None, 2, None, **_u),),
    },
    spot_overall={10: 9.05, 9: 9.74, 8: 9.17, 7: 5.46, 6: 6.19, 5: 10.34, 4: 3.86, 3: 6.55, 2: 16.63, 1: 4.00},
    sources=("https://edit.nylottery.ny.gov/sites/default/files/2020-03/QuickDraw_Odds_and_Prizes_0.pdf",
             "https://test.nylottery.ny.gov/quick-draw"),
    verified="search-snippet: overall odds for all 10 spot games; prizes for 4-8 spots and the "
             "10/9/8/0 tiers of 10-spot and 9/8/0 of 9-spot. Others unverified (marked per tier).",
    unverified=("first_draw", "some prize amounts (per tier)"),
    notes="Era starts at the NY Open Data coverage (2013); Quick Draw itself is older. "
          "Extra, Money Dots and Bullseye add-ons are out of scope. Prize table as of the 2020 sheet.",
)

# ---------------------------------------------------------------------------
# Cash4Life (retired 2026-02-21) and Millionaire for Life (from 2026-02-22)
# ---------------------------------------------------------------------------
# https://edit.nylottery.ny.gov/sites/default/files/2020-01/Cash4Life_Odds_and_Prizes.pdf
# end date: https://gaming.ny.gov/system/files/documents/2025/11/transcript-11.18.2025_0.pdf
CASH4LIFE_ERA = Era(
    game="cash4life", era_id="c4l_2014", label="Cash4Life 5/60 + 1/4 ($2)",
    first_draw=date(2014, 6, 16), last_draw=date(2026, 2, 21),
    white_pool=60, white_drawn=5, special_pool=4, price=2.0,
    tiers=(
        Tier(5, 1, 7_000_000, 21_846_048, verified=False,
             label="$1,000 a day for life (valued at the $7M guaranteed minimum; cash option unverified)"),
        Tier(5, 0, 1_000_000, 7_282_016, verified=False,
             label="$1,000 a week for life (valued at $1M; unverified)"),
        Tier(4, 1, 2_500, 79_440),
        Tier(4, 0, 500, None, verified=False),
        Tier(3, 1, 100, None, verified=False),
        Tier(3, 0, 25, None, verified=False),
        Tier(2, 1, 10, None, verified=False),
        Tier(2, 0, 4, None, verified=False),
        Tier(1, 1, 2, 13),
    ),
    sources=("https://edit.nylottery.ny.gov/sites/default/files/2020-01/Cash4Life_Odds_and_Prizes.pdf",
             "https://gaming.ny.gov/system/files/documents/2025/11/transcript-11.18.2025_0.pdf"),
    verified="search-snippet: matrix, $2, end date, top/2nd/4+1/1+1 odds and the 4+1 and 1+1 prizes.",
    unverified=("first_draw", "lifetime prize cash values", "most lower-tier prizes"),
    notes="Retired game; NY Open Data dataset is static (2014-06-16 to 2026-02-21).",
)

# https://www.powerball.com/millionaire-for-life-prize-chart
# https://gaming.ny.gov/news/millionaire-lifetm-gives-new-york-lottery-players-new-chance-win-big-every-day
MFL_ERA = Era(
    game="millionaire_for_life", era_id="mfl_2026", label="Millionaire for Life 5/58 + 1/5 ($5)",
    first_draw=date(2026, 2, 22), last_draw=None,
    white_pool=58, white_drawn=5, special_pool=5, price=5.0,
    tiers=(
        Tier(5, 1, 18_000_000, 22_910_580, label="$1 million a year for life (cash option ~$18M, varies)"),
        Tier(5, 0, 2_200_000, 5_727_645, label="$100,000 a year for life (cash option ~$2.2M, varies)"),
        Tier(4, 1, 7_500, 86_455.02), Tier(4, 0, 500, 21_613.75),
        Tier(3, 1, 250, 1_662.60), Tier(3, 0, 50, 415.65),
        Tier(2, 1, 25, 97.80), Tier(2, 0, 8, 24.45), Tier(1, 1, 8, 15.65),
    ),
    # Exact overall odds are 1 in 8.4677: NY's "8.47" is the rounded value; powerball.com's
    # "8.46" is truncated.
    official_overall_odds=8.47,
    sources=("https://www.powerball.com/millionaire-for-life-prize-chart",
             "https://gaming.ny.gov/news/millionaire-lifetm-gives-new-york-lottery-players-new-chance-win-big-every-day"),
    verified="search-snippet: matrix, $5, start date, all prizes and odds (overall 1 in 8.46 on "
             "powerball.com, 8.47 in NY's release). Cash values from recent draw-result pages.",
    unverified=("cash values move with interest rates",),
    notes="Top prizes are paid for life (20-year minimum) or as a lump sum; EV uses the lump sum.",
)

ERAS = {e.era_id: e for e in (*POWERBALL_ERAS, *MEGA_MILLIONS_ERAS, NUMBERS_ERA, WIN4_ERA, LOTTO_ERA,
                              TAKE5_ERA, PICK10_ERA, QUICKDRAW_ERA, CASH4LIFE_ERA, MFL_ERA)}
GAMES = {
    "powerball": POWERBALL_ERAS,
    "mega_millions": MEGA_MILLIONS_ERAS,
    "ny_numbers": (NUMBERS_ERA,),
    "win4": (WIN4_ERA,),
    "ny_lotto": (LOTTO_ERA,),
    "take5": (TAKE5_ERA,),
    "pick10": (PICK10_ERA,),
    "quick_draw": (QUICKDRAW_ERA,),
    "cash4life": (CASH4LIFE_ERA,),
    "millionaire_for_life": (MFL_ERA,),
}
GAME_LABELS = {"powerball": "Powerball", "mega_millions": "Mega Millions", "ny_numbers": "NY Numbers",
               "win4": "Win 4", "ny_lotto": "NY Lotto", "take5": "Take 5", "pick10": "Pick 10",
               "quick_draw": "Quick Draw", "cash4life": "Cash4Life (retired)",
               "millionaire_for_life": "Millionaire for Life"}
RETIRED = {"cash4life"}


def era_for(game: str, d: date) -> Era | None:
    """Return the era a draw on date `d` belongs to, or None if no era covers it."""
    for era in GAMES[game]:
        if era.contains(d):
            return era
    return None


def current_era(game: str) -> Era:
    """The era in effect now, or the last one for a retired game."""
    eras = GAMES[game]
    return next((e for e in eras if e.last_draw is None), eras[-1])
