#!/usr/bin/env python3
"""
make_manifest.py
---------------
Generates census/<release>/MANIFEST.json: a FAIR-style, checksum-verified inventory
of every published census artifact and provenance bundle.

Fields per file: path, bytes, sha256, role, description.
Also records the census headline counts (read from the compact index + full DB meta)
so the manifest doubles as a machine-readable summary card.

Usage: python3 tools/make_manifest.py [--census 2026.10-BD]
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROLES = {
    "census-": ("census", "the full census database (JSON; gunzip the .gz for the uncompressed file)"),
    "popular-": ("census-popular", "the Most Popular page snapshot database"),
    "full-db-build-report": ("build-report", "extraction-time verification detail (build stage 12)"),
    "popular-build-report": ("build-report", "extraction-time verification detail (build stage 04)"),
    "full-db-verification-report": ("verification-report", "independent verification (stage 13), live checks"),
    "popular-verification-report": ("verification-report", "independent verification (stage 05), live checks"),
    "index.json": ("index", "compact index of the full census (id/rank/title/url/counts per show)"),
}
BUNDLE_ROLES = {
    "browse-capture": ("provenance", "headless-Chrome CDP capture of the live Most Popular page: requests + 552 response bodies"),
    "browse-crawl": ("provenance", "sequential API crawl of the popularity feed (31 pages + exhaustion proof)"),
    "full-crawl": ("provenance", "complete video-tree crawl: catalog, series, seasons, episodes, music, extras, logs, ledgers"),
    "sitemaps": ("provenance", "Google sitemap inventory: 2,044 series URLs, 92,275 watch-page ids, shard stats"),
    "research-probes": ("provenance", "research probing captures: listing surfaces, deep pages, render checks"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def role_for(filename, bundle=False):
    if bundle:
        for k, v in BUNDLE_ROLES.items():
            if filename.startswith(k):
                return v
        return ("provenance", "provenance bundle")
    for k, v in ROLES.items():
        if k in filename:
            return v
    return ("other", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default="2026.10-BD")
    args = ap.parse_args()

    census_dir = os.path.join(ROOT, "census", args.census)
    prov_dir = os.path.join(ROOT, "provenance")

    files = []
    for name in sorted(os.listdir(census_dir)):
        p = os.path.join(census_dir, name)
        if not os.path.isfile(p):
            continue
        role, desc = role_for(name)
        local_only = name.endswith(".full.json")  # uncompressed census is gitignored (regenerable from .gz)
        files.append({
            "path": f"census/{args.census}/{name}",
            "bytes": os.path.getsize(p),
            "sha256": sha256(p),
            "role": role,
            "description": desc,
            "local_only": local_only,
        })
    for name in sorted(os.listdir(prov_dir)):
        p = os.path.join(prov_dir, name)
        if not os.path.isfile(p):
            continue
        role, desc = role_for(name, bundle=True)
        files.append({
            "path": f"provenance/{name}",
            "bytes": os.path.getsize(p),
            "sha256": sha256(p),
            "role": role,
            "description": desc,
            "sanitized": True,
        })

    # headline counts from the compact index + the popular DB meta
    idx_path = os.path.join(census_dir, f"census-{args.census}.index.json")
    idx = json.load(open(idx_path, encoding="utf-8"))
    counts = {
        "shows": len(idx["shows"]),
        "shows_with_popularity_rank": sum(1 for s in idx["shows"] if s.get("popularity_rank")),
        "seasons": sum(s["seasons"] for s in idx["shows"]),
        "episodes": sum(s["episodes"] for s in idx["shows"]),
    }

    manifest = {
        "census": args.census,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checksum_algorithm": "sha256",
        "counts": counts,
        "files": files,
        "notes": [
            "census-*.full.json (uncompressed) is the same byte content as its .gz twin; "
            "it is kept locally and excluded from git (GitHub's 100 MiB per-file limit) — "
            "decompress the .gz to recreate it.",
            "All provenance bundles were passed through tools/sanitize_evidence.py "
            "(anonymous-token redaction) before publication.",
        ],
    }
    out = os.path.join(census_dir, "MANIFEST.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[manifest] wrote {out}: {len(files)} files, counts={counts}")


if __name__ == "__main__":
    main()
