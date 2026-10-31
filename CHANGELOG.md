# Changelog

All notable changes to the paripari census project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
census releases follow `census-YYYY.MM-REGION` versioning.

## [census-2026.10-JP] — 2026-10-31

The third census: a complete, verified snapshot of the Crunchyroll **Japan catalog**
(`country: JP`, extracted from a Japanese egress, October 31, 2026) — a **blocked-market
census**, the most structurally distinct of the three:

- **The Crunchyroll website geo-blocks itself in Japan**: every page redirects to
  `currently-unavailable-in-your-location` (titled "Welcome | Some Experiences Not
  Available in Your Area"). Captured with headless Chrome (122 requests, final URL
  and 0 tiles recorded in the browse-capture bundle).
- **Sitemaps are geo-blocked too** (HTTP 301 to the block page from JP egress); the
  census therefore uses the global sitemap snapshot fetched the same day from the US
  egress, documented in a provenance note inside the bundle.
- **The API still serves a pure metadata view**: 2,065 series — every one
  `availability_status: unavailable`, **0 seasons, 0 episodes** across the entire
  region. No popular-page database artifact is published for this census (the page
  does not exist here); the API's popularity feed is still fully recorded: 24 ranked
  titles — the legacy-survivor catalog (*Mizu no Kotoba*, *Tofugu*, *Eyeshine*,
  *Fairy Tail Podcast*…).
- **Music domain: empty** (0 artists / 0 MVs / 0 concerts) — consistent with
  Crunchyroll Music's documented unavailability in Japan.
- A documented upstream inconsistency: the JP feed claims *Mizu no Kotoba* is
  `available` while the CMS marks it `unavailable` with 0 seasons — feed metadata is
  stale-global in blocked markets.
- All 17 hard checks passed (byte-verbatim recomputation, exhaustion proofs,
  sitemap reconciliation with the region quantified at zero content).

### Corrections

- **[census-2026.10-US] region label corrected**: the published US census carried the
  region `country` as a BD-era fallback string due to a log-path bug in stage 12 (the
  true region — `US` — was recorded in the crawl logs all along). Both affected
  censuses were rebuilt and re-verified with the fix; the region is now parsed
  correctly (`US` / `JP`) and the fallback is an explicit "unknown" rather than a
  wrong default. No show/season/episode data was affected.

## [census-2026.10-US] — 2026-10-31

The second census: a complete, verified snapshot of the Crunchyroll **United States
catalog** (`country: US`, extracted from a Los Angeles egress, October 31, 2026).

### Data

- **2,149 shows** — 2,093 available in region, 56 region-unavailable; **2,139 ranked**
  by the live Most Popular feed (2,150 tiles; the feed listed 11 shows on two tiles).
- **3,004 seasons** and **45,535 episodes** (all 45,535 ids unique — the per-audio
  duplicate-season phenomenon observed in the BD census **does not manifest in the
  US catalog structure**).
- **Music domain**: 409 artists, 4,606 music videos, 101 concerts.
- Most Popular page database: 2,150 tiles / 2,139 unique shows.

### Verification

- All 17 full-census hard checks + all 13 popular-DB checks passed.
- Cross-capture evidence with honest live-drift semantics: the browser capture and
  the API crawl ran ~20 minutes apart; the live feed drifted between the two passes
  (98.97% id-set overlap, identical head, divergences confined beyond tile 1,801) —
  all quantified in the popular DB's verification block.
- A live episode publication was caught in the act: *Detective Conan* had 587
  playable episodes at extraction and 588 two hours later — the archived envelope
  proves extraction-time consistency; the +1 is documented live drift.

### Regional findings (new quirk data)

- The upstream-inconsistent-season count grows to **84** (vs 21 in BD) and phantom
  season references to **74 entries across 10 groups** (vs 68 across 7) — more
  available content surfaces more upstream inconsistencies.
- The duplicate-tile phenomenon fluctuates heavily: 11 duplicated ids at extraction,
  21 in the browser pass minutes earlier, **85 in the live feed at verification**.
- Sitemap reconciliation from the US view: 38,369 episodes overlap the global
  sitemap, 7,166 are US-visible-but-not-sitemapped, 52,917 sitemap watch pages
  belong to other regions.

### Pipeline

- Multi-census refactor: artifact filenames derive from the census release id
  (`PARI_WORK` / `PARI_CENSUS` env); the per-audio duplicate check and its meta key
  generalized (`per_audio_duplicate_seasons`, with per-series detail) — see the
  schema-evolution note in `docs/SCHEMA.md`. Published censuses are never rewritten.
- Verification semantics refined: extraction-time consistency (DB vs archived
  envelopes) is the hard invariant; live-service drift is classified and documented,
  not failed.

## [census-2026.10-BD] — 2026-10-31

The first census: a complete, verified snapshot of the Crunchyroll **Bangladesh-region
catalog** (metadata locale `en-US`), extracted October 30–31, 2026.

### Data

- **2,149 shows** (series + movies) — the union of the popularity feed, the public
  sitemap series shards, and the original capture; 1,068 available in region,
  1,081 region-unavailable (kept with full metadata and availability notes).
- **1,628 seasons** and **25,729 episodes** (25,122 unique ids), every field verbatim
  from the CMS API (durations, air dates, premium/availability flags, audio versions,
  subtitle locales, maturity data, thumbnails).
- **1,098 shows ranked** by the live Most Popular feed; tile positions preserved,
  including the 7 shows the feed itself lists on two tiles.
- **Music domain**: 411 artists, 4,582 music videos, 101 concerts — search-coverage +
  per-artist expansion (Crunchyroll exposes no music enumeration; documented honestly).
- **Reference tables**: 72 simulcast seasonal tags, category taxonomy, genre config,
  i18n audio/subtitle language tables, A–Z browse index, games catalog snapshot,
  news RSS snapshot, subscription products.
- **Most Popular page database** (`popular-2026.10-BD.json`): 1,104 tiles / 1,097 unique
  shows, verified tile-for-tile against an independent headless-Chrome capture.

### Verification

- 17 hard checks on the full census + 13 on the popular database — **all passing**,
  including byte-verbatim recomputation from raw archives, exhaustion proofs, sitemap
  reconciliation (2,044/2,044 series present; 92,275 watch pages cross-referenced with
  regional asymmetry quantified), live CMS identity invariants, and rendered-page checks.
- 6 upstream catalog quirks discovered, characterized, and preserved verbatim
  (see `docs/QUIRKS.md`): Fairy Tail per-audio duplicate seasons; 21 self-inconsistent
  seasons; 68 phantom season references; popularity-feed duplicate tiles; dual counting
  models; shuffled locale arrays.

### Pipeline

- 13-stage extraction & verification pipeline (research → capture → crawl → build →
  verify), resumable, rate-limited, zero third-party dependencies (Node ≥ 22,
  Python ≥ 3.11, curl, jq, Chrome/CDP).
- Provenance bundles (sanitized, gzipped): browser capture (5,525 requests), browse
  crawl, full video-tree crawl (~8,000 archived responses), sitemaps, research probes.
