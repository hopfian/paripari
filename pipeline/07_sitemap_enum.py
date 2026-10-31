#!/usr/bin/env python3
"""
07_sitemap_enum.py
------------------
Enumerates Crunchyroll's sitemap inventory (P1/P3 research):
- fetches all /sitemaps/series/*.xml shards  -> counts series URLs, extracts ids
- fetches all /sitemaps/episode/*.xml shards -> counts watch URLs, extracts episode ids
- saves inventories for later cross-validation of the full DB
Output: local/work/sitemaps/{series_ids.txt, episode_ids.txt, sitemap_stats.json}
"""
import re
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("PARI_WORK", os.path.join(ROOT, "local", "work"))
CENSUS = os.environ.get("PARI_CENSUS", os.path.join(ROOT, "census", "2026.10-BD"))
OUT = os.path.join(WORK, "sitemaps")
os.makedirs(OUT, exist_ok=True)

def curl(url, timeout=30):
    r = subprocess.run(["curl", "-s", "-S", "--compressed", "--max-time", str(timeout),
                        "-A", UA, url], capture_output=True, text=True)
    return r.stdout

# ---- load index, pick content shards ----
index = curl("https://www.crunchyroll.com/sitemap.xml")
locs = re.findall(r"<loc>([^<]+)</loc>", index)
series_shards = [u for u in locs if "/sitemaps/series/" in u]
episode_shards = [u for u in locs if "/sitemaps/episode/" in u]
print(f"index: {len(locs)} child sitemaps -> series shards: {len(series_shards)}, episode shard-pages: {len(episode_shards)}")

def fetch_count(urls):
    stats = {}
    def one(u):
        body = curl(u)
        n = body.count("<loc>")
        return u, n, body
    bodies = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(one, u) for u in urls]
        for f in as_completed(futs):
            try:
                u, n, body = f.result()
                stats[u] = n
                bodies[u] = body
            except Exception as e:
                print("shard failed:", u, e)
    return stats, bodies

print("fetching series shards...")
s_stats, s_bodies = fetch_count(series_shards)
print("fetching episode shards...")
e_stats, e_bodies = fetch_count(episode_shards)

series_urls = []
for u in sorted(s_bodies):
    series_urls += re.findall(r"<loc>(https://www\.crunchyroll\.com/series/[^<]+)</loc>", s_bodies[u])
episode_urls = []
for u in sorted(e_bodies):
    episode_urls += re.findall(r"<loc>(https://www\.crunchyroll\.com/watch/[^<]+)</loc>", e_bodies[u])

series_ids = sorted({m.group(1) for u in series_urls for m in [re.match(r"https://www\.crunchyroll\.com/series/([A-Z0-9]+)/", u)] if m})
episode_ids = sorted({m.group(1) for u in episode_urls for m in [re.match(r"https://www\.crunchyroll\.com/watch/([A-Z0-9]+)/", u)] if m})

with open(os.path.join(OUT, "series_urls.txt"), "w") as f:
    f.write("\n".join(sorted(set(series_urls))))
with open(os.path.join(OUT, "episode_urls.txt"), "w") as f:
    f.write("\n".join(sorted(set(episode_urls))))
with open(os.path.join(OUT, "series_ids.txt"), "w") as f:
    f.write("\n".join(series_ids))
with open(os.path.join(OUT, "episode_ids.txt"), "w") as f:
    f.write("\n".join(episode_ids))

stats = {
    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "series_shard_urls": len(series_shards),
    "series_urls_total": len(series_urls),
    "series_urls_unique": len(set(series_urls)),
    "series_ids_unique": len(series_ids),
    "episode_shard_urls": len(episode_shards),
    "episode_urls_total": len(episode_urls),
    "episode_urls_unique": len(set(episode_urls)),
    "episode_ids_unique": len(episode_ids),
    "per_shard_counts": {
        "series": {unquote(u).split("/")[-1].split("?")[0]: n for u, n in sorted(s_stats.items())},
        "episode": {unquote(u).split("/")[-1].split("?")[0] + "|" + (unquote(u).split("?page=")[-1] if "?page=" in u else "0"): n for u, n in sorted(e_stats.items())},
    },
}
with open(os.path.join(OUT, "sitemap_stats.json"), "w") as f:
    json.dump(stats, f, indent=2)

print(f"\nSERIES : {len(series_urls)} URLs, {len(set(series_urls))} unique -> {len(series_ids)} unique series ids")
print(f"EPISODE: {len(episode_urls)} URLs, {len(set(episode_urls))} unique -> {len(episode_ids)} unique watch-page ids")
print(f"\nSaved inventories to {OUT}")
