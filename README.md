# paripari

> **ぱりぱり** *(paripari)* — Japanese onomatopoeia for "crunchy"; also, ぱりぱりと進む — *"work progressing briskly."*

**A provenance-complete census of the Crunchyroll catalog.**

![census](https://img.shields.io/badge/census-2026.10--BD-blue)
![shows](https://img.shields.io/badge/shows-2%2C149-green)
![episodes](https://img.shields.io/badge/episodes-25%2C729-green)
![seasons](https://img.shields.io/badge/seasons-1%2C628-green)
![music_videos](https://img.shields.io/badge/music_videos-4%2C582-green)
![region](https://img.shields.io/badge/region-BD-orange)
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

## Census 2026.10-BD — the first release

Extracted **October 30–31, 2026** from the **Bangladesh-region catalog** (`country: BD`,
IP-derived at token time; metadata language `en-US`). Region, locale and date are recorded inside
every artifact.

| Layer | Count |
|---|---:|
| Shows (series + movies) — the complete id universe | **2,149** |
| — available in region | 1,068 |
| — region-unavailable (kept, with full metadata) | 1,081 |
| — with popularity rank (from the live Most Popular feed) | 1,098 |
| Seasons | **1,628** |
| Episodes (every field verbatim: durations, air dates, versions, subs, maturity…) | **25,729** |
| Music: artists / music videos / concerts | 411 / **4,582** / 101 |
| Most Popular page snapshot (separate database) | 1,104 tiles / 1,097 unique shows |

The id universe is the **union of three independent enumerations** — the discover/browse feed
(1,104 tiles), Crunchyroll's public sitemaps (2,044 series URLs), and the original page capture —
because no single source is complete: 1,051 sitemap series never appear in the browse index
(region-unavailable titles), and 104 browse-index series are absent from the sitemap.

## Quick start

```bash
# decompress the census (13 MB -> 209 MB)
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
census/2026.10-BD/         THE DATA — a complete, verified census release
  census-2026.10-BD.full.json.gz   the full database (committed, 13 MB)
  census-2026.10-BD.full.json       same bytes, uncompressed (local-only; gitignored)
  census-2026.10-BD.index.json      compact index: id/rank/title/url/counts per show
  popular-2026.10-BD.json           the Most Popular page database (12 MB, committed)
  *-build-report.json               extraction-time verification detail
  *-verification-report.json        independent live verification (all hard checks)
  MANIFEST.json                     sha256 inventory + headline counts
provenance/                raw evidence, sanitized + compressed (tar.gz)
  browse-capture-2026.10.tar.gz      headless-Chrome capture of the live page (5,525 requests)
  browse-crawl-2026.10.tar.gz        the popularity-feed API crawl (31 pages + exhaustion proof)
  full-crawl-2026.10.tar.gz          the complete video-tree crawl (~8,000 archived responses)
  sitemaps-2026.10.tar.gz            Google sitemap inventory (2,044 series / 92,275 watch ids)
  research-probes-2026.10.tar.gz     research probing captures (surfaces, deep pages, render checks)
pipeline/                  the 13-stage extraction + verification pipeline (Node .mjs / Python)
tools/                     repo utilities: evidence sanitizer, manifest generator
docs/                      RESEARCH.md · WEB_RESEARCH_REPORT.md · PLAN.md · SCHEMA.md ·
                           QUIRKS.md · REPRODUCING.md
local/                     (gitignored) working area — regenerable via the pipeline
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

- The region is **BD (Bangladesh)** — determined by IP at token time; `locale=en-US` only selects
  the metadata *language*. Crunchyroll catalogs differ per region under per-title licensing.
- The public sitemap is a **global** inventory (92,275 watch pages ≈ 81.5k canonical episode/movie
  targets + ~10.7k per-audio-version pages). This region's CMS view exposes 25,122 canonical
  episodes: 20,409 overlap with the sitemap, 4,713 are BD-visible-but-not-sitemapped, and 71,866
  sitemap pages belong to other regions. All numbers live in the verification report.
- **Other regions**: the pipeline is region-agnostic — run it from a different egress and it will
  issue `census-YYYY.MM-XX` for that region. Contributions welcome (see
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
