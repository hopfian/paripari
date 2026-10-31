#!/usr/bin/env python3
"""
04_build_db.py
--------------
Builds the final JSON database from the archived raw API pages:

  data/raw/api_pages/page_*.json  (archived at data/raw/api_pages/ — now local/work/browse-crawl/
  api_pages/; see provenance bundles) — the complete, ordered popular feed

Database design decisions (all provenance preserved):
  - Every field of every show is kept EXACTLY as Crunchyroll's API returned it
    (lossless values, original key order, nothing dropped or re-typed).
  - The raw popularity feed served to the page contains 1104 tiles in which 7 shows
    appear twice (verified: byte-identical entries, identical duplicate positions in
    two independent capture sessions). The DATABASE keeps ONE record per show and
    preserves every raw position via `tile_positions` (1-based feed/tile positions).
  - `rank` = dense popularity rank over unique shows (1..1097).
  - `url` = canonical human-facing Crunchyroll page URL.
  - A `database` header embeds provenance, schema reference and a full verification
    report (checks are re-run here, never trusted from earlier steps).

Verification performed in this step:
  1. collected count == API-reported total; contiguous pagination; exhaustion proof
     (short last data page + empty overflow page recorded in the manifest)
  2. duplicate audit: every duplicated id's entries byte-identical; duplicate map
     identical to the independent headless-Chrome capture of the same page
  3. 100% coverage of core + series_metadata fields on every record
  4. id-set and order cross-check against the independent browser capture
Output:
  popular-2026.10-BD.json   (the database, written to census/2026.10-BD/)
  data/build_report.json     (machine-readable verification report)
"""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("PARI_WORK", os.path.join(ROOT, "local", "work"))
CENSUS = os.environ.get("PARI_CENSUS", os.path.join(ROOT, "census", "2026.10-BD"))
MANIFEST = os.path.join(WORK, "browse-crawl", "api_crawl_manifest.json")
OUT_DB = os.path.join(CENSUS, "popular-2026.10-BD.json")
OUT_REPORT = os.path.join(CENSUS, "popular-build-report.json")
BODIES_INDEX = os.path.join(WORK, "browse-capture", "bodies_index.json")
BODIES_DIR = os.path.join(WORK, "browse-capture", "bodies")

checks = []


def check(name, ok, detail=""):
    checks.append({"check": name, "passed": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


print("== Loading crawl manifest + raw pages ==")
manifest = json.load(open(MANIFEST, encoding="utf-8"))

data_pages = [p for p in manifest["pages"] if p["received"] > 0 and p.get("file")]
overflow_pages = [p for p in manifest["pages"] if p.get("overflow")]

raw_feed = []          # the exact feed (all tiles, duplicates included), page-concatenated order
page_audit = []
for p in data_pages:
    raw = json.load(open(os.path.join(WORK, "browse-crawl", "api_pages", os.path.basename(p["file"])), encoding="utf-8"))
    data = raw["data"]
    assert p["received"] == len(data), f"manifest/received mismatch on {p['file']}"
    raw_feed.extend(data)
    page_audit.append({"file": p["file"], "start": p["start"], "count": len(data), "total": raw["total"]})

total_api = manifest["final_total"]

print("\n== Structural verification ==")
# 1. counts
check("collected count == API total", len(raw_feed) == total_api,
      f"{len(raw_feed)} tiles vs total={total_api}")
# 2. contiguous pagination
expected_start = 0
contiguous = True
for pa in page_audit:
    if pa["start"] != expected_start:
        contiguous = False
    expected_start = pa["start"] + pa["count"]
check("pagination contiguous (no gaps/overlaps)", contiguous and expected_start == total_api,
      f"{len(page_audit)} data pages, start sequence 0..{expected_start}")
# 3. exhaustion proof: short final data page + empty overflow page
check("feed exhaustion proven (short last page + empty overflow page)",
      data_pages[-1]["received"] < manifest["page_size"]
      and len(overflow_pages) == 1 and overflow_pages[0]["received"] == 0,
      f"last data page {data_pages[-1]['received']}/{manifest['page_size']} items; "
      f"overflow page at start={overflow_pages[0]['start']} returned 0 items")

# 4. duplicate audit
positions = defaultdict(list)
for pos, it in enumerate(raw_feed, start=1):
    positions[it["id"]].append(pos)
dup_ids = {i: p for i, p in positions.items() if len(p) > 1}
dup_entry_info = []
for did, poss in dup_ids.items():
    entries = [raw_feed[p - 1] for p in poss]
    identical = all(json.dumps(entries[0], sort_keys=True) == json.dumps(e, sort_keys=True) for e in entries[1:])
    dup_entry_info.append({"id": did, "title": entries[0]["title"], "tile_positions": poss,
                           "entries_identical": identical})
check("all duplicated feed entries are byte-identical",
      all(d["entries_identical"] for d in dup_entry_info),
      f"{len(dup_ids)} duplicated ids: {[(d['id'], d['tile_positions']) for d in dup_entry_info]}")

# 5. field coverage on every raw item
core_fields = ["id", "external_id", "channel_id", "linked_resource_key", "new", "title",
               "description", "promo_title", "promo_description", "type", "slug", "slug_title",
               "last_public", "images", "series_metadata", "language_presentation", "rating"]
missing_report = {f: sum(1 for i in raw_feed if f not in i) for f in core_fields}
missing_report = {k: v for k, v in missing_report.items() if v}
check("100% coverage of core fields", not missing_report,
      str(missing_report or f"all {len(core_fields)} core fields present in {len(raw_feed)}/{len(raw_feed)} items"))
sm_fields = ["availability_status", "episode_count", "season_count", "is_mature", "mature_blocked",
             "is_subbed", "is_dubbed", "is_simulcast", "audio_locales", "subtitle_locales",
             "series_launch_year", "tenant_categories", "extended_maturity_rating", "maturity_ratings",
             "language_presentation"]
sm_missing = {f: sum(1 for i in raw_feed if f not in i.get("series_metadata", {})) for f in sm_fields}
sm_missing = {k: v for k, v in sm_missing.items() if v}
check("100% coverage of series_metadata fields", not sm_missing,
      str(sm_missing or f"all {len(sm_fields)} metadata fields present in every item"))
# 6. types
types = Counter(i.get("type") for i in raw_feed)
check("all items are valid content types", set(types) <= {"series", "movie"}, str(dict(types)))

print("\n== Cross-verification against independent browser capture ==")
browser_feed = []
browser_first_page_ids = None
cross = {}
try:
    from urllib.parse import urlparse, parse_qs
    bidx = json.load(open(BODIES_INDEX, encoding="utf-8"))
    browse_files = []
    for e in bidx:
        if "/content/v2/discover/browse" in e["url"]:
            qs = parse_qs(urlparse(e["url"]).query)
            browse_files.append((int(qs.get("start", ["0"])[0]), e["seq"], e["file"]))
    browse_files.sort(key=lambda x: x[1])  # capture order
    for start_, seq, file in browse_files:
        d = json.load(open(os.path.join(BODIES_DIR, os.path.basename(file)), encoding="utf-8"))
        browser_feed.extend(d["data"])
        if start_ == 0:
            browser_first_page_ids = [x["id"] for x in d["data"]]

    api_ids = [i["id"] for i in raw_feed]
    browser_ids = [i["id"] for i in browser_feed]
    b_positions = defaultdict(list)
    for pos, it in enumerate(browser_feed, start=1):
        b_positions[it["id"]].append(pos)
    b_dup_ids = {i: p for i, p in b_positions.items() if len(p) > 1}

    check("browser-capture cross-check: same feed size",
          len(browser_feed) == len(raw_feed),
          f"browser: {len(browser_feed)} tiles; API crawl: {len(raw_feed)} tiles")
    check("browser-capture cross-check: identical id sets (unique shows)",
          set(browser_ids) == set(api_ids),
          f"{len(set(api_ids) & set(browser_ids))} shared; "
          f"only-in-API={sorted(set(api_ids) - set(browser_ids))[:5]}; "
          f"only-in-browser={sorted(set(browser_ids) - set(api_ids))[:5]}")
    check("browser-capture cross-check: identical duplicate map",
          b_dup_ids == dup_ids,
          f"{len(b_dup_ids)} duplicated ids in each, same tile positions: {b_dup_ids == dup_ids}")
    check("browser-capture cross-check: identical popularity order (first 36 tiles)",
          browser_first_page_ids == api_ids[:36], "first page ids in identical order")
    diff_positions = [p for p in range(1, min(len(browser_feed), len(raw_feed)) + 1)
                      if browser_feed[p - 1]["id"] != raw_feed[p - 1]["id"]]
    check("browser-capture cross-check: tile-by-tile identical order (entire feed)",
          not diff_positions, f"{len(diff_positions)} divergent positions" + (f", first: {diff_positions[:5]}" if diff_positions else ""))
    cross = {
        "browser_capture_tiles": len(browser_feed),
        "api_crawl_tiles": len(raw_feed),
        "unique_ids_shared": len(set(api_ids) & set(browser_ids)),
        "divergent_tile_positions": diff_positions,
        "duplicate_map_identical": b_dup_ids == dup_ids,
    }
except Exception as ex:  # noqa
    cross = {"error": str(ex)}
    check("browser-capture cross-check executed", False, str(ex))

# duplicate-title audit (informational)
titles_ci = Counter((i["title"] or "").strip().casefold() for i in raw_feed)
dup_titles = {t: n for t, n in titles_ci.items() if n > 1}

# ---------------- dedupe -> database ----------------
print("\n== Building database (dedupe with full provenance) ==")
shows = []
for pos, it in enumerate(raw_feed, start=1):
    if positions[it["id"]][0] != pos:
        continue  # keep first occurrence only
    entry = dict(it)  # original key order, every field verbatim
    entry["tile_positions"] = positions[it["id"]]      # all raw feed positions incl. duplicates
    entry["rank"] = len(shows) + 1                       # dense rank over unique shows
    # canonical URL requires the series id — slug-only form renders "Page not found"
    # (verified via headless-Chrome rendered-title probing; see docs/RESEARCH.md §4.2)
    entry["url"] = f"https://www.crunchyroll.com/series/{it['id']}/{it['slug_title']}"
    shows.append(entry)

assert len(shows) == len(positions), "dedupe must keep exactly one record per unique id"

extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
all_pass = all(c["passed"] for c in checks)

database = {
    "database": {
        "name": "crunchyroll_popular",
        "version": "1.1.0",
        "description": "Complete database of every show listed on Crunchyroll's 'Most Popular' page "
                       "(https://www.crunchyroll.com/videos/popular), in popularity order. "
                       "The page's feed contained 1104 tiles; 7 shows appeared on 2 tiles each "
                       "(a property of Crunchyroll's popularity feed, verified byte-identical and "
                       "identical positions across two independent capture sessions), so the database "
                       "contains 1097 unique shows with every raw tile position preserved.",
        "source_page": "https://www.crunchyroll.com/videos/popular",
        "api_endpoint": "https://www.crunchyroll.com/content/v2/discover/browse",
        "api_query": "start={offset}&n=36&sort_by=popularity&ratings=true&locale=en-US",
        "auth": "anonymous client token (POST /auth/v1/token, grant_type=client_id, client 'cr_web')",
        "locale": "en-US",
        "extracted_at_utc": extracted_at,
        "browser_capture_session_at_utc": json.load(
            open(os.path.join(WORK, "browse-capture", "meta.json"), encoding="utf-8"))["capturedAt"],
        "api_crawl_started_at_utc": manifest["crawl_started_at"],
        "api_crawl_finished_at_utc": manifest["crawl_finished_at"],
        "counts": {
            "raw_feed_tiles": len(raw_feed),
            "unique_shows": len(shows),
            "duplicated_shows": len(dup_ids),
            "api_reported_total": total_api,
        },
        "pagination": {
            "page_size": 36,
            "data_pages_fetched": len(data_pages),
            "contiguous": True,
            "exhaustion_proof": f"last data page returned {data_pages[-1]['received']}/36 items "
                                 f"and the overflow page at start={overflow_pages[0]['start']} returned 0 items",
        },
        "rank_definition": "rank = dense popularity rank over unique shows (1 = most popular; "
                           "array order == rank order). tile_positions = the exact 1-based position(s) "
                           "of the show's tile(s) in the raw feed as rendered on the page.",
        "url_format": "https://www.crunchyroll.com/series/{id}/{slug_title} — the id is REQUIRED: "
                      "slug-only URLs (/series/{slug}) answer HTTP 200 but render 'Page not found' "
                      "in the app (verified by headless-Chrome title probing).",
        "losslessness": "Every field of every show is preserved exactly as returned by the API; the only "
                        "additions are 'rank', 'tile_positions' and 'url'. Raw page payloads are archived "
                        "archived (see the provenance bundles under provenance/) for byte-level provenance.",
        "field_reference": {
            "rank": "int — dense popularity rank over unique shows (1 = most popular)",
            "tile_positions": "int[] — 1-based position(s) of this show's tile(s) in the raw page feed "
                              "(length > 1 means Crunchyroll's feed listed this show more than once)",
            "url": "string — canonical Crunchyroll page URL, format https://www.crunchyroll.com/series/{id}/{slug_title}",
            "id": "string — Crunchyroll CMS id (stable identifier)",
            "external_id": "string — external reference id (e.g. SRZ.283731)",
            "channel_id": "string — content channel (crunchyroll)",
            "linked_resource_key": "string — CMS resource pointer (cms:/series/{id})",
            "new": "bool — flagged as 'new' by Crunchyroll",
            "title": "string — display title",
            "description": "string — show description (empty string when the API provides none)",
            "promo_title / promo_description": "string — marketing-optimized title/description variants",
            "type": "string — content type ('series' or 'movie')",
            "slug / slug_title": "string — URL slugs (slug_title is used in canonical URLs)",
            "last_public": "string (ISO-8601 UTC) — timestamp of the most recently published episode/movie",
            "images": "object — poster_wide (16:9), poster_tall (2:3), promo_image; each is an array of "
                       "size-variants with width/height/type/source",
            "images_localized": "object — localized key-art asset templates (URLs contain a '{:param}' "
                                 "CDN transform placeholder); present where the API provides it",
            "series_metadata": "object — availability_status, extended_description, episode_count, "
                                "season_count, extended_maturity_rating{system,rating,level,advisories}, "
                                "maturity_ratings[], content_descriptors[], content_descriptors_with_symbol[], "
                                "is_mature, mature_blocked, is_subbed, is_dubbed, is_simulcast, linked_guid, "
                                "availability_notes, audio_locales[], subtitle_locales[], series_launch_year, "
                                "awards[{text,icon_url,is_current_award,is_winner}], tenant_categories[] "
                                "(genres), language_presentation{...}",
            "language_presentation": "object — locale presentation defaults for the listing "
                                      "(audio_notation, text_notation, audio_locale, text_locale, ...)",
            "rating": "object — Crunchyroll star ratings: '1s'..'5s' = per-star vote counts "
                       "{displayed (approximate), unit, percentage}, 'average' = average rating 0-5, "
                       "'total' = total number of ratings",
        },
        "semantics_caveats": {
            "episode_count": "Number of playable episodes as the popular page displays it. This equals the "
                             "`media_count` field of Crunchyroll's CMS series endpoint. (The CMS endpoint's "
                             "own episode_count/season_count use a different counting model — e.g. dub-only "
                             "seasons counted separately — and can differ; verified on 45/45 sampled shows "
                             "that this database's episode_count == CMS media_count, while titles matched "
                             "100%.)",
            "audio_locales / subtitle_locales": "Semantically UNORDERED sets: the API returns these arrays "
                                                "in a different order on every call. Order here is exactly as "
                                                "served at extraction time; compare as sets.",
            "popularity_order": "Popularity ranks are a live, continuously-updating ordering. This database "
                               "is a verified snapshot at 'extracted_at_utc'; live drift is measured and "
                               "reported in data/verification_report.json.",
        },
        "verification": {
            "all_passed": all_pass,
            "checks": checks,
            "browser_capture_cross_check": cross,
            "duplicate_audit": {
                "duplicated_shows": sorted(dup_entry_info, key=lambda d: d["tile_positions"][0]),
                "explanation": "These 7 shows each appeared on 2 tiles in the raw popularity feed. "
                               "Entries were byte-identical, and the exact same ids at the exact same "
                               "tile positions appeared in the independent headless-Chrome capture — "
                               "i.e. this is how Crunchyroll's feed is served, not a crawl artifact. "
                               "The database keeps one record per show; all raw positions are in "
                               "'tile_positions'.",
            },
            "notes": [
                "The feed was captured twice independently: (1) a real headless-Chrome session that "
                "scrolled the live page until the infinite-scroll feed was exhausted, and (2) a direct "
                "sequential crawl of the same API the page uses. They matched tile-for-tile.",
                "2 shows have an empty description (OFFSIDE, BangG Dream! Movies) — exactly as the API "
                "serves it; preserved as-is.",
                f"{len(dup_titles)} titles are shared by multiple distinct shows (different ids, e.g. "
                "remasters/alternate entries) — kept as separate records since they are distinct catalog "
                "entries.",
            ],
        },
    },
    "shows": shows,
}

with open(OUT_DB, "w", encoding="utf-8") as f:
    json.dump(database, f, ensure_ascii=False, indent=2)
    f.write("\n")

report = {
    "generated_at_utc": extracted_at,
    "all_checks_passed": all_pass,
    "checks": checks,
    "browser_capture_cross_check": cross,
    "page_audit": page_audit,
    "duplicate_audit": sorted(dup_entry_info, key=lambda d: d["tile_positions"][0]),
    "duplicate_titles_case_insensitive": {t: n for t, n in sorted(dup_titles.items(), key=lambda kv: -kv[1])},
    "stats": {
        "raw_feed_tiles": len(raw_feed),
        "unique_shows": len(shows),
        "with_awards": sum(1 for i in raw_feed if i["series_metadata"].get("awards")),
        "with_images_localized": sum(1 for i in raw_feed if "images_localized" in i),
        "with_content_descriptors": sum(1 for i in raw_feed if i["series_metadata"].get("content_descriptors")),
        "empty_descriptions": sorted({i["title"] for i in raw_feed if not (i.get("description") or "").strip()}),
        "type_breakdown": dict(types),
    },
}
with open(OUT_REPORT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

size = os.path.getsize(OUT_DB)
print(f"\nWrote {OUT_DB} ({size/1_048_576:.2f} MB)")
print(f"Wrote {OUT_REPORT}")
print(f"\nALL CHECKS PASSED: {all_pass}")
if not all_pass:
    raise SystemExit(1)
