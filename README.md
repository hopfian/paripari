# paripari

> **ぱりぱり** *(paripari)* — Japanese onomatopoeia for "crunchy"; also, ぱりぱりと進む — *"work progressing briskly."*

**A provenance-complete census of the Crunchyroll catalog.**

![census](https://img.shields.io/badge/census-2026.10--BD%20·%20US%20·%20JP-blue)
![shows](https://img.shields.io/badge/shows-6%2C363%20across%203%20regions-green)
![episodes](https://img.shields.io/badge/episodes-71%2C264%20total-green)
![seasons](https://img.shields.io/badge/seasons-4%2C632%20total-green)
![music_videos](https://img.shields.io/badge/music_videos-9%2C188%20total-green)
![license](https://img.shields.io/badge/code-MIT-lightgrey)
![unofficial](https://img.shields.io/badge/unofficial-not_affiliated_with_Crunchyroll-9cf)

---

**paripari** is a reproducible extraction harness and a family of **censuses** — complete, verified,
timestamped snapshots of everything a Crunchyroll regional catalog contains: every series and movie,
every season, every episode, the music domain (artists, music videos, concerts), the popularity
rankings, and the reference taxonomies — with byte-level provenance for every value.

Like a real census, every release is *exhaustive by proof, not by claim*: each crawl demonstrates
exhaustion (empty overflow pages), each build is re-verified against raw archives, and every
discrepancy is classified, documented, and preserved rather than silently "fixed".

> **This is an unofficial, read-only research project.** paripari is not affiliated with or endorsed
> by Crunchyroll or Sony. It collects **publicly served catalog metadata only** — no video streams,
> no DRM circumvention, no accounts, no personal data. See [Ethics & legal](#ethics--legal).

---

## Censuses — 2026.10-BD · 2026.10-US · 2026.10-JP

Three releases are published, each a complete, verified snapshot of one Crunchyroll
regional catalog. **Region, locale and date are recorded inside every artifact.**

| Layer | **2026.10-BD** (Bangladesh) | **2026.10-US** (United States) | **2026.10-JP** (Japan) |
|---|---:|---:|---:|
| Shows (series + movies) — complete id universe | 2,149 | 2,149 | **2,065** |
| — available in region | 1,068 | 2,093 | **0** |
| — region-unavailable (kept, with full metadata) | 1,081 | 56 | 2,065 |
| — with popularity rank (discover/browse feed) | 1,098 | 2,139 | **24** |
| Seasons | 1,628 | 3,004 | **0** |
| Episodes (every field verbatim) | 25,729 | 45,535 | **0** |
| Music: artists / MVs / concerts | 411 / 4,582 / 101 | 409 / 4,606 / 101 | **0 / 0 / 0** |
| Most Popular page snapshot | 1,104 / 1,097 | 2,150 / 2,139 | **n/a — site geo-blocked** |
| Census size (gz) | 13 MB | 21 MB | **1.2 MB** |

The three censuses now span the full range of regional catalog postures: **partial
catalog** (BD: roughly half the sitemap universe playable), **full catalog** (US:
almost everything playable), and **blocked market** (JP: the website geo-blocks itself,
the API serves metadata-only with zero playable content, yet still ranks a 24-title
legacy feed). The same series resolves completely differently per region — *Attack on
Titan* and *Detective Conan* are absent from BD but present in the US; the Fairy Tail
per-audio duplicate-season structure exists in BD but not the US; and in JP the
top-ranked feed title (*Mizu no Kotoba*) is itself unwatchable.

Each id universe is the **union of independent enumerations** — the discover/browse
feed, Crunchyroll's public sitemaps (geo-blocked from JP, so that census uses the
global snapshot with a documented provenance note), and prior captures — because no
single source is complete.

## Quick start

Every example below works identically for `census/2026.10-US/` — swap the release id.

```bash
# decompress a census (13 MB -> 209 MB; the US twin is 21 MB -> 333 MB)
gzip -dk census/2026.10-BD/census-2026.10-BD.full.json.gz

# top 10 most popular shows
jq -r '.shows[0:10][] | "\(.popularity_rank)\t\(.series.title)"' census/2026.10-BD/census-2026.10-BD.full.json

# total seasons and episodes
jq '[.shows[].seasons[]] | {seasons: length, episodes: map(.episodes|length)|add}' census/2026.10-BD/census-2026.10-BD.full.json

# biggest shows by episode count
jq -r '[.shows[] | {t: .series.title, n: ([.seasons[].episodes[]]|length)}] | sort_by(-.n)[0:10][] | "\(.n)\t\(.t)"' census/2026.10-BD/census-2026.10-BD.full.json

# every episode of a season, with durations in minutes
jq -r '.shows[] | select(.series.title=="Frieren: Beyond Journey'"'"'s End") | .seasons[0].episodes[] | "\(.sequence_number)\t\(.title)\t\((.duration_ms/60000)|floor)min"' census/2026.10-BD/census-2026.10-BD.full.json

# a genre census, by popularity
jq -r '[.shows[] | select(.browse.series_metadata.tenant_categories | index("Romance"))] | sort_by(.popularity_rank) | .[0:20][] | "\(.popularity_rank)\t\(.series.title)"' census/2026.10-BD/census-2026.10-BD.full.json

# the compact index only (fast, 0.6 MB)
jq -r '.shows[] | [.popularity_rank, .seasons, .episodes, .title] | @tsv' census/2026.10-BD/census-2026.10-BD.index.json | head
```

## Repository map

```
census/                         THE DATA — one directory per census release
  2026.10-BD/                  Bangladesh-region census (Oct 30–31, 2026)
  2026.10-US/                  United States census (Oct 31, 2026)
  2026.10-JP/                  Japan census (Oct 31, 2026) — blocked market:
                                 site geo-blocked, API metadata-only, 0 playable
                                 episodes, no popular-page artifact (see census meta)
    census-<release>.full.json.gz   the full database (committed)
    census-<release>.full.json       same bytes, uncompressed (local-only; gitignored)
    census-<release>.index.json      compact index: id/rank/title/url/counts per show
    popular-<release>.json           the Most Popular page database (where the page exists)
    *-build-report.json              extraction-time verification detail
    *-verification-report.json       independent live verification (all hard checks)
    MANIFEST.json                    sha256 inventory + headline counts
provenance/                raw evidence, sanitized + compressed (tar.gz)
  *-2026.10.tar.gz                the BD census bundles
  *-2026.10-US.tar.gz             the US census bundles
  browse-capture-…            headless-Chrome capture of the live page (all requests)
  browse-crawl-…              the popularity-feed API crawl (pages + exhaustion proof)
  full-crawl-…                 the complete video-tree crawl (every archived response)
  sitemaps-…                   Google sitemap inventory (2,044 series / 92,275 watch ids)
  research-probes-…             research probing captures (surfaces, render checks)
pipeline/                  the 13-stage extraction + verification pipeline (Node .mjs / Python)
tools/                      repo utilities: evidence sanitizer, manifest generator, validator
docs/                      RESEARCH.md · WEB_RESEARCH_REPORT.md · PLAN.md · SCHEMA.md ·
                           QUIRKS.md · REPRODUCING.md
local/                     (gitignored) working areas — one per census, regenerable
```

**Censuses are versioned like census data**: `census-YYYY.MM-REGION`. The catalog is a living
thing — popularity re-shuffles continuously, titles enter and leave regional feeds — so every
release is a bounded, timestamped snapshot, and the pipeline exists to issue the next one.

## Verification — the whole point

Every release ships its own verification evidence:

- **Double capture**: the Most Popular feed was captured twice independently (a real headless-Chrome
  session scrolling the live page until exhaustion, and a direct sequential crawl of the same API).
  They matched **tile-for-tile: 0 divergent positions out of 1,104**.
- **Exhaustion proofs**: every crawl ends on an *empty overflow page* — completeness is
  demonstrated, never assumed.
- **Byte-verbatim provenance**: the census is recomputed from raw archived API responses and
  compared value-for-value (25,729/25,729 episodes identical).
- **Cross-source reconciliation**: all 2,044 sitemap series ids are present; episode ids are
  reconciled against the 92,275 global watch pages; regional asymmetry is *quantified*, not hand-waved.
- **Live checks**: CMS identity invariants, canonical-URL render checks in the real app
  (not status-code-only — slug-only URLs return HTTP 200 but render "Page not found"), image liveness.
- **Everything else is documented failure analysis**: the checks that failed during development
  found real upstream catalog phenomena — see [docs/QUIRKS.md](docs/QUIRKS.md).

`census/2026.10-BD/full-db-verification-report.json` records all 17 hard checks (all passed at
publication); `popular-verification-report.json` records the 13 checks on the popular-page database.

## Regionality (read this before comparing numbers)

- The region is **BD (Bangladesh)** for the first census and **US (United States)** for the
  second — determined by IP at token time; `locale=en-US` only selects the metadata
  *language*. Crunchyroll catalogs differ per region under per-title licensing.
- The public sitemap is a **global** inventory (92,275 watch pages ≈ 81.5k canonical episode/movie
  targets + ~10.7k per-audio-version pages). Each region's CMS view exposes a different subset:
  BD sees 25,122 canonical episodes (20,409 in the sitemap), the US sees 45,535 (38,369 in the
  sitemap). ~53k sitemap pages remain outside even the US view. All numbers live in each
  census's verification report.
- **Other regions**: the pipeline is region-agnostic — `census-2026.10-US` was issued exactly
  this way, by running the same pipeline from a different egress. Contributions welcome (see
  [CONTRIBUTING.md](CONTRIBUTING.md)).

## Ethics & legal

- **Read-only public metadata.** The pipeline uses the same public, unauthenticated API the website
  itself calls, at polite rates (~2–3 req/s, sequential or lightly sharded, with backoff).
- **No circumvention**: no DRM, no stream downloading, no login, no paywalled content. Everything
  collected is metadata the site serves to anonymous visitors.
- **No personal data**: no accounts, cookies, or user-scoped endpoints were used.
- **Sanitized evidence**: all anonymous tokens (short-lived, expired) were redacted from published
  archives by `tools/sanitize_evidence.py`; the sanitizer's `--check` mode is part of CI.
- **Takedowns**: this is metadata about works, provided for research/analysis with attribution.
  If you represent a rights holder and want something removed, open an issue labeled `takedown`
  and it will be handled promptly.

## License

- **Code, docs, and the original commentary/organization** (pipeline, tools, docs, the compilation
  arrangement): **MIT** — see [LICENSE](LICENSE).
- **The data**: catalog metadata belongs to its rights holders (Crunchyroll, licensors, producers).
  To the extent the *compilation itself* is protectable, it is released under
  **CC BY 4.0** with attribution — see [DATA_LICENSE.md](DATA_LICENSE.md) for exactly what is and
  isn't claimed.

## Citing

```bibtex
@dataset{paripari_census_2026_10_bd,
  title  = {paripari: a provenance-complete census of the Crunchyroll catalog (2026.10-BD)},
  year   = {2026},
  note   = {Unofficial research dataset; not affiliated with Crunchyroll/Sony. Region BD, locale en-US.},
  url    = {https://github.com/hopfian/paripari}
}
```

(`CITATION.cff` ships in the repo root — fill in your GitHub URL before publishing.)

## FAQ

**Why "paripari"?** It's the Japanese onomatopoeia for *crunchy* — an affectionate nod without
using anyone's trademark — and ぱりぱりと進む means "work progressing briskly", which is what a
good extraction pipeline does.

**Why is the full JSON only available as `.gz`?** GitHub hard-blocks files over 100 MiB; the census
is 209 MB uncompressed but 13 MB gzipped, so the compressed twin is the committed artifact.

**Is this legal?** Catalog metadata is largely factual; the compilation is published for research
with attribution, with takedown contact. This is the same posture as long-standing community
projects around the same APIs. It is not legal advice; read [DATA_LICENSE.md](DATA_LICENSE.md) and
decide for your own use case.

**Can you re-run it for my region?** Yes — see [docs/REPRODUCING.md](docs/REPRODUCING.md).
Contributions of new censuses are explicitly welcome.

**Is the catalog "everything Crunchyroll has"?** No — it's everything Crunchyroll *serves in the
census region at census time*, plus the global sitemap universe of series ids (with
region-availability flags). Numbers vs. marketing claims ("50,000+ episodes") measure different
things; the README and verification reports explain exactly what is counted.
