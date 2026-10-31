# Reproducing & issuing censuses

Everything in this repository is reproducible: the published census can be regenerated
byte-for-byte from the provenance bundles offline, and a fresh census can be extracted from
the live site by running the pipeline end to end.

## Requirements

| Tool | Version | Used by |
|---|---|---|
| Node.js | ≥ 22 (tested 26) | stages 01, 03, 06, 08, 09, 10 |
| Python | ≥ 3.11 (tested 3.14) | stages 02, 04, 05, 07, 11, 12, 13, tools |
| curl | any recent | **all HTTP** (Cloudflare accepts curl's TLS fingerprint, rejects Node's fetch) |
| jq | any recent | validation, quick queries |
| Google Chrome | any recent | CDP stages 01, 06 (verification render checks) |
| GNU make, tar, gzip | standard | repo utilities |

**No npm/pip dependencies.** The region of a census is determined by your **egress IP**
at token time; `locale=en-US` selects only the metadata language.

## A. Verify the published census (offline, ~1 minute)

```bash
git clone https://github.com/hopfian/paripari && cd paripari
make provenance-extract      # untar the bundles into local/work/
gzip -dk census/2026.10-BD/census-2026.10-BD.full.json.gz
python3 pipeline/12_build_full_db.py    # rebuild from raw archives — must be byte-identical
python3 pipeline/04_build_db.py         # rebuild the popular DB
```

Both builds end with `ALL CHECKS PASSED`. Stage 13 additionally performs **live** checks
(below) — its published report is the verification record for census 2026.10-BD.

## B. Run the full pipeline from the live site (a new census)

Research (already done for the Crunchyroll surface — results in `docs/RESEARCH.md`;
re-run only if the site's API changes):

```bash
node pipeline/01_cdp_capture.mjs                      # real-browser capture of the page
python3 pipeline/02_analyze_captures.py               # identify the API
python3 pipeline/07_sitemap_enum.py                   # sitemap universe (2,044 series / 92,275 watch ids)
node pipeline/06_surface_prober.mjs pipeline/probe-lists/surfaces.txt
```

Extraction & build (region = your egress IP):

```bash
node  pipeline/03_fetch_api_full.mjs                  # popular feed crawl (exhaustion proof)
python3 pipeline/04_build_db.py                       # popular DB + build checks
node  pipeline/08_refresh_catalog.mjs                  # refresh feed for current ranks
node  pipeline/09_crawl_video_tree.mjs                 # ~2,149 series → seasons → episodes
                                                        # speed up: run 3 shards in parallel:
                                                        #   node pipeline/09... 0 3 & node pipeline/09... 1 3 & node pipeline/09... 2 3
node  pipeline/10_crawl_music.mjs                      # music domain (search + per-artist)
python3 pipeline/11_fetch_extras.py                    # reference tables
python3 pipeline/12_build_full_db.py                   # assemble + all build checks
```

Verification (must fully pass before a census is publishable):

```bash
python3 pipeline/13_verify_full_db.py                  # offline recomputation + live checks
python3 pipeline/05_verify.py                          # popular DB verification
```

## C. Publish the release

```bash
cd census/<release> && gzip -9 -k census-<release>.full.json   # ≤100 MiB artifact for git
python3 tools/make_manifest.py --census <release>
# stage + sanitize + bundle evidence:
rm -rf /tmp/staging && mkdir -p /tmp/staging
cp -r local/work/browse-crawl local/work/browse-capture local/work/full-crawl local/work/sitemaps /tmp/staging/
rm -rf /tmp/staging/browse-capture/screenshots          # artwork stays local-only
mkdir /tmp/staging/research-probes && cp -r local/work/research-probes/* /tmp/staging/research-probes/
python3 tools/sanitize_evidence.py /tmp/staging         # redact anonymous tokens
python3 tools/sanitize_evidence.py /tmp/staging --check # must exit 0
for b in browse-capture browse-crawl full-crawl sitemaps research-probes; do
  tar -czf provenance/$b-$(date +%Y.%m).tar.gz -C /tmp/staging $b
done
python3 tools/make_manifest.py --census <release>       # pick up the new bundles
# then update CHANGELOG.md and open the PR (see CONTRIBUTING.md)
```

## Expected runtimes (census 2026.10-BD)

| Stage | Runtime |
|---|---|
| 01 browser capture (auto-scroll to exhaustion) | ~15 min |
| 03/08 feed crawls | ~1 min each |
| 07 sitemaps | ~1 min |
| 09 video tree (~8,000 requests, 3 shards) | ~35 min |
| 10 music (~4,700 requests) | ~20 min |
| 11 extras | ~1 min |
| 12 build | ~30 s |
| 13 verification (offline + live + headless render checks) | ~5 min |

## Operational notes

- **Pacing & politeness**: ~350 ms between requests per worker (≤3 workers), exponential
  backoff on 429/5xx, token refresh on 401/403. Do not raise the concurrency without
  discussion (see CONTRIBUTING.md).
- **Resumability**: stages 09/10 skip existing archive files — a killed run restarts where
  it stopped. Envelopes are `{status, fetched_at, body}`; 404s are recorded as such.
- **Completeness proofs**: a crawl is only complete when the *overflow page is empty*;
  the same standard applies to any future census.
- **Verification protocol**: the independent verifier (13) recomputes the census from raw
  archives, byte-compares episode arrays, reconciles against the sitemap universe,
  classifies every anomaly against the documented quirk set, and runs live spot checks
  (CMS identity invariant + rendered-page checks via headless Chrome — status-code-only
  checks are explicitly insufficient: slug-only URLs return HTTP 200 but render 404).
- **Known instability**: the popularity feed drifts **hourly** (ranks shuffle; new titles
  enter; a 2026-10-30 vs 31 comparison measured 4 entrants/10 leavers in the deep tail).
  Ranks are meaningful only together with their extraction timestamp.
