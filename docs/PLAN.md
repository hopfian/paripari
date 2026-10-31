# Crunchyroll Full-Database Extraction — Plan

**Goal:** Extract the complete Crunchyroll video database (every show, season, and
episode reachable by the website), with the same rigor as the Popular-page database:
exhaustive capture, lossless fields, provenance archives, and independent verification.

**Mandated order of work (user requirement):**
1. **Surface survey** — map crunchyroll.com's visible surfaces (nav, listing pages,
   sitemap/robots, static configs, section sites).
2. **Extensive research** — web research (known API knowledge, community projects,
   endpoint documentation) *plus* live endpoint probing on our side.
3. Only then: **design → crawl → build → verify**.

## Phase plan

| # | Phase | Output |
|---|---|---|
| P1 | Surface survey of crunchyroll.com (nav surfaces, sitemaps, robots, static configs, redirect map of legacy listing URLs) | `docs/RESEARCH.md` §Surface |
| P2 | Web research: Crunchyroll API knowledge (endpoints, auth, pagination, known catalog sizes, music/manga/games surfaces) | `docs/RESEARCH.md` §Web research |
| P3 | Live endpoint probing: validate every candidate endpoint, auth, pagination & filter vocabulary against the live service | `docs/RESEARCH.md` §Endpoint probing |
| P4 | Design: scope decision record + target schema + crawl architecture (resumable, rate-limited, archived) | `docs/RESEARCH.md` §Design |
| P5 | Execution: catalog crawl → seasons crawl → episodes crawl (all archived, checkpointed, resumable) | `data/raw/{catalog,seasons,episodes}/` |
| P6 | Build: `crunchyroll_full_db.json` (catalog + seasons + episodes, lossless + added keys) | `crunchyroll_full_db.json` |
| P7 | Verification: internal consistency, cross-source checks (CMS vs browse, sitemap vs catalog, episode sums vs counts), live spot checks | `data/full_db_verification.json` |
| P8 | Documentation: final report + README update | `README.md`, `docs/RESEARCH.md` |

## Scope (working assumptions, to be confirmed in P1–P3)

- **Region/locale:** `en-US` (what the site serves this session). Other locales get
  probed for size comparison and documented; full multi-region crawl only on request.
- **Content:** the video catalog (series + movies → seasons → episodes) with all
  metadata the CMS exposes; popular-page ranks merged in from the existing verified DB.
- **Out of core scope but surveyed:** manga, games, music, news, store — documented,
  and extracted only if a clean official data surface exists.
- **Playback streams** (HLS/DRM manifests) are not metadata; whatever the CMS episode
  objects expose is kept, but stream-license fetching is out of scope.

## Engineering constraints (from prior verified work)

- All HTTP via `curl` (Cloudflare rejects other TLS fingerprints).
- Anonymous token via `POST /auth/v1/token` (`cr_web` client); refresh on 401/403;
  exponential backoff on 429/5xx; ≤3 req/s pacing.
- Every response archived to disk immediately (crash-safe, resumable).
- Every crawl must prove exhaustion (empty overflow page / last-page short).
- Independent cross-verification required before any dataset is trusted.
