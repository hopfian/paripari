# Upstream catalog quirks

**What this document is.** During verification, several checks "failed" in ways that turned out
to be properties of **Crunchyroll's own catalog data**, not extraction errors. Each was then
characterized precisely (exact ids, exact field diffs, exact scope) and is preserved **verbatim**
in the census — nothing was "fixed", dropped, or silently munged. This is the catalogue of
those findings: §1–6 as documented in the **2026.10-BD** census, plus §7 comparing against the
**2026.10-US** census extracted from the same pipeline.

All of this is also machine-readable inside the census itself:
`census-*.full.json → database.upstream_data_quirks` (with per-item detail lists).

---

## 1. Fairy Tail's per-audio duplicate seasons

**Series:** `G6DQDD3WR` *Fairy Tail* — **329 episode ids each appear 2–3 times** across 9
season-title groups that Crunchyroll models as per-audio "seasons":

> **Regional note (2026.10-US):** this structure **does not exist in the US catalog** —
> the US census has 45,535 episode ids, all unique, zero per-audio duplicate seasons.
> The same series can be packaged completely differently per region.

| Season title | Audio copies |
|---|---|
| Season 1 Part 1 (1-48), Part 2 (49-72), Part 3 (73-98), Part 4 (99-124), Part 5 (125-150), Part 6 (151-175) | ja-JP, de-DE, en-US |
| Season 2 Part 1 (176-226), Part 2 (227-277) | ja-JP, de-DE, en-US |
| Final Season (278-328) | ja-JP, en-US |

- The copies share **the same episode ids**; the objects differ in exactly **one field**:
  `recent_audio_locale`. Sequence numbers are consistent across copies.
- The shared episode objects carry the **original-audio (ja-JP) season's id** in
  `episode.season_id` even when listed under the de-DE/en-US season copies (607 such
  listing entries; each target is a real season the episode is genuinely listed under).
- This matches how Crunchyroll's own series page lists the show.

**Database handling:** every listing preserved verbatim; duplicates classified in the build
report; `season_id` back-references verified to point at real listings.

## 2. Phantom season references

**68 episodes across 7 series (BD census); 74 entries across 10 groups (US census)**
carry a `season_id` pointing at a season that the seasons endpoint **never exposes**
(not present for any series in the region) — hidden, other-region, or unpackaged
seasons. The BD list (the US census records its own set in
`database.upstream_data_quirks`):

| Series | Listing season | Episodes | Phantom targets |
|---|---|---:|---|
| *Peeping Life* | "OVA 3" | 8 | 8 distinct unexposed OVA season ids |
| *Yu-Gi-Oh! 5D's* | "Season 2 (English Dub)" | 32 | `GY2P1D2KY` — apparently the unexposed original-audio season |
| *Bakemonogatari* | "Nademonogatari" | 6 | 2 unexposed season ids |
| *Dragon Raja* | "Dragon Raja II — The Mourner's Eyes" | 19 | `GRVNC2W8X` |
| *King of Eden (English Dub)* | "King of Eden" | 1 | the unexposed EN dub season |
| *Paradise Lost (English Dub)* | "Paradise Lost" | 1 | the unexposed EN dub season |
| *LINK CLICK* | "Link Click" | 1 | `G62PCV3D3` |

Verification guarantees **zero cross-series contamination** — every foreign `season_id` is
either a real same-series listing (Fairy Tail) or one of these phantom ids.

## 3. Self-inconsistent seasons (`number_of_episodes` vs the actual list)

**21 seasons in the BD census; 84 in the US census** where the season object's
`number_of_episodes` disagrees with the episode list the API itself returns (episodes
removed/geo-restricted while the counter wasn't updated — or the reverse). More
available content surfaces more inconsistencies. The **episodes array is the
page-facing truth**; both values are preserved. The BD list:

| Series | Season | Claimed | Listed | Missing sequence numbers |
|---|---|---:|---:|---|
| *Marginal Prince* | `GR5VCDP0W` | 13 | 12 | 7 |
| *One-Punch Man* | `GS00365927JAJP` | 2 | 1 | 2 |
| *POP TEAM EPIC* | `GYMGC3ZN0` | 12 | 7 | 6–9, 11 |
| *Shining Tears X Wind* | `GYX08ME5R` | 13 | 0 | all |
| *Fairy Tail* | `GS00002955ENUS` | 1 | 0 | 1 |
| *The Ambition of Oda Nobuna* | `GYNQJ0Z0Y` | 13 | 14 | — (lists one extra; two entries at seq 0) |
| *Shugo Chara!* | `GR2PW23KR` / `GRDQ4ZKGY` / `GYWEXP00Y` | 51 / 51 / 25 | 50 / 49 / 24 | 19 · 43, 46 · 25 |
| *Fairy Princess Minky Momo* | `GYNQCJEEW` | 63 | 62 | 33 |
| *Boogiepop Phantom* | `GRGGCV7PG` | 12 | 0 | all |
| *King of Thorn* | `GMSE00000017ENUS` | 1 | 0 | 1 |
| *EAT-MAN* | `GYEX421V6` | 12 | 4 | 1, 4, 6–9, 11, 12 |
| *gdgd men's party* | `GY8VE708Y` | 12 | 11 | 1 |
| *Miss Monochrome* | `G65VJ5256` | 13 | 12 | 5 |
| *GXYZ123* | `GXYZ123S1` / `GXYZ123S3` | 1 / 1 | 0 / 0 | 1 · 1 |
| *Gundam Build Divers* | `GRXJ9E42Y` | 26 | 25 | 20 |
| *Gintama* | `G69PJMKVY` | 52 | 53 | — (lists one extra) |
| *Yakitate!! Japan* | `GR3VM53W6` | 69 | 1 | 1–61, 63–69 |
| *Fairy Musketeers* | `GR5VE345R` | 39 | 35 | 8, 15, 24, 36 |

## 4. The popularity feed lists some shows twice

The live popularity feed can serve the **same show on two tiles** — 7 ids in the BD
snapshot (e.g. *Dorohedoro* at tiles 899 **and** 901), byte-identical entries
with identical positions in two independently captured sessions; 11 ids in the US
snapshot. Databases key on unique ids and preserve every raw position in
`tile_positions`.

**The phenomenon churns heavily over time** (US observations, one evening):
11 duplicated ids in the API crawl, 21 in the browser capture minutes earlier, and
**85 in the live feed** during the verification run — the duplicate-tile count is a
property of the feed's continuous re-ranking, not a stable catalog attribute.

## 5. Two episode-counting models

The CMS series object exposes **both** `episode_count` and `media_count`:
- `media_count` = playable episodes (== the browse feed's `series_metadata.episode_count`
  — verified 45/45 on samples and 100% on live spot checks);
- `episode_count`/`season_count` use a different (episode-entry) model and can disagree
  wildly — e.g. *VINLAND SAGA*: 48 playable episodes / 96 episode-entries.

The census stores the **page-facing numbers** in browse data and both raw values on the
series object; ~50 series in this region differ between the two models. Sum-of-seasons can
also legitimately differ for region-restricted series.

## 6. Locale arrays are unordered sets

`audio_locales` / `subtitle_locales` are returned in a **different order on every API call**
(live-probed: same series, two calls, same members, different order). Compare as sets.
(The census preserves the order as served at extraction time.)

---

## 7. Regional quirk divergence (BD vs US, October 2026)

Running the same verified pipeline against two regions produced a controlled comparison
of how Crunchyroll packages catalogs differently:

| Quirk | 2026.10-BD | 2026.10-US |
|---|---:|---:|
| Per-audio duplicate seasons (shared episode ids) | 329 ids (Fairy Tail) | **0 — absent** |
| Self-inconsistent seasons | 21 | 84 |
| Phantom season references | 68 entries / 7 series | 74 entries / 10 groups |
| Duplicate tiles in the feed snapshot | 7 | 11 |
| Series differing under the two counting models | 723 | 1,603 |

A real-time demonstration also got captured during US verification: *Detective Conan*
(`G6JQVM3ER`) had **587 playable episodes at extraction and 588 two hours later** —
the archived envelope proves extraction-time consistency; the +1 is a live episode
publication, documented as drift in the verification report rather than a defect.

---

### Method notes

- Every finding above was found by a **failing check** that was then investigated rather
  than loosened — see the verification reports in the census release.
- The distinction "upstream quirk vs extraction defect" is enforced by the checks themselves:
  e.g. *no episode references a real season of a different series* is a hard, unconditional
  invariant; the quirks are the *classified* exceptions with exact scope.
- Quirks are **time-stamped**: Crunchyroll can fix any of these server-side; a future census
  may show fewer (or new) ones. `docs/REPRODUCING.md` describes how to re-run the analysis.
