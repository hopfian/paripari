# paripari — repo utilities (everything else is in pipeline/ and tools/)

RELEASE ?= 2026.10-BD

.PHONY: help census-extract provenance-extract validate sanitize-check manifest

help:
	@echo "make census-extract      — decompress the census JSON (gz -> 209 MB file)"
	@echo "make provenance-extract  — untar all provenance bundles into local/work/"
	@echo "make validate            — JSON validity + manifest checksums + census self-consistency + syntax"
	@echo "make sanitize-check      — verify no tokens remain in provenance bundles"
	@echo "make manifest            — regenerate census MANIFEST.json"

census-extract:
	gzip -dk census/$(RELEASE)/census-$(RELEASE).full.json.gz
	@echo "-> census/$(RELEASE)/census-$(RELEASE).full.json"

provenance-extract:
	mkdir -p local/work
	for b in provenance/*.tar.gz; do tar -xzf $$b -C local/work; done
	@echo "-> local/work/{browse-capture,browse-crawl,full-crawl,sitemaps,research-probes}"

validate:
	python3 tools/validate.py --release $(RELEASE)

sanitize-check:
	rm -rf /tmp/paripari-sanitize-check && mkdir -p /tmp/paripari-sanitize-check
	for b in provenance/*.tar.gz; do tar -xzf $$b -C /tmp/paripari-sanitize-check; done
	python3 tools/sanitize_evidence.py /tmp/paripari-sanitize-check --check
	rm -rf /tmp/paripari-sanitize-check
	@echo "  [ok] no tokens in published provenance"

manifest:
	python3 tools/make_manifest.py --census $(RELEASE)
