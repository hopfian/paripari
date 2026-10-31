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
| `browse-capture-2026.10.tar.gz` | `local/work/browse-capture/` | The headless-Chrome CDP session that scrolled the live Most Popular page to exhaustion: 2,914 requests (`requests.json`), 552 captured response bodies (`bodies/`), the bodies index with sha256s, session meta. (Screenshots of the page were deliberately **excluded** from publication — they contain rights-holder artwork — and remain local-only.) |
| `browse-crawl-2026.10.tar.gz` | `local/work/browse-crawl/` | The sequential popularity-feed crawl: 31 archived pages + the crawl manifest with the exhaustion proof (empty overflow page). |
| `full-crawl-2026.10.tar.gz` | `local/work/full-crawl/` | The complete video-tree crawl: refreshed catalog pages + manifest, 2,149 series envelopes, 2,149 season lists, 1,628 episode lists, the music domain (search + artists + MVs + concerts), reference extras, run logs and per-shard ledgers. Every envelope is `{status, fetched_at, body}`. |
| `sitemaps-2026.10.tar.gz` | `local/work/sitemaps/` | The public sitemap inventory: 2,044 series URLs/ids, 92,275 watch-page URLs/ids, per-shard stats. |
| `research-probes-2026.10.tar.gz` | `local/work/research-probes/` | Surface-research captures (listing pages, deep pages, canonical-URL checks, render checks) — the evidence behind `docs/RESEARCH.md`. |

## Sanitization

Every bundle was passed through `tools/sanitize_evidence.py` before publication:

- anonymous Bearer JWTs and `access_token`/`refresh_token` values → `[REDACTED]`
  (they were short-lived, already-expired anonymous tokens; hygiene, not secrecy);
- `ETP-Anonymous-Id` device ids → `[REDACTED]`;
- intentionally **kept** (public, non-secret, part of the research record): the public
  `cr_web` basic-auth header, the anonymous `grant_type=client_id` flow, all endpoint URLs.

The sanitizer's `--check` mode runs in CI to guarantee no token-shaped string exists in
any published bundle.
