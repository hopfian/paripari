## What & why

<!-- One-paragraph summary of the change and its purpose. -->

## Checklist

- [ ] If this touches pipeline behavior: the relevant verification stages still pass
      (`04`, `12` offline; `05`, `13` for live checks where applicable).
- [ ] If this adds/changes published artifacts: `make validate` passes and
      `MANIFEST.json` was regenerated (`make manifest`).
- [ ] If this adds evidence: it was sanitized and `make sanitize-check` passes.
- [ ] Docs updated (`docs/`, READMEs, CHANGELOG when user-visible).
- [ ] No secrets, no screenshots of the site, no personal data.
- [ ] Politeness preserved: request pacing unchanged (or justified in the PR).
