import json
import math

import pytest

from lottery import build, config, states


def test_build_writes_valid_json_without_data(tmp_path):
    out, data = tmp_path / "out", tmp_path / "data"
    data.mkdir()
    build.build(out_dir=out, data_dir=data, histories=50, readme=None)
    files = {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}
    assert set(files) == {"games.json", "ev.json", "stats.json", "simulation.json", "states.json", "sales.json"}
    assert files["stats.json"]["data_available"] is False
    sims = files["simulation.json"]["simulations"]
    assert {s["game"] for s in sims} == {"powerball", "mega_millions"}
    assert all(s["real"] is None for s in sims)
    head = files["ev.json"]["headline"]
    assert 0 < head["powerball"] < 1 and 0 < head["mega_millions"] < 1
    assert head["ny_numbers"] == pytest.approx(0.5 * (1 - config.combined_tax_rate()))  # after tax owed


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


def test_findings_section_is_rewritten_in_place(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# x\n<!-- findings:start -->\nold\n<!-- findings:end -->\nafter\n")
    build.write_findings(readme, "new text")
    assert readme.read_text() == "# x\n<!-- findings:start -->\nnew text\n<!-- findings:end -->\nafter\n"


def test_findings_markdown_with_and_without_data():
    assert "pending" in build.findings_markdown({"data_available": False}, [])
    tests = [{"p_value": 0.3, "significant": False, "era_label": "E", "ball_set": "white"}] * 4
    text = build.findings_markdown({"data_available": True, "tests": tests}, [])
    assert "**None** fall below it" in text and "0.05/4" in text
