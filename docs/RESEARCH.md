# Crunchyroll — Research & Design (Phases P1–P4)

**Compiled 2026-10-31 from live probing (all claims verified against the live service unless
marked "web") + extensive web research (see `docs/WEB_RESEARCH_REPORT.md` for the full sourced
report). This document defines the extraction design for the full database.**

---

## §1. Surface survey (P1) — what crunchyroll.com actually exposes

### 1.1 Listing surfaces (video catalog)

| Surface URL | Status | API the page actually calls (live-probed) |
|---|---|---|
| `/videos/popular` | live | `discover/browse?n=36&sort_by=popularity&ratings=true&locale=en-US` |
| `/videos/anime` | live (alias) | client-redirects to `/videos/popular` |
| `/videos/new` | live | `discover/browse?...&sort_by=newly_added` |
| `/videos/alphabetical` | live | `discover/browse/index?sort_by=alphabetical` (A–Z prefix index) + `browse?n=50&sort_by=alphabetical` |
| `/videos/{genre}` (+`/{sub}/{popular,new,alphabetical}`) | live | `discover/browse?categories={g}` / `categories={g1,g2}` |
| `/videos/music` | live | `discover/browse?categories=music` (music-category *series*) |
| `/simulcasts/seasons/{fall-2009…fall-2026}` (72 pages) | live | `discover/browse?seasonal_tag={tag}&n=100` |
| `/browse` | legacy | client-redirects to `/videos/popular` |
| `/videos/dramas`, `/videos/movies`, `/videos/simulcasts`, `/simulcastcalendar` | **DEAD** | server returns 200 but SPA renders **"Page not found"** (live-probed via headless Chrome) |
| `/search?q=` | live | `discover/search?q=&type=music,series,episode,top_results,movie_listing&n=6` |

**Catalog dimensions** (live-probed values): `sort_by ∈ {popularity, newly_added, alphabetical}`;
`categories={slug}` (genre/subgenre combos, enumerated by sitemap `videos.xml`: 312 category-combination
pages over 38 genre slugs); `seasonal_tag` (72 tags: `fall-2009`…`fall-2026` + `spring/summer/winter`);
`type ∈ {series, movie, episode}` (movie = 72 items; all CMS items are typed `series` at top level);
`is_dubbed`, `is_subbed` filters.

### 1.2 Content pages (live-probed call sequences)

- **Series page** `/series/{id}/{slug}` → `cms/series/{id}`, `cms/series/{id}/seasons`,
  `cms/seasons/{sid}/episodes` (per season), `discover/categories?guid={id}`,
  `discover/up_next/{id}`, `discover/similar_to/{id}?n=30&ratings=true`, `music/featured/{id}`.
  ⚠ **Slug-only URLs (`/series/{slug}`) render "Page not found"** — canonical form requires the id
  (`/series/GG5H5XQX4/frieren-beyond-journeys-end`). (The server still answers HTTP 200, so status-only
  checks are misleading — verified via rendered title in headless Chrome.)
- **Watch page** `/watch/{id}/{slug}` → `cms/objects/{id}?ratings=true`, `discover/previous_episode/{id}`,
  `cms/series/{id}`, `cms/series/{id}/seasons?force_locale=ja-JP`, `discover/categories?guid={series_id}`.
- **Movie pages**: movies are modeled as series (e.g. *5 Centimeters Per Second* = series
  `GMTE00115271` with a single locale-suffixed season `GMSE00115271JAJP`) — same call tree as series.
- **Music**: `/watch/musicvideo/{id}` → `music/music_videos/{id}`, `music/artists/{aid}`,
  `music/artists/{aid}/concerts`, `music/artists/{aid}/music_videos`. `/watch/concert/{id}` analogous.
  Artist *pages* (`/music/artist/...`) 404 — only the `/music` landing and watch pages exist.
  The `/music` landing calls `music/landing_feed?n=14&start=0` (curated, `total=14`, no paging),
  then batch lookups `music/artists/{ids}`, `music/concerts/{ids}`, `music/music_videos/{ids}`.
- **Games**: `/games` is a Gatsby static site; machine-readable at `/games/page-data/games/page-data.json`.
- **News**: `/news` (Storyblok); machine-readable RSS at
  `https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss` (live-probed: 200, XML).
- **Manga**: dead surface on crunchyroll.com — the page loads a Gatsby shell with no data calls
  (consistent with web research: manga relaunched Oct 2025 as a Link-U-built US/Canada app, no
  crunchyroll.com API).
- **Store**: `store.crunchyroll.com` (Right Stuf); the robots-allowed
  `/cr-lab-akihabara-service/v1/products/search` requires a session (401 "Missing session id") → out of scope.

### 1.3 Sitemap inventory (live-crawled 2026-10-31)

`robots.txt` → `sitemap.xml` = index of **178 child sitemaps**. Content shards:
- `/sitemaps/series/{A–Z,#}.xml` — **2,044 unique series URLs** (`/series/{id}/{slug}`), 27 shards.
- `/sitemaps/episode/{A–Z,#}.xml` — 107 shard-pages, **92,275 unique `/watch/{id}/{slug}` URLs**.
  ID analysis: 80,708 9-char ids + 10,713 ids with **5-letter audio-locale suffixes**
  (e.g. `GE00003432ENUS`, `GE00003432ES419`) → per-audio-version watch pages; 4,464 end in a known
  locale suffix; also `GWDU…`-prefixed live-TV ids (2,800).
- `/sitemaps/videos.xml` = 312 category-listing URLs; `/sitemaps/simulcasts.xml` = 72 season URLs;
  news sitemaps per locale (8 languages); static/extras.

**Key insight: neither the API browse index nor the sitemaps alone are complete.**
The browse/discover index serves **1,104 entries** (its own `total`, confirmed 4 independent ways:
popular feed, `type=series`(1,032)+`type=movie`(72), `browse/index` prefix sums, and the alphabetical
feed). The sitemaps list **2,044 series** of which **1,051 are NOT in the browse index** — these are
region-unavailable titles (live-probed: `availability_status="unavailable"`, `episode_count=0`,
`media_count>0`, e.g. *Love of Kill*, *Manyu Scroll*). Conversely **104 browse-index series are NOT in
the sitemap**. The complete series inventory from this vantage = **2,148 unique ids** (union).

### 1.4 Session/region facts (live-probed)

- Anonymous token via `POST /auth/v1/token` (`Basic Y3Jfd2ViOg==` = `cr_web:`) returns
  `country: "BD"` — **this session's catalog is the Bangladesh region with en-US metadata language**
  (matches web research: region = IP at token time; `locale` only selects metadata language).
- Token `expires_in: 3600`. Cloudflare accepts `curl`'s TLS fingerprint and rejects Node's fetch.
- Region-unavailable series still return full CMS metadata with `media_count` (the raw episode
  inventory) but zero available seasons/episodes through `content/v2`.

## §2. Web research — key conclusions (P2)

Full sourced report: `docs/WEB_RESEARCH_REPORT.md`. Highlights:
- No official API docs; community-verified endpoint inventory matches our live probing 1:1
  (yt-dlp [removed Jan 2025], crunchyroll-rs 0.19.1, Crunchyroll-Plus docs).
- Season/episode object schemas documented by crunchyroll-rs (§2 of the report) — our live probes
  match (`duration_ms`, `is_premium_only`, `versions`, `availability_*`, `season_tags`, etc.).
- Signed-CMS bulk route alive: `GET /index/v2` → `beta-api.crunchyroll.com/cms/v2/BD/M2/-/...`
  (live-probed, returns old-style `__class__` model). **Not used for the DB**: it exposes a *raw*
  media model (Frieren → 25 season-entries incl. per-dub variants) that does not match the site's
  user-facing model (2 seasons). Unsigned `content/v2` = what the site displays.
- Bulk-scan soft-ban guidance: reuse one token (~50 min), serialize auth, back off on 403/429.
- Official catalog-size claims (marketing): 1,000+ titles / 30,000 episodes (2021) → 40k (2022) →
  46k episodes+films & 3,300 music videos (2024) → 50,000+ episodes / 25,000+ hours (2025–26).
  Free tier removed Dec 31, 2025.
- Manga: external Link-U platform (US/CA app), no crunchyroll.com API → out of scope, documented.
- Music videos/concerts: premium-only, absent in ~15 mostly-Asian markets (available in BD region —
  live-probed working).

## §3. Endpoint probing — verified behaviors (P3)

All live-verified 2026-10-31 with anonymous `cr_web` token, `locale=en-US`:

| Endpoint | Verified behavior |
|---|---|
| `POST /auth/v1/token` | `grant_type=client_id` → Bearer + `country`. 405 if method dropped (GET). Cloudflare-resistant via curl. |
| `GET /content/v2/discover/browse` | `{data,total}`; pages of `n` (36/50/100 all work); `start` offset; **`total` changes live** (popularity churn); duplicate tiles possible (7 seen, byte-identical, both captures); filter vocabulary as §1.1. `browse/index` → per-letter prefix/offset table summing to 1104. |
| `GET /content/v2/discover/browse?type=episode&sort_by=newly_added` | **`total` capped at 10,000** → cannot enumerate all episodes; returns episode items with nested `episode_metadata` and per-audio-version ids (`GE00379526JAJP`). |
| `GET /content/v2/discover/search` | types `music, series, episode, top_results, movie_listing`; `music` search works, returns `musicVideo` items. |
| `GET /content/v2/cms/series/{id}` | full series metadata; **`media_count` = playable episodes (== browse `episode_count`; CMS's own `episode_count`/`season_count` use a different counting model — verified 45/45)**. |
| `GET /content/v2/cms/series/{id}/seasons` | user-facing seasons (dubs collapsed); fields per §2 of web report. |
| `GET /content/v2/cms/seasons/{sid}/episodes` | **returns ALL episodes of a season in one call** (208/208 for One Piece's largest season; `n`/`start` params are IGNORED → no pagination needed). Rich episode objects (§2). |
| `GET /content/v2/cms/objects/{id}` | polymorphic single lookup (used by watch pages) with `ratings=true`. |
| `GET /content/v2/music/landing_feed` | curated, `total=14`, no full enumeration. |
| `GET /content/v2/music/artists/{id}` (+`/music_videos`, `/concerts`) | complete per-artist listings (e.g. 36 MVs, 1 concert); artist object embeds aggregate counts (`totalVideoDurationMs`, `concerts`, `videos`). |
| Global music listing endpoints (`music/artists?`, `music_videos?`, `concerts?`) | **404** — no public enumeration; only search + per-artist expansion. |
| `GET /content/v2/discover/seasonal_tags` | 72 tags `fall-2009`…`fall-2026` with localized titles. |
| `GET /content/v2/discover/categories`, `categories/{slug}/sub_categories` | category taxonomy. |
| `static.crunchyroll.com/config/*` | `genres/en-US.json`, `i18n/v3/*`, `cx-web/config.json` — reference configs. |
| `GET /index/v2` → signed CMS (`beta-api`) | alive; **raw model** (25 Frieren season-entries incl. dub variants) — rejected for DB (see §2). |
| `static.crunchyroll.com/datalab-intro-v2/{ep}.json` | intro timestamps (per web research; not core DB). |

## §4. Data-model findings that shape the schema

1. **Feed duplicates**: popularity feed can list a show on 2 tiles (7/1,104 seen; byte-identical;
   identical in two independent captures) → DB keys on unique id, preserves `tile_positions`.
2. **Canonical URLs**: `/series/{id}/{slug_title}` (id REQUIRED — slug-only 404s);
   `/watch/{id}/{slug_title}`; movies = series model. **→ the popular DB's `url` field must be
   corrected** (was slug-only form).
3. **Per-audio-version watch pages** exist (locale-suffixed ids) but the user-facing episode list
   gives canonical episode ids + `versions` array per episode — sufficient.
4. **Region-unavailable series**: full metadata, 0 seasons via `content/v2`, `media_count>0` —
   must be included in the DB with availability info, not silently dropped.
5. **`audio_locales`/`subtitle_locales` arrays are unordered** (API shuffles per call) — compare as sets.
6. **Two counting models**: DB stores the page-facing counts (`episode_count` = CMS `media_count`).
7. **Catalog vs sitemap drift**: sitemaps are a third enumeration source — used for cross-validation.

## §5. Scope decision record (P4)

**IN (the full database):**
1. **Video catalog — complete and provable**: every series id from the union of
   {browse index (refreshed), sitemap series ids} → ~2,148 series;
   per series: CMS metadata; per season: full season objects; per season: full episode lists.
   Ranks/tile positions from a refreshed popularity feed merged in.
2. **Music domain — best effort, explicitly labeled**: artists + music videos + concerts discovered
   via `search type=music` (multi-query) + per-artist expansion. No public enumeration exists
   (404-probed), so completeness is *search-coverage-based* and will be documented as such.
3. **Reference tables**: seasonal tags (72), category taxonomy, genres/i18n configs, A–Z browse index.
4. **Games catalog**: Gatsby page-data JSON (small).
5. **News**: RSS snapshot (en-US) + endpoint documentation.

**OUT (documented):** playback streams/DRM, manga (external platform), store (requires session),
news full crawl, anime-awards data, account-scoped endpoints (watchlists, playheads, home feed).

**Region note**: the DB documents this session's region: **BD (anonymous IP-derived), locale=en-US**.
Multi-region comparison is out of scope (would need egress per region).

## §6. Crawl architecture (P5 design)

- **Client**: `curl` via subprocess (Cloudflare-compatible TLS), Node orchestrator (no npm deps).
- **Auth**: one anonymous token, proactive refresh at ~50 min, reactive on 401/403.
- **Pacing**: ~400ms between requests; exponential backoff on 429/5xx; global cool-down on repeated
  403s. Estimated request budget: 2,148 series + ~2,148 seasons-lists + ~4–6k seasons' episodes
  ≈ **8–10k requests ≈ 60–75 min** for the video tree, plus ~30 for catalog refresh, plus a few
  hundred for music.
- **Resumability**: every response archived immediately under `data/raw/full_crawl/{collection}/{id}.json`;
  a progress ledger; restarts skip completed ids. 404s recorded as such (region-unavailable series may
  have seasons lists that are empty — 200 with `total: 0`).
- **Exhaustion proofs**: catalog crawl must end with an empty overflow page; per-season episode
  counts must equal the response `total`; the sitemap union must be fully covered.
- **Verification (P7)**: (a) every sitemap series id present in DB; (b) sitemap watch-id coverage:
  every canonical episode id (9-char) from CMS must appear in sitemap watch ids, and every un-suffixed
  sitemap watch id must be explained by CMS data (episode/movie); (c) Σ episode counts per season ==
  season `number_of_episodes`; Σ seasons/episodes == series `episode_count` where availability allows;
  (d) popular-feed ranks consistent with refreshed feed; (e) live spot-checks incl. rendered series
  pages (title check via headless Chrome), CMS identity invariant, image liveness; (f) duplicate audit.

## §7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Soft-ban on unsigned CMS bulk scan | pacing + backoff + resumability; signed route exists as fallback (different model — only if unsigned becomes unusable) |
| Live catalog churn during long crawl | snapshot semantics; per-page timestamps; drift measured in verification (proven technique from the popular DB) |
| Long seasons truncation | verified: full season returned in one call (208/208); builder also asserts `len(episodes)==total` |
| Search-based music enumeration gaps | explicit `coverage` metadata in DB; multiple query strategies (a–z, 0–9, common words, artist names from featured) |
| Locale-array shuffling | treat as sets in all comparisons |
| SPA 404s with HTTP 200 | rendered-title checks in verification (headless Chrome), never status-only |
