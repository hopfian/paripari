# Security policy

## Scope

This repository is a read-only metadata extraction toolkit. It runs no services, holds no
secrets, and accepts no untrusted input at runtime. Security review therefore focuses on
**what the project publishes**:

- **No credentials.** All API tokens used during extraction are anonymous, short-lived
  (≈1 hour), and expired before anything is published. Evidence archives are passed through
  `tools/sanitize_evidence.py` (JWT/token redaction) whose `--check` mode runs in CI.
- **No personal data.** No accounts, cookies, or user-scoped endpoints are used anywhere
  in the pipeline. Verify this claim any time with a grep for `Authorization` in published
  archives after sanitization.
- **No secrets in history.** If a contributor ever accidentally commits a secret, do NOT open
  a public issue — see reporting below.

## Reporting a vulnerability

If you find a security issue in the pipeline code or published artifacts, use GitHub's
**private vulnerability reporting** on this repository, or email the maintainer listed in
`CITATION.cff`. Expect a response within a few days.

**Out of scope:** Crunchyroll's own infrastructure and security. Do not probe, stress, or
attack crunchyroll.com — if you find issues *in their service*, report them to them, not here.
This project will not host tooling that degrades their service or circumvents access controls.
