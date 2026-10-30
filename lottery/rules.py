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

JACKPOT = "JACKPOT"


@dataclass(frozen=True)
class Tier:
    white: int            # white balls matched
    special: int          # 1 if the special ball (Powerball / Mega Ball) matched
    prize: object         # dollars, or JACKPOT
    official_odds: float  # "1 in X" as published; used by the tests


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

    def contains(self, d: date) -> bool:
        return d >= self.first_draw and (self.last_draw is None or d <= self.last_draw)

    @property
    def matrix(self) -> str:
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

ERAS = {e.era_id: e for e in (*POWERBALL_ERAS, *MEGA_MILLIONS_ERAS, NUMBERS_ERA)}
GAMES = {
    "powerball": POWERBALL_ERAS,
    "mega_millions": MEGA_MILLIONS_ERAS,
    "ny_numbers": (NUMBERS_ERA,),
}
GAME_LABELS = {"powerball": "Powerball", "mega_millions": "Mega Millions", "ny_numbers": "NY Numbers"}


def era_for(game: str, d: date) -> Era | None:
    """Return the era a draw on date `d` belongs to, or None if no era covers it."""
    for era in GAMES[game]:
        if era.contains(d):
            return era
    return None


def current_era(game: str) -> Era:
    return next(e for e in GAMES[game] if e.last_draw is None)
