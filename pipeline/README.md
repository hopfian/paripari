# The pipeline

Thirteen self-contained stages: research → capture → crawl → build → verify.
Node (.mjs) for anything that drives Chrome or curl-backed crawling; Python for analysis
and assembly. **No third-party dependencies** — Node ≥ 22, Python ≥ 3.11, `curl`, `jq`,
and Google Chrome (for CDP stages).

All stages read/write a **working area** (`local/work/`, gitignored) and publish final
artifacts to `census/<release>/`:

```
PARI_WORK   (default: <repo>/local/work)     — working area
PARI_CENSUS (default: <repo>/census/2026.10-BD) — census output directory
```

## Stage map

| # | Stage | Reads | Writes | What it does |
|---|---|---|---|---|
| 01 | `01_cdp_capture.mjs` | live page | `work/browse-capture/` | Headless Chrome via raw CDP; loads the real page, auto-scrolls until the infinite feed is exhausted, records every network request/response. Proves the page is exhausted, not just the API. |
| 02 | `02_analyze_captures.py` | `work/browse-capture/` | stdout | Identifies the API the page actually uses. |
| 03 | `03_fetch_api_full.mjs` | live API | `work/browse-crawl/` | Sequential crawl of the popularity feed (36-item pages) until an **empty overflow page**; archives every page + manifest. |
| 04 | `04_build_db.py` | `work/browse-crawl/`, `work/browse-capture/` | `census/popular-*.json` | Builds the popular-page database; 13 structural + cross-capture checks; dedupes with full tile-position provenance. |
| 05 | `05_verify.py` | census + live | `census/popular-verification-report.json` | Independent LIVE verification: internal consistency, top-36 identity, CMS identity invariant, rendered-page checks, drift scan. |
| 06 | `06_surface_prober.mjs` | a URL list | `work/research-probes/<name>/` | Multi-URL CDP prober: captures any page's API calls + bodies (no scrolling). Used for surface research and render checks. |
| 07 | `07_sitemap_enum.py` | sitemaps | `work/sitemaps/` | Enumerates the public sitemap inventory: 2,044 series ids, 92,275 watch-page ids, shard stats. |
| 08 | `08_refresh_catalog.mjs` | live API | `work/full-crawl/catalog/` | Refreshes the popularity feed (current items + ranks) with exhaustion proof. |
| 09 | `09_crawl_video_tree.mjs` | `work/` inventories | `work/full-crawl/{series,seasons,episodes}/` | The main crawl: for every id in the universe, CMS series → seasons → per-season episodes. Resumable (skips existing files), shardable (`node 09… <shard> <shards>`), paced with backoff. |
| 10 | `10_crawl_music.mjs` | live API | `work/full-crawl/music/` | Music domain: broad search discovery + complete per-artist expansion (no enumeration endpoint exists — see DB meta). |
| 11 | `11_fetch_extras.py` | live API | `work/full-crawl/extras/` | Reference tables: seasonal tags, categories, genres, i18n, A–Z index, games, news RSS, products. |
| 12 | `12_build_full_db.py` | `work/` | `census/census-*.full.json` + `.index.json` | Assembles the full database; runs all build checks (recomputation, duplicate/quirk classification, coverage). |
| 13 | `13_verify_full_db.py` | census + `work/` + live | `census/full-db-verification-report.json` | Independent verification: byte-verbatim vs archives, sitemap reconciliation, live CMS invariant, rendered pages. **All hard checks must pass.** |

Probe URL lists (inputs for stage 06) live in `probe-lists/`.

## Engineering notes

- **All HTTP goes through `curl`** (subprocess): Cloudflare accepts curl's TLS fingerprint
  and rejects Node's native fetch — a live-probed fact, see `docs/RESEARCH.md` §3.
- **One anonymous token** (`POST /auth/v1/token`, public `cr_web` client), refreshed
  proactively (~45 min) and reactively on 401/403; exponential backoff on 429/5xx.
- **Every response archived immediately** as `{status, fetched_at, body}` envelopes —
  crash-safe, resumable, and publishable as provenance.
- Stage scripts are kept **exactly as executed** (their only post-run edits were path
  constants during the repo restructure): the scripts are their own provenance.
