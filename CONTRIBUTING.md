# Contributing to paripari

Thanks for wanting to help! This project welcomes contributions of three kinds.

## 1. New censuses (most wanted)

A census is a regional snapshot: `census-YYYY.MM-REGION`. The pipeline is region-agnostic —
**the region comes from your egress IP at token time**, so anyone in another part of the
world can issue a census for their own catalog.

To contribute one:

1. Read [docs/REPRODUCING.md](docs/REPRODUCING.md) and run stages `08 → 09 → 10 → 11 → 12 → 13`
   (the research stages `01–07` have already been run once and their findings are in
   [docs/RESEARCH.md](docs/RESEARCH.md); re-run them only if you want to re-verify the surface map).
2. All **17 hard verification checks** must pass before a census can be merged — no exceptions.
   A census that fails checks is not a census.
3. Add `census/YYYY.MM-XX/` with the same artifact set as `2026.10-BD`, its `MANIFEST.json`
   (`tools/make_manifest.py --census YYYY.MM-XX`), and a `CHANGELOG.md` entry.
4. PR title: `census: add YYYY.MM-XX`.

Please be a polite crawler: the pipeline's pacing (~2–3 req/s with backoff) is part of the
project's ethics — do not "optimize" it without discussion.

## 2. Quirk reports

Crunchyroll's catalog has documented inconsistencies (see [docs/QUIRKS.md](docs/QUIRKS.md)).
If you spot a new one — a count that disagrees with a listing, a phantom reference, a
duplicate — open a **quirk report** issue with: ids involved, what the API says, when you
observed it, and (ideally) a minimal reproduction. Characterized quirks get promoted into
the census metadata and the catalogue doc.

## 3. Pipeline & docs improvements

- Keep scripts self-contained (they are their own provenance) — shared helpers go through
  a design discussion first.
- Every behavioral change must keep the verification checks green; run
  `python3 pipeline/13_verify_full_db.py` offline sections at minimum.
- Node ≥ 22 / Python ≥ 3.11, no npm/pip dependencies — this is a feature (the whole pipeline
  runs on a base system with `curl`, `jq`, and Chrome). If you need a dependency, argue for it.
- Docs live in `docs/`; the main README is the front door — keep the tone precise and honest.

## Development setup

```bash
git clone https://github.com/hopfian/paripari
cd paripari
make provenance-extract   # unpack raw archives into local/work/
make validate             # JSON validity + manifest checksums + syntax checks
```

## Commit style

Conventional-ish and boring is good: `census: add 2026.11-BD`, `pipeline: fix token refresh in 09`,
`docs: expand QUIRKS`. Squash WIP; one logical change per commit.
