# Provenance bundles

Raw evidence backing every claim in the census — every API response the pipeline ever
received, sanitized and compressed. Unpack into `local/work/` to re-run any build or
verification stage offline:

```bash
make provenance-extract      # or: for b in provenance/*.tar.gz; do tar -xzf $b -C local/work; done
```

## Bundle inventory

| Bundle | Original working path | Contents |
|---|---|---|
| `browse-capture-2026.10.tar.gz` | `local/work/browse-capture/` | BD census — headless-Chrome CDP session that scrolled the live Most Popular page to exhaustion: 2,914 requests (`requests.json`), 552 captured response bodies (`bodies/`), the bodies index with sha256s, session meta. (Screenshots of the page were deliberately **excluded** from publication — they contain rights-holder artwork — and remain local-only.) |
| `browse-crawl-2026.10.tar.gz` | `local/work/browse-crawl/` | BD — the sequential popularity-feed crawl: 31 archived pages + the crawl manifest with the exhaustion proof (empty overflow page). |
| `full-crawl-2026.10.tar.gz` | `local/work/full-crawl/` | BD — the complete video-tree crawl: refreshed catalog pages + manifest, 2,149 series envelopes, 2,149 season lists, 1,628 episode lists, the music domain, reference extras, run logs and per-shard ledgers. Every envelope is `{status, fetched_at, body}`. |
| `sitemaps-2026.10.tar.gz` | `local/work/sitemaps/` | BD snapshot — the public sitemap inventory: 2,044 series URLs/ids, 92,275 watch-page URLs/ids, per-shard stats. |
| `research-probes-2026.10.tar.gz` | `local/work/research-probes/` | BD — surface-research captures (listing pages, deep pages, canonical-URL checks, render checks) — the evidence behind `docs/RESEARCH.md`. |
| `browse-capture-2026.10-US.tar.gz` | `local/work-US/browse-capture/` | US census — the equivalent CDP capture of the live US feed (4,418 requests, 176 bodies; 6,450 tile anchors = 2,150 tiles × 3, exhaustion proven). |
| `browse-crawl-2026.10-US.tar.gz` | `local/work-US/browse-crawl/` | US — 60 archived feed pages + manifest with exhaustion proof. |
| `full-crawl-2026.10-US.tar.gz` | `local/work-US/full-crawl/` | US — 2,149 series envelopes, 2,149 season lists, **3,004 episode lists**, the US music domain (409 artists / 4,606 MVs / 101 concerts), US extras, logs, ledgers. |
| `sitemaps-2026.10-US.tar.gz` | `local/work-US/sitemaps/` | US snapshot of the (global) sitemap inventory. |
| `research-probes-2026.10-US.tar.gz` | `local/work-US/research-probes/` | US — render-check captures from the US verification runs. |

> Naming: BD bundles carry no region suffix (it was the first census); US bundles are
> suffixed `-US`. Future censuses should use suffixed names from the start
> (`*-YYYY.MM-REGION.tar.gz`).

## Sanitization

Every bundle was passed through `tools/sanitize_evidence.py` before publication:

- anonymous Bearer JWTs and `access_token`/`refresh_token` values → `[REDACTED]`
  (they were short-lived, already-expired anonymous tokens; hygiene, not secrecy);
- `ETP-Anonymous-Id` device ids → `[REDACTED]`;
- intentionally **kept** (public, non-secret, part of the research record): the public
  `cr_web` basic-auth header, the anonymous `grant_type=client_id` flow, all endpoint URLs.

The sanitizer's `--check` mode runs in CI to guarantee no token-shaped string exists in
any published bundle.
