#!/usr/bin/env python3
"""
11_fetch_extras.py
------------------
Fetches the small reference/survey datasets for the full database:
  - seasonal tags (72 simulcast seasons)
  - discover/categories taxonomy (+ per-category sub_categories)
  - static configs: genres en-US, i18n audio/timed-text languages, cx-web config
  - browse A-Z index (prefix table)
  - games catalog page-data (Gatsby JSON)
  - news RSS snapshot (en-US)
  - subscription products seen on pages (cr_premium.1_month, cr_fan_pack.1_month)
Output: local/work/full-crawl/extras/*.json (+ .xml as json-wrapped text)
"""
import json
import os
import subprocess
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("PARI_WORK", os.path.join(ROOT, "local", "work"))
OUT = os.path.join(WORK, "full-crawl", "extras")
os.makedirs(OUT, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"

def curl(url, headers=None, method="GET", data=None, tries=3):
    last = (0, "")
    for a in range(1, tries + 1):
        cmd = ["curl", "-s", "-S", "--compressed", "--max-time", "30", "-X", method, url,
               "-H", f"User-Agent: {UA}", "-H", "Accept: application/json"]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        if data:
            cmd += ["-H", "Content-Type: application/x-www-form-urlencoded", "--data-raw", data]
        cmd += ["-w", "\n__STATUS__:%{http_code}"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        text = out.stdout.rstrip("\n")
        idx = text.rfind("\n__STATUS__:")
        status = int(text[idx + 12:]) if idx >= 0 else 0
        body = text[:idx] if idx >= 0 else text
        if status in (200, 404):
            return status, body
        last = (status, body)
        time.sleep(3 * a)
    return last

def token():
    st, b = curl("https://www.crunchyroll.com/auth/v1/token",
                 {"Authorization": "Basic Y3Jfd2ViOg=="}, method="POST", data="grant_type=client_id")
    assert st == 200, f"token HTTP {st}"
    return json.loads(b)["access_token"]

def save(name, status, body, wrap=None):
    obj = {"status": status, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "body": wrap(body) if wrap else body}
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"  {name}: HTTP {status}")

tok = token()
H = {"Authorization": f"Bearer {tok}"}

print("== extras ==")
# seasonal tags
st, b = curl("https://www.crunchyroll.com/content/v2/discover/seasonal_tags?locale=en-US", H)
save("seasonal_tags.json", st, json.loads(b) if st == 200 else b)

# categories taxonomy
st, b = curl("https://www.crunchyroll.com/content/v2/discover/categories?locale=en-US", H)
save("categories.json", st, json.loads(b) if st == 200 else b)
if st == 200:
    cats = json.loads(b).get("data", [])
    subs = {}
    for c in cats[:60]:
        st2, b2 = curl(f"https://www.crunchyroll.com/content/v2/discover/categories/{c['slug']}/sub_categories?locale=en-US", H)
        if st2 == 200:
            subs[c["slug"]] = json.loads(b2)
        time.sleep(0.4)
    save("sub_categories.json", 200, subs)

# static configs
for name, url in [
    ("genres_en-US.json", "https://static.crunchyroll.com/config/genres/en-US.json"),
    ("audio_languages.json", "https://static.crunchyroll.com/config/i18n/v3/audio_languages.json"),
    ("timed_text_languages.json", "https://static.crunchyroll.com/config/i18n/v3/timed_text_languages.json"),
    ("cx_web_config.json", "https://static.crunchyroll.com/config/cx-web/config.json"),
]:
    st, b = curl(url)
    try:
        parsed = json.loads(b)
    except Exception:
        parsed = b[:2000]
    save(name, st, parsed)

# browse A-Z index
st, b = curl("https://www.crunchyroll.com/content/v2/discover/browse/index?sort_by=alphabetical&ratings=true&locale=en-US", H)
save("browse_az_index.json", st, json.loads(b) if st == 200 else b)

# games (Gatsby page-data)
st, b = curl("https://www.crunchyroll.com/games/page-data/games/page-data.json")
try:
    parsed = json.loads(b)
except Exception:
    parsed = b[:2000]
save("games_page_data.json", st, parsed)

# news RSS snapshot
st, b = curl("https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss")
save("news_rss_en-US.json", st, b, wrap=lambda x: x)

# subscription products (public pricing surface seen on pages)
for pid in ["cr_premium.1_month", "cr_fan_pack.1_month"]:
    st, b = curl(f"https://www.crunchyroll.com/subs/v2/products/{pid}?locale=en-US", H)
    save(f"product_{pid.replace('.', '_')}.json", st, json.loads(b) if st == 200 and b.strip().startswith("{") else b[:2000])

print("extras done ->", OUT)
