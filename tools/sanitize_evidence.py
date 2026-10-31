#!/usr/bin/env python3
"""
sanitize_evidence.py
--------------------
Security sweep for evidence/provenance archives before publication.

What it redacts (in-place, in the directory given):
  1. Anonymous Bearer tokens: any JWT-shaped string (eyJ...) -> "REDACTED-JWT".
     (These were short-lived anonymous tokens — expired long before publication —
     but publishing them would still be pointless operational hygiene debt.)
  2. `"Authorization": "Bearer ..."` header values -> "Bearer [REDACTED]".
  3. `access_token` / `refresh_token` JSON values -> "[REDACTED-ANONYMOUS-TOKEN]".
  4. `ETP-Anonymous-Id` header values -> "[REDACTED]" (rotating device ids).

Public, non-secret values are intentionally KEPT (they are part of the research
record and are already public knowledge in the open-source community):
  - the `Authorization: Basic Y3Jfd2ViOg==` header (the public web client "cr_web:");
  - the `grant_type=client_id` anonymous auth flow;
  - endpoint URLs and query parameters.

Usage:
  python3 tools/sanitize_evidence.py <directory> [--check]
--check: only report findings without modifying (exit 1 if anything remains).
"""
import argparse
import os
import re
import sys

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}")
AUTH_BEARER_RE = re.compile(r'("Authorization"\s*:\s*")Bearer [^"\\]*(")')
ACCESS_TOKEN_RE = re.compile(r'("(?:access_token|refresh_token)"\s*:\s*")[^"]*(")')
ETP_RE = re.compile(r'("ETP-Anonymous-Id"\s*:\s*")[0-9a-fA-F-]{36}(")')


def redact(text):
    text = JWT_RE.sub("REDACTED-JWT", text)
    text = ACCESS_TOKEN_RE.sub(r"\1[REDACTED-ANONYMOUS-TOKEN]\2", text)
    text = AUTH_BEARER_RE.sub(r"\1Bearer [REDACTED]\2", text)
    text = ETP_RE.sub(r"\1[REDACTED]\2", text)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--check", action="store_true", help="report only; do not modify")
    args = ap.parse_args()

    checked = modified = 0
    findings = []
    for dirpath, _, files in os.walk(args.directory):
        for name in files:
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, IsADirectoryError):
                continue  # binary evidence (screenshots) — excluded from bundles anyway
            checked += 1
            new = redact(text)
            if new != text:
                findings.append(path)
                if not args.check:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new)
                    modified += 1
    action = "remaining" if args.check else "redacted in"
    print(f"[sanitize] {checked} text files scanned, {len(findings)} with secrets ({action} {len(findings) if args.check else modified})")
    for p in findings[:10]:
        print(f"   {p}")
    if args.check and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
