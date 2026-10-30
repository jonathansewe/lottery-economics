"""Check every official lottery URL in lottery/states.py and the rule source URLs.

  python scripts/check_links.py

Prints one line per URL with its HTTP status. The URLs were written down without
network access, so run this before publishing and fix anything that is not 200.
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lottery import rules, states  # noqa: E402

urls = [j["lottery_url"] for j in states.jurisdictions() if j["lottery_url"]]
urls += sorted({u for e in rules.ERAS.values() for u in e.sources})
bad = 0
for url in urls:
    try:
        r = requests.get(url, timeout=20, allow_redirects=True, headers={"User-Agent": "lottery-economics link check"})
        status = r.status_code
        final = f" -> {r.url}" if r.url.rstrip("/") != url.rstrip("/") else ""
    except requests.RequestException as exc:
        status, final = "ERR", f" {type(exc).__name__}"
    ok = status == 200
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {status} {url}{final}")
print(f"\n{len(urls) - bad}/{len(urls)} OK")
sys.exit(1 if bad else 0)
