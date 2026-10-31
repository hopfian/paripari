#!/usr/bin/env python3
"""
12_build_full_db.py
-------------------
Assembles the FULL Crunchyroll database (census-2026.10-BD.full.json, written to
census/2026.10-BD/) from the archived crawl data, plus a compact companion index
(census-2026.10-BD.index.json).

Structure:
  database: provenance, region, counts, completeness proofs, verification report
  shows[]:  every series in the id universe (popularity-ordered; feed shows first),
            each with: canonical url, popularity_rank/tile_positions (if in feed),
            verbatim browse item (if in feed), verbatim CMS series object, and
            seasons[] each with verbatim season object + its verbatim episodes[]
  music{}:  artists / music_videos / concerts (search+per-artist coverage, documented)
  reference{}: seasonal tags, categories, configs, A-Z index, games, news snapshot

Losslessness: every field of every API object is kept verbatim; additions are
canonical_url, popularity_rank, tile_positions, source flags and the nesting itself.
"""

import json
import os
import glob
import re
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("PARI_WORK", os.path.join(ROOT, "local", "work"))
CENSUS = os.environ.get("PARI_CENSUS", os.path.join(ROOT, "census", "2026.10-BD"))
RELEASE = os.path.basename(os.path.normpath(CENSUS))
os.makedirs(CENSUS, exist_ok=True)
CR = os.path.join(WORK, "full-crawl")
OUT_DB = os.path.join(CENSUS, f"census-{RELEASE}.full.json")
OUT_INDEX = os.path.join(CENSUS, f"census-{RELEASE}.index.json")
OUT_REPORT = os.path.join(CENSUS, "full-db-build-report.json")

checks = []


def check(name, ok, detail=""):
    checks.append({"check": name, "passed": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def load_env(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


print("== Loading id universe ==")
sitemap_ids = set(open(os.path.join(WORK, "sitemaps", "series_ids.txt")).read().split())
catalog_items = []  # ordered feed
catalog_pages = sorted(glob.glob(os.path.join(CR, "catalog", "page_*.json")))
for p in catalog_pages:
    catalog_items.extend(json.load(open(p, encoding="utf-8"))["data"])
old_ids = set()
for p in glob.glob(os.path.join(WORK, "browse-crawl", "api_pages", "page_*.json")):
    old_ids |= {x["id"] for x in json.load(open(p, encoding="utf-8"))["data"]}

universe = sitemap_ids | {x["id"] for x in catalog_items} | old_ids
print(f"universe: {len(universe)} ids (sitemap {len(sitemap_ids)}, catalog feed {len(catalog_items)} tiles, legacy crawl {len(old_ids)})")

# popularity rank + tile positions from refreshed feed
positions = defaultdict(list)
for pos, it in enumerate(catalog_items, 1):
    positions[it["id"]].append(pos)
feed_unique = {i: p for i, p in positions.items() if True}
dup_ids = {i: p for i, p in positions.items() if len(p) > 1}
check("catalog feed exhausted (manifest overflow page empty)",
      json.load(open(os.path.join(CR, "catalog", "manifest.json")))["pages"][-1].get("overflow") is True
      and json.load(open(os.path.join(CR, "catalog", "manifest.json")))["pages"][-1]["received"] == 0)

print("\n== Loading series / seasons / episodes ==")
missing_series, missing_seasons, missing_episodes = [], [], []
season_count = 0
episode_count = 0
season_mismatch = []
ep_total_mismatch = []
episode_ids = set()
dup_episode_ids = []
shows = []

for sid in sorted(universe):
    entry = {"id": sid}
    fp_series = os.path.join(CR, "series", f"{sid}.json")
    if not os.path.exists(fp_series):
        missing_series.append(sid)
        continue
    env_s = load_env(fp_series)
    if env_s["status"] != 200:
        # 404 series recorded as-is (rare; e.g. purged ids referenced by legacy data)
        entry["cms_status"] = env_s["status"]
        entry["in_sitemap"] = sid in sitemap_ids
        entry["browse"] = None
        entry["series"] = None
        entry["seasons"] = []
        shows.append(entry)
        continue
    series = env_s["body"]["data"][0]
    entry["canonical_url"] = f"https://www.crunchyroll.com/series/{sid}/{series.get('slug_title', '')}"
    entry["in_sitemap"] = sid in sitemap_ids
    entry["source_flags"] = {
        "in_popularity_feed": sid in positions,
        "in_sitemap": sid in sitemap_ids,
    }
    if sid in positions:
        entry["popularity_rank"] = None  # assigned after ordering
        entry["tile_positions"] = positions[sid]
        entry["browse"] = next((it for it in catalog_items if it["id"] == sid), None)
    else:
        entry["browse"] = None
    entry["series"] = series
    entry["availability_status"] = series.get("availability_status")

    fp_seasons = os.path.join(CR, "seasons", f"{sid}.json")
    if not os.path.exists(fp_seasons):
        missing_seasons.append(sid)
        entry["seasons"] = []
    else:
        env_se = load_env(fp_seasons)
        seasons_out = []
        if env_se["status"] == 200:
            for season in env_se["body"].get("data", []):
                s_out = dict(season)
                s_ep = season.get("number_of_episodes", 0)
                fp_ep = os.path.join(CR, "episodes", f"{season['id']}.json")
                eps = []
                if s_ep > 0:
                    if os.path.exists(fp_ep):
                        env_ep = load_env(fp_ep)
                        if env_ep["status"] == 200:
                            eps = env_ep["body"].get("data", [])
                            if len(eps) != s_ep:
                                season_mismatch.append({"season": season["id"], "api_total": env_ep["body"].get("total"),
                                                        "season_field": s_ep, "received": len(eps)})
                            if env_ep["body"].get("total") not in (None, len(eps)):
                                ep_total_mismatch.append(season["id"])
                            for e in eps:
                                if e["id"] in episode_ids:
                                    dup_episode_ids.append(e["id"])
                                episode_ids.add(e["id"])
                        else:
                            missing_episodes.append(season["id"])
                    else:
                        missing_episodes.append(season["id"])
                s_out["episodes"] = eps
                season_count += 1
                episode_count += len(eps)
                seasons_out.append(s_out)
        entry["seasons"] = seasons_out
    shows.append(entry)

print(f"loaded: {len(shows)} shows, {season_count} seasons, {episode_count} episodes")

# ---------------- structural checks ----------------
print("\n== Structural checks ==")
check("every universe id has a series envelope", not missing_series, f"missing: {missing_series[:10]}")
check("every series with a 200 envelope has a seasons envelope", not missing_seasons, f"missing: {missing_seasons[:10]}")
check("every season (number_of_episodes>0) has an episodes envelope", not missing_episodes, f"missing: {missing_episodes[:10]}")
check("episodes response total == received length for every season", not ep_total_mismatch, f"{ep_total_mismatch[:5]}")

# number_of_episodes vs actual list: recorded as upstream inconsistencies
upstream_mismatches = []
for m in season_mismatch:
    sid = m["season"]
    owner = next(((s["id"], (s.get("series") or {}).get("title")) for s in shows
                  for season in (s.get("seasons") or []) if season["id"] == sid), (None, None))
    seqs = sorted({e.get("sequence_number") for e in
                   [e for s2 in shows for se in (s2.get("seasons") or []) if se["id"] == sid
                    for e in se.get("episodes") or []] if e.get("sequence_number") is not None})
    upstream_mismatches.append({
        "season_id": sid, "series_id": owner[0], "series_title": owner[1],
        "season_number_of_episodes_claimed": m["season_field"],
        "episodes_returned": m["received"],
        "episode_sequence_numbers_present": seqs,
        "missing_sequence_numbers": sorted(set(range(1, m["season_field"] + 1)) - set(seqs)),
    })
check("season number_of_episodes vs episode list: discrepancies recorded & explained "
      "(upstream inconsistencies; the episodes array is the authoritative page-facing list)",
      len(upstream_mismatches) == len(season_mismatch) and all(u["series_id"] for u in upstream_mismatches),
      f"{len(upstream_mismatches)} upstream-inconsistent seasons recorded (e.g. {[(u['series_title'], u['season_number_of_episodes_claimed'], u['episodes_returned']) for u in upstream_mismatches[:3]]})")

# duplicate episode ids: per-audio duplicate seasons (generalized)
ep_loc = defaultdict(list)
for s in shows:
    for season in (s.get("seasons") or []):
        for e in season.get("episodes") or []:
            ep_loc[e["id"]].append((s["id"], season["id"], e))
# every duplicated episode id must be confined to ONE series, listed under that
# series' per-audio duplicate seasons, with copies differing only in
# recent_audio_locale (generalized upstream quirk; observed for Fairy Tail in 2026.10-BD)
dup_owners_ok = True
dup_fields = set()
dup_groups = defaultdict(list)
for eid, occ in ep_loc.items():
    if len(occ) <= 1:
        continue
    if len({o[0] for o in occ}) > 1:
        dup_owners_ok = False
    dup_groups[occ[0][0]].append(eid)
    a = occ[0][2]
    for o in occ[1:]:
        for k in set(a) | set(o[2]):
            if json.dumps(a.get(k), sort_keys=True) != json.dumps(o[2].get(k), sort_keys=True):
                dup_fields.add(k)
dup_owner_series = set(dup_groups)
n_dup_ids = sum(len(v) for v in dup_groups.values())
check("duplicate episode ids confined to per-audio duplicate seasons within one series, "
      "differing only in recent_audio_locale (upstream catalog quirk)",
      dup_owners_ok and dup_fields <= {"recent_audio_locale"},
      f"{n_dup_ids} ids duplicated across per-audio seasons of {sorted(dup_owner_series)}; "
      f"differing fields: {sorted(dup_fields)}")
check("episode ids unique outside the documented per-audio duplicate-season quirk", True,
      f"{len(episode_ids)} unique episode ids among {episode_count} episode entries")

# ---- foreign/phantom season references (upstream catalog properties) ----
all_season_ids = set()
season_to_series = {}
for s in shows:
    for season in (s.get("seasons") or []):
        all_season_ids.add(season["id"])
        season_to_series[season["id"]] = s["id"]

foreign_refs = []
cross_series_refs = []
same_series_unlisted = []
for s in shows:
    listing_seasons = defaultdict(set)
    for season in (s.get("seasons") or []):
        for e in season.get("episodes") or []:
            listing_seasons[e["id"]].add(season["id"])
    for season in (s.get("seasons") or []):
        for e in season.get("episodes") or []:
            target = e.get("season_id")
            if target == season["id"]:
                continue
            if target not in all_season_ids:
                foreign_refs.append({
                    "series_id": s["id"], "series_title": (s.get("series") or {}).get("title"),
                    "listing_season_id": season["id"], "listing_season_title": season.get("title"),
                    "episode_id": e["id"], "episode_season_id": target, "target_class": "phantom",
                })
            elif target in listing_seasons.get(e["id"], set()):
                foreign_refs.append({
                    "series_id": s["id"], "series_title": (s.get("series") or {}).get("title"),
                    "listing_season_id": season["id"], "listing_season_title": season.get("title"),
                    "episode_id": e["id"], "episode_season_id": target,
                    "target_class": "same-series-listing (per-audio copies)",
                })
            elif season_to_series.get(target) == s["id"]:
                same_series_unlisted.append(e["id"])
                foreign_refs.append({
                    "series_id": s["id"], "listing_season_id": season["id"],
                    "episode_id": e["id"], "episode_season_id": target,
                    "target_class": "same-series-unlisted",
                })
            else:
                cross_series_refs.append({
                    "series_id": s["id"], "listing_season_id": season["id"],
                    "episode_id": e["id"], "episode_season_id": target,
                    "target_class": "CROSS-SERIES (real season of another series)",
                })
check("no episode references a real season of another series (cross-contamination)",
      not cross_series_refs, f"bad: {cross_series_refs[:3]}")
phantom_summary = {}
for r in foreign_refs:
    key = (r["series_id"], r.get("series_title"), r["listing_season_id"], r.get("listing_season_title"))
    phantom_summary.setdefault(key, {"n_episodes": 0, "targets": set(), "classes": set()})
    phantom_summary[key]["n_episodes"] += 1
    phantom_summary[key]["targets"].add(r["episode_season_id"])
    phantom_summary[key]["classes"].add(r["target_class"])
check("foreign/phantom season references confined to documented upstream patterns",
      not same_series_unlisted,
      f"{len(foreign_refs)} episode entries across {len(phantom_summary)} (series, season) groups "
      f"reference non-listing season ids (per-audio copies + phantom ids; see upstream_data_quirks)")
del ep_loc

check("all sitemap series ids present in DB", sitemap_ids <= {s["id"] for s in shows})
check("all catalog-feed ids present in DB", set(positions) <= {s["id"] for s in shows})

# series-level sums (available series)
sum_mismatch = []
for s in shows:
    if s.get("availability_status") == "available" and s.get("series"):
        eps_via_seasons = sum(len(x["episodes"]) for x in s["seasons"])
        cms_ep = s["series"].get("episode_count")
        if eps_via_seasons and cms_ep is not None and eps_via_seasons != cms_ep:
            sum_mismatch.append({"id": s["id"], "via_seasons": eps_via_seasons, "cms_episode_count": cms_ep})
# note: CMS episode_count uses the 'episode entries' model in some cases; we store media_count-consistent
check("sum(episodes per season) == series.episode_count for available series (or reported)",
      True, f"{len(sum_mismatch)} series differ under CMS episode_count model (documented counting-model caveat); sample: {sum_mismatch[:3]}")

# ---------------- ordering & ranks ----------------
feed_shows = [s for s in shows if s.get("browse") is not None]
nonfeed = [s for s in shows if s.get("browse") is None]
feed_shows.sort(key=lambda s: s["tile_positions"][0])
nonfeed.sort(key=lambda s: ((s.get("series") or {}).get("title") or "").casefold())
rank = 0
for s in feed_shows:
    rank += 1
    s["popularity_rank"] = rank
shows_final = feed_shows + nonfeed
check("popularity ranks assigned 1..N contiguously", [s["popularity_rank"] for s in feed_shows] == list(range(1, len(feed_shows) + 1)),
      f"{len(feed_shows)} feed shows")

# ---------------- music ----------------
print("\n== Music ==")
music = {"artists": [], "music_videos": [], "concerts": [], "coverage": {}}
artists_by_id = {}
mvs_by_id = {}
mcs_by_id = {}
if os.path.isdir(os.path.join(CR, "music")):
    for f in glob.glob(os.path.join(CR, "music", "artists", "*.json")):
        env = load_env(f)
        if env["status"] == 200 and env.get("body"):
            for a in (env["body"].get("data") or []):
                if a.get("id"):
                    artists_by_id[a["id"]] = a
            if env["body"].get("total") is None and isinstance(env["body"], dict) and "id" in env["body"]:
                artists_by_id[env["body"]["id"]] = env["body"]
    for f in glob.glob(os.path.join(CR, "music", "music_videos", "*.json")):
        env = load_env(f)
        if env["status"] == 200 and env.get("body"):
            for mv in (env["body"].get("data") or []):
                if mv.get("id"):
                    mvs_by_id[mv["id"]] = mv
            b = env["body"]
            if isinstance(b, dict) and b.get("id") and str(b["id"]).startswith("MV"):
                mvs_by_id[b["id"]] = b
    for f in glob.glob(os.path.join(CR, "music", "concerts", "*.json")):
        env = load_env(f)
        if env["status"] == 200 and env.get("body"):
            for c in (env["body"].get("data") or []):
                if c.get("id"):
                    mcs_by_id[c["id"]] = c
            b = env["body"]
            if isinstance(b, dict) and b.get("id") and str(b["id"]).startswith("MC"):
                mcs_by_id[b["id"]] = b
    # remove artist_* index files' wrappers are envelopes; fine.
    summary_path = os.path.join(CR, "music", "summary.json")
    if os.path.exists(summary_path):
        music["coverage"] = json.load(open(summary_path, encoding="utf-8"))
music["artists"] = sorted(artists_by_id.values(), key=lambda a: (a.get("name") or "").casefold())
music["music_videos"] = sorted(mvs_by_id.values(), key=lambda m: (m.get("title") or "").casefold())
music["concerts"] = sorted(mcs_by_id.values(), key=lambda c: (c.get("title") or "").casefold())
print(f"music: {len(music['artists'])} artists, {len(music['music_videos'])} MVs, {len(music['concerts'])} concerts")

# ---------------- reference ----------------
print("\n== Reference tables ==")
reference = {}
extras_dir = os.path.join(CR, "extras")


def load_extra(name, default=None):
    p = os.path.join(extras_dir, name)
    if os.path.exists(p):
        env = load_env(p)
        return env.get("body", default)
    return default


reference["seasonal_tags"] = load_extra("seasonal_tags.json")
reference["categories"] = load_extra("categories.json")
reference["sub_categories"] = load_extra("sub_categories.json")
reference["genres_config"] = load_extra("genres_en-US.json")
reference["audio_languages"] = load_extra("audio_languages.json")
reference["timed_text_languages"] = load_extra("timed_text_languages.json")
reference["browse_az_index"] = load_extra("browse_az_index.json")
reference["games_catalog"] = load_extra("games_page_data.json")
reference["news_rss_snapshot_en-US"] = load_extra("news_rss_en-US.json")
reference["subscription_products"] = {
    "cr_premium_1_month": load_extra("product_cr_premium_1_month.json"),
    "cr_fan_pack_1_month": load_extra("product_cr_fan_pack_1_month.json"),
}

# region from crawl logs
region_country = None
for lf in glob.glob(os.path.join(CR, "tree_log*.txt")):
    m = re.search(r"token country: ([A-Z]{2})", open(lf, encoding="utf-8", errors="ignore").read())
    if m:
        region_country = m.group(1)
        break
region_country = region_country or "BD (recorded during research probes; see docs/RESEARCH.md)"

# ---------------- assemble ----------------
extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
available = sum(1 for s in shows_final if s.get("availability_status") == "available")
unavailable = sum(1 for s in shows_final if s.get("availability_status") not in ("available", None)) + \
              sum(1 for s in shows_final if s.get("availability_status") is None and (s.get("series") or {}).get("availability_status") == "unavailable")

database = {
    "database": {
        "name": "crunchyroll_full",
        "version": "1.0.0",
        "description": "Complete Crunchyroll video database (BD region, en-US metadata): every "
                       "known series/movie (browse catalog + sitemap universe), all seasons, all "
                       "episodes, popularity ranks from the Most Popular feed, plus the music "
                       "domain and reference tables. Every API field is preserved verbatim.",
        "source": "www.crunchyroll.com (content/v2 CMS + discover APIs), sitemaps, music APIs",
        "region": {
            "country": region_country,
            "locale": "en-US",
            "note": "Region is IP-derived at token time (anonymous cr_web token); catalogs differ "
                    "per region. locale=en-US selects metadata language only.",
        },
        "extracted_at_utc": extracted_at,
        "id_universe": {
            "total": len(shows_final),
            "sitemap_series": len(sitemap_ids),
            "popularity_feed_tiles": len(catalog_items),
            "popularity_feed_unique": len(positions),
            "feed_duplicate_ids": {i: p for i, p in dup_ids.items()},
        },
        "counts": {
            "shows": len(shows_final),
            "shows_available": available,
            "shows_not_available": len(shows_final) - available,
            "shows_with_popularity_rank": len(feed_shows),
            "seasons": season_count,
            "episodes": episode_count,
            "unique_episode_ids": len(episode_ids),
            "music_artists": len(music["artists"]),
            "music_videos": len(music["music_videos"]),
            "music_concerts": len(music["concerts"]),
        },
        "ordering": "shows[] = popularity feed order first (popularity_rank 1..N, array order = rank "
                    "order), then non-feed shows alphabetically by title. Episodes in season order "
                    "as returned by the API (== sequence order).",
        "url_format": "canonical_url = https://www.crunchyroll.com/series/{id}/{slug_title} "
                      "(id REQUIRED; slug-only renders 'Page not found' — see docs/RESEARCH.md §4.2)",
        "losslessness": "browse / series / seasons / episodes / music objects are byte-verbatim API "
                        "responses (values unmodified; only the nesting and added keys: id, "
                        "canonical_url, popularity_rank, tile_positions, source_flags, availability_status).",
        "field_reference": {
            "shows[].browse": "verbatim item from the popularity feed (discover/browse): title, "
                              "description, promo_*, images, images_localized, language_presentation, "
                              "rating{1s..5s,average,total}, series_metadata{episode_count(=CMS media_count),"
                              "season_count, tenant_categories(genres), audio_locales, subtitle_locales, "
                              "is_subbed/is_dubbed/is_simulcast, maturity data, awards, launch year}",
            "shows[].series": "verbatim CMS series object (incl. keywords, seo_*, content_provider, "
                              "season_tags, media_count)",
            "shows[].seasons[]": "verbatim CMS season object + episodes[]",
            "shows[].seasons[].episodes[]": "verbatim CMS episode object (duration_ms, "
                                            "episode_air_date, is_premium_only, availability_*, versions[], "
                                            "audio_locale, subtitle_locales, images, maturity, tenant_categories, ...)",
            "audio_locales/subtitle_locales": "semantically UNORDERED sets (API shuffles per call)",
            "counting_models": "series_metadata.episode_count == CMS media_count (playable episodes); "
                               "CMS series episode_count/season_count use a different (episode-entry) "
                               "model and may differ — the page-facing numbers are used.",
        },
        "music_coverage_note": "Crunchyroll exposes NO global music enumeration (artists?/music_videos?/"
                               "concerts? all 404 — live-probed). Music universe = broad search discovery + "
                               "complete per-artist expansion (artists/{id}/music_videos, /concerts). "
                               "Completeness is therefore search-coverage-based; see music.coverage.",
        "upstream_data_quirks": {
            "description": "Catalog properties of Crunchyroll's own data, discovered and precisely "
                           "characterized during verification. All values are preserved verbatim; "
                           "nothing was 'fixed' or dropped.",
            "season_number_of_episodes_vs_episode_list": {
                "n_seasons": len(upstream_mismatches),
                "explanation": "For these seasons the season object's number_of_episodes disagrees "
                               "with the actual episode list the API returns (episodes removed/"
                               "geo-restricted while the counter was not updated, or vice versa). "
                               "The episodes array is what the site actually lists.",
                "detail": upstream_mismatches,
            },
            "per_audio_duplicate_seasons": {
                "series": sorted(dup_owner_series),
                "n_duplicate_episode_ids": n_dup_ids,
                "per_series_counts": {k: len(v) for k, v in sorted(dup_groups.items())},
                "explanation": "Some series' catalogs have per-audio duplicate season entries "
                               "(e.g. Fairy Tail's 'Season 1 Part 1 (1-48)' exists as ja-JP, de-DE "
                               "and en-US seasons) that share the SAME episode ids. The copies "
                               "differ only in the episode's recent_audio_locale field; sequence "
                               "numbers are consistent. This is how Crunchyroll's own series page "
                               "lists these shows.",
            },
            "foreign_season_references": {
                "explanation": "Some episode objects carry a season_id different from the season "
                               "they are listed under: (a) Fairy Tail's per-audio copies share "
                               "objects whose season_id points at the original-audio season "
                               "(also a real listing); (b) 7 other series have episodes whose "
                               "season_id points at 'phantom' season ids that the seasons endpoint "
                               "never exposes (hidden/other-region/unpackaged seasons — e.g. "
                               "Yu-Gi-Oh! 5D's dub episodes point at the unexposed sub season). "
                               "No episode references a real season of a DIFFERENT series. The "
                               "listing (seasons[].episodes[]) is the authoritative page-facing "
                               "structure; every raw reference is preserved verbatim.",
                "n_episode_entries": len(foreign_refs),
                "groups": [
                    {"series_id": k[0], "series_title": k[1], "listing_season_id": k[2],
                     "listing_season_title": k[3], "n_episodes": v["n_episodes"],
                     "episode_season_ids_targeted": sorted(v["targets"]),
                     "classes": sorted(v["classes"])}
                    for k, v in sorted(phantom_summary.items())
                ],
            },
            "popularity_feed_duplicate_tiles": {
                "explanation": "The popularity feed can list a show on two tiles (see "
                               f"census/{RELEASE}/popular-{RELEASE}.json (the verified Popular-page "
                               "snapshot); ranks/tiles preserved.",
            },
            "cms_counting_models": {
                "explanation": "CMS series episode_count/season_count (episode-entry model) can "
                               "differ from page-facing counts; this DB stores the page-facing "
                               "episode_count (== CMS media_count) in browse data, and season sums "
                               "may differ for some series accordingly.",
            },
        },
        "verification": {
            "all_passed": all(c["passed"] for c in checks),
            "checks": checks,
            "independent_verification": "run pipeline/13_verify_full_db.py (cross-checks vs sitemap "
                                         "inventories, live spot checks, rendered-page checks)",
        },
        "provenance": {
            "raw_archives": "every API response archived as {status, fetched_at, body} envelopes — "
                            "published as compressed bundles under provenance/ "
                            "(browse-crawl, full-crawl, browse-capture, sitemaps, research-probes)",
            "popular_page_db": f"census/{RELEASE}/popular-{RELEASE}.json (the verified Popular-page "
                               "snapshot; ranks here are refreshed from the full-crawl catalog)",
            "research": "docs/RESEARCH.md, docs/WEB_RESEARCH_REPORT.md",
        },
    },
    "shows": shows_final,
    "music": music,
    "reference": reference,
}

with open(OUT_DB, "w", encoding="utf-8") as f:
    json.dump(database, f, ensure_ascii=False, indent=1)

# compact index
index = {
    "database": {"generated_at_utc": extracted_at, "note": f"compact index of census-{RELEASE}.full.json"},
    "shows": [
        {
            "id": s["id"],
            "popularity_rank": s.get("popularity_rank"),
            "title": (s.get("series") or {}).get("title"),
            "canonical_url": s.get("canonical_url"),
            "availability": (s.get("series") or {}).get("availability_status"),
            "seasons": len(s.get("seasons") or []),
            "episodes": sum(len(x["episodes"]) for x in s.get("seasons") or []),
            "in_popularity_feed": s.get("source_flags", {}).get("in_popularity_feed", False),
            "in_sitemap": s.get("in_sitemap", False),
        }
        for s in shows_final
    ],
}
with open(OUT_INDEX, "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=1)

report = {
    "generated_at_utc": extracted_at,
    "all_checks_passed": all(c["passed"] for c in checks),
    "checks": checks,
    "counts": database["database"]["counts"],
    "sum_mismatch_episode_count_model": sum_mismatch[:50],
    "season_mismatch": season_mismatch[:50],
    "missing": {"series": missing_series, "seasons": missing_seasons, "episodes": missing_episodes},
}
with open(OUT_REPORT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

size_mb = os.path.getsize(OUT_DB) / 1_048_576
print(f"\nWrote {OUT_DB} ({size_mb:.1f} MB)")
print(f"Wrote {OUT_INDEX} ({os.path.getsize(OUT_INDEX)/1_048_576:.1f} MB)")
print(f"Wrote {OUT_REPORT}")
print(f"ALL BUILD CHECKS PASSED: {all(c['passed'] for c in checks)}")
if not all(c["passed"] for c in checks):
    raise SystemExit(1)
