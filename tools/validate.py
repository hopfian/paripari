#!/usr/bin/env python3
"""
validate.py
-----------
Offline validation for the published repository (used by `make validate` and CI):

  1. every committed JSON artifact parses;
  2. every MANIFEST.json checksum matches the artifact on disk (published files only);
  3. the census is internally consistent (counts agree across full DB, index, manifest;
     ranks contiguous; verification reports record all-checks-passed);
  4. optional --skip-syntax to only run data checks.

Exits non-zero on the first class of failure. Deliberately never touches the network.
"""
import argparse
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fail(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default="2026.10-BD")
    ap.add_argument("--skip-syntax", action="store_true")
    args = ap.parse_args()

    census_dir = os.path.join(ROOT, "census", args.release)

    # 1. JSON validity
    n = 0
    for f in (glob.glob(os.path.join(census_dir, "*.json")) + glob.glob(os.path.join(ROOT, "docs", "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                json.load(fh)
            n += 1
        except Exception as e:
            fail(f"{f}: {e}")
    print(f"  [ok] {n} census/docs JSON files parse")

    # 2. manifest checksums
    man = json.load(open(os.path.join(census_dir, "MANIFEST.json"), encoding="utf-8"))
    published = [e for e in man["files"] if not e.get("local_only")]
    for entry in published:
        p = os.path.join(ROOT, entry["path"])
        if not os.path.exists(p):
            fail(f"missing published artifact {entry['path']}")
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if h != entry["sha256"]:
            fail(f"checksum mismatch {entry['path']}")
    print(f"  [ok] MANIFEST sha256 verified for {len(published)} published files")

    # 3. census self-consistency (needs the decompressed full DB if present)
    full_path = os.path.join(census_dir, f"census-{args.release}.full.json")
    if os.path.exists(full_path):
        db = json.load(open(full_path, encoding="utf-8"))
        idx = json.load(open(os.path.join(census_dir, f"census-{args.release}.index.json"), encoding="utf-8"))
        c = db["database"]["counts"]
        assert c["shows"] == len(db["shows"]) == len(idx["shows"]) == man["counts"]["shows"], "show counts disagree"
        assert c["seasons"] == sum(len(s.get("seasons") or []) for s in db["shows"]) == man["counts"]["seasons"], "season counts disagree"
        eps = sum(len(se.get("episodes") or []) for s in db["shows"] for se in (s.get("seasons") or []))
        assert c["episodes"] == eps == man["counts"]["episodes"], "episode counts disagree"
        assert db["database"]["verification"]["all_passed"] is True, "census meta claims failed verification"
        ranks = [s["popularity_rank"] for s in db["shows"] if s.get("popularity_rank")]
        assert ranks == list(range(1, len(ranks) + 1)), "popularity ranks not contiguous"
        print(f"  [ok] census self-consistency: {man['counts']}")
    else:
        print("  [note] uncompressed census absent (run `make census-extract`) — skipped deep checks")

    # 4. verification reports record passing runs (the popular-page report exists
    #    only for censuses where the region's website serves the Most Popular page;
    #    blocked-market censuses like 2026.10-JP legitimately omit it)
    for rep in ("full-db-verification-report.json", "popular-verification-report.json"):
        p = os.path.join(census_dir, rep)
        if rep == "popular-verification-report.json" and not os.path.exists(p):
            print("  [note] popular-verification-report.json absent (blocked-market census) — skipped")
            continue
        r = json.load(open(p, encoding="utf-8"))
        key = "hard_checks_passed" if "hard_checks_passed" in r else "all_checks_passed"
        if not r.get(key):
            fail(f"{rep} records a failed verification run")
    print("  [ok] verification reports record all-checks-passed")

    if not args.skip_syntax:
        import subprocess
        for f in glob.glob(os.path.join(ROOT, "pipeline", "*.mjs")):
            subprocess.run(["node", "--check", f], check=True)
        subprocess.run([sys.executable, "-m", "py_compile",
                        *glob.glob(os.path.join(ROOT, "pipeline", "*.py")),
                        *glob.glob(os.path.join(ROOT, "tools", "*.py"))], check=True)
        print("  [ok] pipeline + tools syntax")

    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
