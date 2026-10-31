# Censuses

A **census** is a complete, verified, timestamped snapshot of one Crunchyroll regional
catalog. Releases are named `census-YYYY.MM-REGION` — like census data, they are bounded
in time and space, and re-issued rather than updated.

## Why "census" and not "dump"

A dump claims to contain everything. A census *proves* it, per release:

1. **Enumeration** — the id universe is the union of multiple independent sources
   (popularity feed, Google sitemaps, prior captures), because no single source is complete.
2. **Exhaustion proof** — every crawl terminates on an empty overflow page.
3. **Byte-verbatim provenance** — the published database is recomputed from archived raw
   API responses and compared value-for-value.
4. **Cross-source reconciliation** — sitemap inventories are checked against the crawl,
   with regional asymmetry quantified rather than excused.
5. **Live verification** — identity invariants and rendered-page checks against the
   current site at publication time.
6. **Honest caveats** — everything that could not be proven complete (the music domain
   has no enumeration endpoint) is labeled as such in the artifact itself.

## Release contents (`census/<release>/`)

| File | What it is |
|---|---|
| `census-*.full.json.gz` | **The census** — the full database (2,149 shows with nested seasons + episodes, music, reference tables, and a `database` meta block with all provenance & verification). Committed; `gunzip` for the 209 MB uncompressed twin. |
| `census-*.full.json` | Same bytes, uncompressed. Local-only (gitignored — GitHub's 100 MiB per-file limit); regenerate with `gzip -dk`. |
| `census-*.index.json` | Compact index: `id, popularity_rank, title, canonical_url, availability, season/episode counts, source flags` per show. Fast to load and grep. |
| `popular-*.json` | The Most Popular page database: every tile of the feed in popularity order, with ranks, tile positions, ratings, and its own verification block. |
| `full-db-build-report.json` | Extraction-time checks from the build stage (recomputation, duplicate audits, quirk classification). |
| `full-db-verification-report.json` | The independent verification run (all hard checks, informational drift scan, sitemap reconciliation). |
| `popular-build-report.json` / `popular-verification-report.json` | The same for the popular-page database. |
| `MANIFEST.json` | sha256 + size + role for every artifact, plus headline counts. |

## Headline numbers

| | 2026.10-BD | 2026.10-US | 2026.10-JP |
|---|---:|---:|---:|
| shows (available / not available) | 2,149 (1,068 / 1,081) | 2,149 (2,093 / 56) | 2,065 (0 / 2,065) |
| ranked by the live feed | 1,098 | 2,139 | 24 |
| seasons · episodes | 1,628 · 25,729 | 3,004 · 45,535 | 0 · 0 |
| music (artists / MVs / concerts) | 411 / 4,582 / 101 | 409 / 4,606 / 101 | 0 / 0 / 0 |
| popular page (tiles / unique) | 1,104 / 1,097 | 2,150 / 2,139 | **n/a — geo-blocked** |

> **Blocked-market censuses** (like 2026.10-JP): the region's website geo-blocks itself,
> so the `popular-*.json` page-snapshot artifact and its verification reports are
> legitimately absent; the API popularity feed is still recorded inside the census
> (`browse` items + `popularity_rank`). See each census's `database` meta and
> `docs/QUIRKS.md` for the full regional findings.

## Issuing a new census

See [../CONTRIBUTING.md](../CONTRIBUTING.md) and [../docs/REPRODUCING.md](../docs/REPRODUCING.md).
The pipeline is region-agnostic; your egress IP determines the region. All 17 hard checks
must pass before a census can be merged.
