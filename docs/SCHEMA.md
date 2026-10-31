# Census schema reference

The canonical database is `census/<release>/census-<release>.full.json` (and its `.gz`
twin — byte-identical). This document is the complete schema reference; the JSON itself
embeds a condensed version in `database.field_reference`.

**Losslessness rule:** every object under `shows[].browse`, `shows[].series`,
`shows[].seasons[]` (minus the `episodes` key added by the build), `seasons[].episodes[]`,
`music.*`, and `reference.*` is the **verbatim API response** — original key order,
nothing dropped or re-typed. The only keys the build *adds* are explicitly marked
`(added)` below.

## Top level

```jsonc
{
  "database": { /* provenance & verification meta — below */ },
  "shows":    [ /* every show, popularity-ordered then A–Z — below */ ],
  "music":    { /* artists, music_videos, concerts, coverage */ },
  "reference":{ /* lookup tables & snapshots */ }
}
```

## `database` — the meta block

> **Schema evolution note:** in the `2026.10-BD` census the per-audio duplicate-seasons
> quirk is recorded under the key `fairy_tail_per_audio_duplicate_seasons` (it was
> named after its first observed instance). From the `2026.10-US` census onward the
> generalized key is `per_audio_duplicate_seasons` (with `series` as a list and
> `per_series_counts`), because the phenomenon is not unique to Fairy Tail. Published
> censuses are never rewritten; each release documents its own meta schema in place.

| Key | Contents |
|---|---|
| `name`, `version` | `crunchyroll_full`, `1.0.0` (internal artifact names, kept for provenance) |
| `description` | what the census is, in one paragraph |
| `source`, `region` | API sources; `region.country` (IP-derived, e.g. `"BD"`), `region.locale` (`"en-US"` = metadata language only) |
| `extracted_at_utc` | build timestamp; plus `browser_capture_session_at_utc`, crawl start/finish |
| `id_universe` | the enumeration universe and its sources: `sitemap_series`, `popularity_feed_tiles`/`_unique`, `feed_duplicate_ids` (quirk #4) |
| `counts` | shows (total/available/not-available/ranked), seasons, episodes, unique episode ids, music |
| `ordering` | array-order semantics |
| `url_format` | `https://www.crunchyroll.com/series/{id}/{slug_title}` — id REQUIRED (slug-only URLs render "Page not found" despite HTTP 200) |
| `losslessness` | the rule stated above |
| `field_reference` | condensed schema, embedded for self-description |
| `semantics_caveats` | counting models, unordered locale arrays, live-popularity note |
| `upstream_data_quirks` | full machine-readable quirk catalogue → see `docs/QUIRKS.md` |
| `music_coverage_note` | the honest statement about music enumeration |
| `verification` | build-time checks + pointer to the independent verification report |
| `provenance` | where the raw archives live (the provenance bundles) |

## `shows[]`

Ordered: popularity-ranked shows first (`popularity_rank` 1..N contiguous, array order =
rank order), then non-feed shows alphabetically by title.

| Key | Type | Origin |
|---|---|---|
| `id` | string | Crunchyroll CMS id, e.g. `GG5H5XQX4` **(added)** |
| `canonical_url` | string | `/series/{id}/{slug_title}` **(added)** |
| `popularity_rank` | int \| absent | 1..1098; present iff the show is in the live feed **(added)** |
| `tile_positions` | int[] | every 1-based tile position in the raw feed (length > 1 ⇒ the feed listed it twice — quirk #4) **(added)** |
| `in_sitemap`, `source_flags` | bool / object | enumeration sources of this id **(added)** |
| `availability_status` | string | e.g. `available`, `unavailable` **(added, mirrors series)** |
| `browse` | object \| null | **verbatim** popularity-feed item (only for ranked shows) |
| `series` | object | **verbatim** CMS series object |
| `seasons` | object[] | **verbatim** CMS season objects, each with an `episodes` array added |

### `browse` (verbatim `discover/browse` item)

`title`, `description`, `promo_title`, `promo_description`, `type` (`"series"` — movies are
series containers in this model), `slug_title`, `last_public` (ISO-8601), `new`,
`external_id`, `channel_id`, `linked_resource_key`, `images` (poster_wide 16:9 /
poster_tall 2:3 / promo_image; multi-size variants), `images_localized` (key-art templates
with `{:param}` CDN placeholder), `language_presentation`,
`rating` (`1s`…`5s` per-star counts {displayed, unit, percentage}, `average` 0–5, `total`),
`series_metadata` — `availability_status`, `episode_count` (**= CMS `media_count`**),
`season_count`, `series_launch_year`, `tenant_categories` (genres), `audio_locales`,
`subtitle_locales` (**unordered**), `is_subbed/is_dubbed/is_simulcast`, maturity block
(`extended_maturity_rating`, `maturity_ratings`, `content_descriptors*`), `awards`,
`is_mature`, `mature_blocked`, `availability_notes`.

### `series` (verbatim CMS series object)

Everything in `browse.series_metadata` plus series-level fields: `keywords`, `season_tags`,
`seo_title`, `seo_description`, `content_provider`, `media_count`, `images`+`images_localized`,
`publish_date`, and its own maturity/descriptor blocks.

### `seasons[]` (verbatim CMS season + added episodes array)

`id`, `series_id`, `title`, `slug_title`, `description`, `season_number`,
`season_sequence_number`, `season_display_number`, `is_complete`, `is_subbed`, `is_dubbed`,
`is_simulcast`, `number_of_episodes` (⚠ can disagree with the list — quirk #3),
`audio_locale`/`audio_locales`, `subtitle_locales`, `keywords`, `season_tags`,
`maturity_ratings`/`extended_maturity_rating`/`content_descriptors*`, `is_mature`,
`mature_blocked`, `availability_notes`, `versions` (per-audio variants with
restriction windows), `language_presentation`, `seo_*`, `images`, `identifier`,
`channel_id`, `linked_resource_key` — plus **(added)** `episodes`: the verbatim episode list.

### `episodes[]` (verbatim CMS episode object)

`id`, `title`, `slug_title`, `description`, `promo_title`, `promo_description`,
`sequence_number` (the reliable ordering), `episode_number` (nullable — specials),
`season_id`, `season_title`, `season_number`, `series_id`, `series_title`,
`duration_ms`, `episode_air_date`, `upload_date`, `premium_available_date`,
`free_available_date`, `availability_starts/ends`, `availability_status`, `availability_notes`,
`is_premium_only`, `is_mature`, `is_clip`, `is_subbed`, `is_dubbed`, `mature_blocked`,
`maturity_ratings`, `content_descriptors*`, `audio_locale`, `recent_audio_locale`,
`subtitle_locales`, `closed_captions_available`, `available_offline`, `eligible_region`,
`tenant_categories`, `images` (thumbnails), `versions` (per-audio variants: `guid`,
`media_guid`, `audio_locale`, `is_premium_only`, `original`), `ad_breaks`,
`language_presentation`, `next_episode_id`, `production_episode_id`, `roles`,
`seo_*`, `streams_link` (path only; stream *licenses* are out of scope), `type`.

⚠ Back-reference caveats (quirks #1/#2): shared Fairy Tail episode objects point at the
original-audio season; 68 episodes reference phantom season ids.

## `music`

- `artists[]` — verbatim artist objects: `id` (`MA…`), `name`, `slug`, `description`,
  `genres`, `images`, `isPublic`, `publishDate`, `totalConcertDurationMs`,
  `totalVideoDurationMs`, nested `concerts`/`videos` counts, `type`, timestamps.
- `music_videos[]` — verbatim MV objects (`MV…`): title, description, artist reference,
  images, durations, availability/copyright blocks.
- `concerts[]` — verbatim concert objects (`MC…`).
- `coverage` — discovery statistics + the completeness caveat (no enumeration endpoint
  exists; universe = search coverage × per-artist expansion).

## `reference`

| Key | Contents |
|---|---|
| `seasonal_tags` | 72 simulcast seasons (`fall-2009` … `fall-2026`) with localized titles |
| `categories`, `sub_categories` | discover taxonomy trees |
| `genres_config` | static genre configuration |
| `audio_languages`, `timed_text_languages` | i18n language tables |
| `browse_az_index` | per-letter prefix/offset table of the browse catalog |
| `games_catalog` | the crunchyroll.com/games Gatsby page-data snapshot |
| `news_rss_snapshot_en-US` | RSS snapshot of the news feed |
| `subscription_products` | the public pricing surface seen on pages |

## The compact index (`census-*.index.json`)

One object per show: `id`, `popularity_rank`, `title`, `canonical_url`, `availability`,
`seasons`, `episodes`, `in_popularity_feed`, `in_sitemap` — enough for quick exploration
without loading the full database.

## The popular-page database (`popular-*.json`)

Self-contained: `database` meta (provenance, `tile_positions` semantics, semantics caveats,
verification report incl. the double-capture proof) + `shows[]` = verbatim popularity-feed
items ordered by rank with `(added)` `rank`, `tile_positions`, `url`. 1,104 tiles →
1,097 unique shows for census 2026.10-BD.
