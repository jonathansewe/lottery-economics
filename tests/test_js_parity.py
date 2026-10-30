"""The calculator's JavaScript must agree with the Python engine."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lottery import build, config, rules
from lottery import math as lm

JS = Path(__file__).resolve().parent.parent / "docs" / "js" / "ev.js"
CASES = [(2e7, 0), (2e7, 1e7), (5e8, 8e7), (1.5e9, 3e8)]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("game", ["powerball", "mega_millions"])
def test_js_matches_python(game):
    g = build.ev_json()["games"][game]
    rate, tfm = config.combined_tax_rate(), config.TAX_FREE_PRIZE_MAX
    script = f"""
      const ev = require({json.dumps(str(JS))});
      const g = {json.dumps(g)};
      const cases = {json.dumps(CASES)};
      const out = cases.map(([j, n]) => ev.evBreakdown(g, {{jackpot: j, cashRatio: g.cash_ratio,
          tickets: n, taxRate: {rate}, taxFreeMax: {tfm}}}));
      out.push(ev.breakEvenJackpot(g, g.cash_ratio, {rate}, {tfm}));
      console.log(JSON.stringify(out));
    """
    res = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    era = rules.current_era(game)
    for (j, n), js in zip(CASES, res[:-1]):
        py = lm.ev_breakdown(era, j, tickets_sold=n)
        for step in ("advertised", "cash", "after_tax", "with_split"):
            assert js[step]["total_per_dollar"] == pytest.approx(py[step]["total_per_dollar"], rel=1e-12)
        assert js["p_shared"] == pytest.approx(py["p_shared"], rel=1e-12, abs=1e-15)
    assert res[-1] == pytest.approx(lm.break_even_jackpot(era, tax_rate=rate), rel=1e-12)
