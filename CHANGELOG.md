# Changelog

All notable changes to the paripari census project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
census releases follow `census-YYYY.MM-REGION` versioning.

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
