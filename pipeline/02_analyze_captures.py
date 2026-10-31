#!/usr/bin/env python3
"""
02_analyze_captures.py
----------------------
Scans captured network response bodies to identify the API call(s) that serve the
"Popular" feed, and reports their shape (pagination fields, item counts, etc.)
"""
import json
import os
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("PARI_WORK", os.path.join(ROOT, "local", "work"))
CENSUS = os.environ.get("PARI_CENSUS", os.path.join(ROOT, "census", "2026.10-BD"))
RAW = os.path.join(WORK, "browse-capture")
BODIES = os.path.join(RAW, "bodies")

idx = json.load(open(os.path.join(RAW, "bodies_index.json"), encoding="utf-8"))
reqs = json.load(open(os.path.join(RAW, "requests.json"), encoding="utf-8"))
req_by_file = {r.get("bodyFile"): r for r in reqs}

print(f"total bodies: {len(idx)}")
print("\n=== hosts x paths of JSON responses ===")
hp = Counter()
for e in idx:
    u = urlparse(e["url"])
    hp[(u.netloc, u.path)] += 1
for (host, path), n in hp.most_common(40):
    print(f"{n:4d}  {host}{path[:90]}")

print("\n=== crunchyroll API JSON bodies (non-static) ===")
api_entries = []
for e in idx:
    u = urlparse(e["url"])
    if "crunchyroll.com" not in u.netloc:
        continue
    if any(u.path.startswith(p) for p in ("/build/", "/fonts/")) or u.path.endswith((".js", ".css", ".woff2", ".png", ".svg", ".webp")):
        continue
    if not (e.get("mimeType") or "").lower().startswith(("application/json", "text/javascript", "application/javascript")) and "json" not in (e.get("mimeType") or "").lower():
        continue
    api_entries.append(e)

print(f"api-ish entries: {len(api_entries)}")
for e in api_entries[:80]:
    req = req_by_file.get(e["file"], {})
    print(f"  #{e['seq']:4d} {e['status']} {e['method']:6s} len={e['length']:8d} {e['url'][:150]}")
    if req.get("postData"):
        print(f"        POST: {req['postData'][:300]}")
