---
name: New census
about: You ran the pipeline from another region and want to contribute the census
labels: census
---

**Census release id** (`YYYY.MM-REGION`)

**Token country + locale** (from the crawl logs: `[tree] token country: XX`)

**All hard checks passed?** (paste the tail of `pipeline/13_verify_full_db.py`)

**MANIFEST.json counts** (paste `jq .counts census/<release>/MANIFEST.json`)

**Notable regional observations** (id-universe size differences, quirks specific to your region, …)

- [ ] Provenance bundles sanitized (`tools/sanitize_evidence.py --check` clean)
- [ ] CHANGELOG.md entry added
- [ ] Census README row added (if headline numbers differ notably)
