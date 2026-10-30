"""Which US jurisdictions sell Powerball and Mega Millions, and their lottery sites.

Participation (verified by search-snippet, 2026-10-30):
  Powerball: "sold in 45 U.S. states, the District of Columbia, Puerto Rico,
  the U.S. Virgin Islands" (and, since July 2026, the United Kingdom).
    https://www.powerball.com/powerball-launch-set-in-the-uk-for-july-21-first-drawing-to-follow
  Mega Millions: "45 states, plus Washington, D.C. and the U.S. Virgin Islands".
    https://www.megamillions.com/Where-to-Play.aspx
  The five states without either game (Alabama, Alaska, Hawaii, Nevada, Utah)
  are inferred from those counts plus the official contact/where-to-play
  lists; these five have no state lottery at all.

Lottery website URLs are from general knowledge and were NOT verified in this
build (the sites were unreachable). Run `python scripts/check_links.py` to check
them before publishing.
"""

NO_LOTTERY = {"AL", "AK", "HI", "NV", "UT"}

# abbr: (FIPS, name, official lottery URL or None)
JURISDICTIONS = {
    "AL": ("01", "Alabama", None),
    "AK": ("02", "Alaska", None),
    "AZ": ("04", "Arizona", "https://www.arizonalottery.com"),
    "AR": ("05", "Arkansas", "https://www.myarkansaslottery.com"),
    "CA": ("06", "California", "https://www.calottery.com"),
    "CO": ("08", "Colorado", "https://www.coloradolottery.com"),
    "CT": ("09", "Connecticut", "https://www.ctlottery.org"),
    "DE": ("10", "Delaware", "https://www.delottery.com"),
    "DC": ("11", "District of Columbia", "https://dclottery.com"),
    "FL": ("12", "Florida", "https://www.floridalottery.com"),
    "GA": ("13", "Georgia", "https://www.galottery.com"),
    "HI": ("15", "Hawaii", None),
    "ID": ("16", "Idaho", "https://www.idaholottery.com"),
    "IL": ("17", "Illinois", "https://www.illinoislottery.com"),
    "IN": ("18", "Indiana", "https://hoosierlottery.com"),
    "IA": ("19", "Iowa", "https://www.ialottery.com"),
    "KS": ("20", "Kansas", "https://www.kslottery.com"),
    "KY": ("21", "Kentucky", "https://www.kylottery.com"),
    "LA": ("22", "Louisiana", "https://louisianalottery.com"),
    "ME": ("23", "Maine", "https://www.mainelottery.com"),
    "MD": ("24", "Maryland", "https://www.mdlottery.com"),
    "MA": ("25", "Massachusetts", "https://www.masslottery.com"),
    "MI": ("26", "Michigan", "https://www.michiganlottery.com"),
    "MN": ("27", "Minnesota", "https://www.mnlottery.com"),
    "MS": ("28", "Mississippi", "https://www.mslotteryhome.com"),
    "MO": ("29", "Missouri", "https://www.molottery.com"),
    "MT": ("30", "Montana", "https://www.montanalottery.com"),
    "NE": ("31", "Nebraska", "https://nelottery.com"),
    "NV": ("32", "Nevada", None),
    "NH": ("33", "New Hampshire", "https://www.nhlottery.com"),
    "NJ": ("34", "New Jersey", "https://www.njlottery.com"),
    "NM": ("35", "New Mexico", "https://www.nmlottery.com"),
    "NY": ("36", "New York", "https://nylottery.ny.gov"),
    "NC": ("37", "North Carolina", "https://nclottery.com"),
    "ND": ("38", "North Dakota", "https://www.lottery.nd.gov"),
    "OH": ("39", "Ohio", "https://www.ohiolottery.com"),
    "OK": ("40", "Oklahoma", "https://www.lottery.ok.gov"),
    "OR": ("41", "Oregon", "https://www.oregonlottery.org"),
    "PA": ("42", "Pennsylvania", "https://www.palottery.pa.gov"),
    "RI": ("44", "Rhode Island", "https://www.rilot.com"),
    "SC": ("45", "South Carolina", "https://www.sceducationlottery.com"),
    "SD": ("46", "South Dakota", "https://lottery.sd.gov"),
    "TN": ("47", "Tennessee", "https://www.tnlottery.com"),
    "TX": ("48", "Texas", "https://www.texaslottery.com"),
    "UT": ("49", "Utah", None),
    "VT": ("50", "Vermont", "https://vtlottery.com"),
    "VA": ("51", "Virginia", "https://www.valottery.com"),
    "WA": ("53", "Washington", "https://www.walottery.com"),
    "WV": ("54", "West Virginia", "https://wvlottery.com"),
    "WI": ("55", "Wisconsin", "https://wilottery.com"),
    "WY": ("56", "Wyoming", "https://www.wyolotto.com"),
    # Territories are not drawn on the Albers USA map; the site lists them below it.
    "PR": ("72", "Puerto Rico", None),
    "VI": ("78", "U.S. Virgin Islands", None),
}

POWERBALL_ONLY = {"PR"}  # sells Powerball but not Mega Millions


def jurisdictions() -> list[dict]:
    out = []
    for abbr, (fips, name, url) in JURISDICTIONS.items():
        sells = abbr not in NO_LOTTERY
        out.append({
            "abbr": abbr, "fips": fips, "name": name,
            "powerball": sells,
            "mega_millions": sells and abbr not in POWERBALL_ONLY,
            "lottery_url": url,
            "url_verified": False,
            "has_lottery": sells,
            "deep_dive": abbr == "NY",
        })
    return out
