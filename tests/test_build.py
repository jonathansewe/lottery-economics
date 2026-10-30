import json
import math

from lottery import build, states


def test_build_writes_valid_json_without_data(tmp_path):
    out, data = tmp_path / "out", tmp_path / "data"
    data.mkdir()
    build.build(out_dir=out, data_dir=data, histories=50)
    files = {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}
    assert set(files) == {"games.json", "ev.json", "stats.json", "simulation.json", "states.json"}
    assert files["stats.json"]["data_available"] is False
    sims = files["simulation.json"]["simulations"]
    assert {s["game"] for s in sims} == {"powerball", "mega_millions"}
    assert all(s["real"] is None for s in sims)
    head = files["ev.json"]["headline"]
    assert 0 < head["powerball"] < 1 and 0 < head["mega_millions"] < 1
    assert head["ny_numbers"] == 0.5


def test_ev_json_reference_matches_math():
    ev = build.ev_json()["games"]["powerball"]
    ref = ev["reference"]
    # with no other tickets the split step changes nothing
    assert ref["with_split"]["total_per_dollar"] <= ref["after_tax"]["total_per_dollar"]
    assert math.isclose(sum(t["probability"] for t in ev["tiers"]), 1 / 24.87, rel_tol=1e-3)


def test_participation_counts_match_official_totals():
    js = states.jurisdictions()
    # Powerball: 45 states + DC + PR + USVI; Mega Millions: 45 states + DC + USVI
    assert sum(j["powerball"] for j in js) == 48
    assert sum(j["mega_millions"] for j in js) == 47
    assert {j["abbr"] for j in js if not j["powerball"]} == {"AL", "AK", "HI", "NV", "UT"}
    assert [j["abbr"] for j in js if j["deep_dive"]] == ["NY"]
    assert len({j["fips"] for j in js}) == len(js)
