# docs/WEB_RESEARCH_REPORT.md
See RESEARCH.md §Web for the condensed version. (Verbatim subagent report, 2026-10-31)

# Crunchyroll API Research Report

*Compiled October 31, 2026. Bracketed numbers `[n]` refer to the source list in §9. Crunchyroll has no official public API documentation; everything below comes from reverse-engineered community projects (yt-dlp, crunchyroll-rs, crunchyroll-go, Crunchyroll-Plus docs), Crunchyroll's own web surfaces, and official press releases.*

## 1. Content API v2 — endpoints, params, pagination

**Hosts.** All modern endpoints are served from `https://www.crunchyroll.com` and `https://beta-api.crunchyroll.com`; the community treats these as the same backend [1][2]. A legacy app API still exists at `https://api.crunchyroll.com` [5][6]. Static JSON via `static.crunchyroll.com` [5].

**Known `content/v2/cms` paths** (all GET, Bearer token required) [1][3][5][6][7][8]:

| Path | Purpose |
|---|---|
| `GET /content/v2/cms/series/{series_id}` | Series metadata |
| `GET /content/v2/cms/series/{series_id}/seasons` | Seasons of a series |
| `GET /content/v2/cms/seasons?series_id={id}` | Same, query-param form (signed CMS mirror) |
| `GET /content/v2/cms/seasons/{season_id}` | One season |
| `GET /content/v2/cms/seasons/{season_id}/episodes` | Episodes of a season |
| `GET /content/v2/cms/episodes?season_id={id}` | Same, query-param form (signed CMS) |
| `GET /content/v2/cms/episodes/{episode_id}` | One episode |
| `GET /content/v2/cms/objects/{ids}` | Polymorphic lookup by content id |
| `GET /content/v2/cms/movie_listings/{id}/movies` | Movies in a movie listing |
| `GET /content/v2/cms/series/{id}/categories` | Categories of a series |

**Known `content/v2/discover` paths** [1][3][5][8][9][10][11]: `browse` (params `n`, `start`, `categories`, `type`, `q`, `seasonal_tag`, `is_dubbed`, `is_subbed`, `sort_by`; `newly_added` confirmed working with `type=episode&n=100`), `search` (`type=music,series,episode,top_results,movie_listing`), `seasonal_tags`, `categories`, `categories/{category}/sub_categories`, `up_next/{id}`, `previous_episode/{id}`, `{account}/similar_to/{id}`, `{account}/home_feed`, `{account}/watchlist`.

**Music (`content/v2/music`)** [5][8][12]: `artists/{id}`, `artists/{id}/concerts`, `artists/{id}/music_videos`, `concerts/{id}`, `music_videos/{ids}`, landing feed + featured per series in the app service list [1].

**CMS signing ("signed" mirror).** `GET /index/v2` returns `{cms: {bucket, policy, signature, key_pair_id}}`; yt-dlp rewrote heavy calls to `beta-api.crunchyroll.com/cms/v2{bucket}/...?Policy=...&Signature=...&Key-Pair-Id=...` explicitly "to avoid getting soft banned" [5]. Episode objects carry `streams_link`; stream responses contain `adaptive_hls`, `adaptive_dash`, `hls`, `dash` with `hardsub_locale` variants plus `meta.subtitles` [5][7].

**Pagination behavior.** `{data: [...], total, meta}`; crunchyroll-rs notes "Crunchyroll doesn't always deliver the correct number of total elements on pagination endpoints" and uses `next_page` when present [8].

## 2. Season & episode object schemas

**Episode object fields** (crunchyroll-rs 0.19.1 + yt-dlp) [8][5]: `id`, `channel_id`, `identifier`, `slug`, `title`, `slug_title`, `description`, `next_episode_id`, `season_id`, `season_title`, `series_id`, `series_title`, `roles`, `production_episode_id`, `episode`, `episode_number`, `sequence_number`, `season_number`, `audio_locale`, `recent_audio_locale`, `subtitle_locales`, `content_descriptors`, `duration_ms`, `episode_air_date`, `upload_date`, `free_available_date`, `premium_available_date`, `availability_starts`, `availability_ends`, `images`, `tenant_categories`, `is_dubbed`, `is_subbed`, `is_premium_only`, `is_clip`, `is_mature`, `maturity_ratings`, `mature_blocked`, `available_offline`, `availability_notes`, `availability_status`, `closed_captions_available`, `eligible_region`, `versions` (per-audio variants: `guid`, `media_guid`, `audio_locale`, `is_premium_only`, `original`, `roles`), `ad_breaks`, `language_presentation`, `streams_link`, `promo_title`, `seo_title`, `external_id`, `type`. Intro timestamps statically at `static.crunchyroll.com/datalab-intro-v2/{episode_id}.json`; skip events at `static.crunchyroll.com/skip-events/production/{episode_id}.json` [5][14].

**Season object fields** [8]: `id`, `series_id`, `channel_id`, `identifier`, `title`, `slug_title`, `description`, `season_number`, `season_sequence_number`, `number_of_episodes`, `is_complete`, `keywords`, `season_tags`, `content_descriptors`, `is_subbed`, `is_dubbed`, `is_simulcast`, `audio_locale`, `audio_locales`, `subtitle_locales`, `maturity_ratings`, `is_mature`, `mature_blocked`, `availability_notes`, `versions` (with `restriction_windows`), `language_presentation`, `images`, `season_display_number`, `extended_maturity_rating`, `seo_title`, `seo_description`.

## 3. Authentication (anonymous / client_id grant)

- `POST /auth/v1/token`, `Authorization: Basic base64(client_id + ":")`, body `grant_type=client_id` [1][5][6]. Response includes `country` (catalog region by IP) [6][15].
- Web client: `cr_web` → `Basic Y3Jfd2ViOg==` [14]. Other known public client ids: `noaihdevm_6iyg0a8l0q` (iOS), `lkesi7snsy9oojmi2r9h` + secret (Android TV) [15].
- `ETP_RT` cookie refresh: `grant_type=etp_rt_cookie` [6].
- `GET /index/v2` → CMS policy/signature/bucket [5][13].

## 4. Sitemaps

`robots.txt` declares sitemap index `https://www.crunchyroll.com/sitemap.xml` (+ `/sitemap`) and allows `/cr-lab-akihabara-service/v1/products/search` (store JSON) [18]. The index has **178 child sitemaps** (live-verified, 2026-10-31): static_routes, extras, videos (category listing pages), simulcasts, news per-locale, **series/{A–Z,#} (27 shards)** and **episode/{A–Z,#} (27 letters, 107 shard-pages)** [19][20].

## 5. Catalog size claims (official, chronological)

2021: "1,000+ titles / 30,000 episodes" [22][23]; 2022: "40,000+ episodes" [24][25]; Feb 2024: "18,000 hours, 46,000 episodes and films, 3,300 music videos and concert specials, 13M subs" [26][27]; Jun 2025: "over 50,000 episodes and 25,000 hours" [28]; Oct 2025 boilerplate: "more than 25,000 hours and 50,000 episodes" [29]. Free ad-supported tier removed Dec 31, 2025 [31].

## 6. Other surfaces

- **Music**: `content/v2/music/...` endpoints (§1); premium-only; ~3,300 MVs/concerts (2024 press); web URLs `/watch/musicvideo/{id}`, `/watch/concert/{id}` [26][33][5].
- **Manga**: original service shut down Dec 11, 2023 [34]; relaunched Oct 9, 2025 (US/Canada only, app+web reader) **built/operated by Link-U Group** — no crunchyroll.com JSON API [35][36][37][38].
- **Games**: `crunchyroll.com/games` marketing/catalog page; Game Vault ~50 titles (Oct 2025), target 100 by summer 2026; no public JSON API known [39][40][41].
- **News**: Storyblok-backed; RSS at `cr-news-api-service.prd.crunchyrollsvc.com/v1/{locale}/rss` [42][43].
- **Simulcast calendar**: legacy HTML page redirects; community rebuilds from `browse?type=episode&sort_by=newly_added` [9][44].
- **Store**: `store.crunchyroll.com` (Right Stuf) [34]; JSON product search requires session (live-probed → 401).
- **Anime Awards**: annual, Telescope platform, results via news articles; no API [32][46].

## 7. Rate limiting & Cloudflare

Cloudflare fronting + "Just a moment…" challenge to non-browser clients [19][21]. yt-dlp **removed** its Crunchyroll extractors Jan 2025 (hostile to non-browser clients) [48]; before that it used the signed CMS route for bulk metadata "to avoid getting soft banned" [5]. Community guidance: cache one anonymous token ~50 min; serialize auth; page sizes 20–100; back off on 403/429; consider browser impersonation for auth [49][50]. beta-api vs www Cloudflare posture has flip-flopped 2024→2025 [51][52]. Playback-level soft bans (kat-3002/429) exist separately [15][53].

## 8. Locale/regional notes

`locale` = metadata language only; **region comes from IP at token time** (`country` in token response); catalogs differ per region; VPN needed to see other catalogs (ToS risk) [6][54][55]. Episodes carry `eligible_region`; seasons carry per-version `restriction_windows` [8]. Music videos absent in ~15 mostly-Asian markets [33]. Japan has no Crunchyroll streaming service [56].

## 9. Source list

1. https://github.com/Crunchyroll-Plus/crunchyroll-docs
2. https://github.com/Crunchyroll-Plus/crunchyroll-docs/blob/release/Services/EtpContent/README.md
3. https://github.com/Crunchyroll-Plus/crunchyroll-docs/tree/release/Services
4. https://github.com/HarshitKumar9030/crunchyroll-api (npm `crunchy-api`)
5. yt-dlp crunchyroll extractor (pre-removal snapshot) — https://raw.githubusercontent.com/yt-dlp/yt-dlp/c25cac2f8e5fbac2737a426d7778fd2f0efc5381/yt_dlp/extractor/crunchyroll.py
6. https://github.com/crunchy-labs/crunchyroll-go/blob/master/crunchyroll.go
7. https://github.com/yt-dlp/yt-dlp/issues/6234
8. crunchyroll-rs 0.19.1 — https://docs.rs/crunchyroll-rs/latest/src/crunchyroll_rs/ (media/anime/episode.rs, season.rs, common.rs, categories.rs, media/music/artist.rs, release_calendar.rs)
9. https://github.com/Spirrwell/crunchyroll-release-calendar
10. Crunchyroll-Plus getWatchlist/getHomeFeed docs
11. Crunchyroll-Plus getSeasonList (seasonal_tags)
12. https://github.com/anidl/multi-downloader-nx/issues/801
13. hyugogirubato API-Crunchyroll-Beta wiki (index/v2)
14. https://github.com/ToonTamilIndia/Crunchy-Bot-CLI/blob/main/crunchyroll.py
15. https://git.drmlab.io/Reddington/Unshackle-Services/src/branch/main/CR/config.yaml
16. https://github.com/jhassan8/crunchyroll-tizen/commit/f69cb8cfa4f26d0ca3127ce68b87414b09b2ceed
17. https://github.com/vitalygashkov/crextractor
18. https://www.crunchyroll.com/robots.txt
19. https://beavercheck.com/sites/crunchyroll.com/infrastructure
20. https://www.crunchyroll.com/sitemap.xml (+ sample shards)
21. https://agentability.org/ai-index/site/crunchyroll.com/
22. https://www.animationxpress.com/animation/crunchyroll-surpasses-the-4m-subscriber-milestone-and-announced-the-production-of-sci-fi-thriller-dantai/
23. https://www.hollywoodreporter.com/business/digital/sony-crunchyroll-acquisition-1234994997/
24. https://www.sonypictures.com/corp/press_releases/2022/0301
25. https://www.googlecloudpresscorner.com/2022-04-25-Crunchyroll-Adds-Google-as-Strategic-Technology-Partner-to-Help-in-Global-Growth-of-Anime
26. https://www.prnewswire.com/news-releases/exploring-anime-is-easier-than-ever-as-crunchyroll-launches-on-lg-smart-tvs-internationally-beginning-today-302067913.html
27. https://www.animenewsnetwork.com/press-release/2024-02-05/crunchyroll-to-be-added-to-samsung-smart-tvs-globally-providing-anime-access-to-millions/.207263
28. https://www.licensingmagazine.com/2025/06/13/exclusive-annecy-2025-anime-as-a-cultural-force-crunchyrolls-perspective-from-annecy/
29. https://www.animenewsnetwork.com/press-release/2025-10-29/crunchyroll-launches-24-7-crunchyroll-channel-on-samsung-smart-tvs/.230441
30. Third-party repetition examples (earthweb.com, realbusiness.co.uk, americantv.com)
31. https://www.cbr.com/crunchyroll-free-anime-episodes-youtube-2026/
32. https://deadline.com/2026/05/crunchyroll-anime-awards-73m-votes-1236915518/
33. https://help.crunchyroll.com/article/Music-Videos-and-Concerts
34. https://www.animenewsnetwork.com/news/2023-11-11/crunchyroll-ends-digital-manga-app-on-mobile-web-on-december-11/.204339
35. https://www.crunchyroll.com/news/announcements/2025/9/25/crunchyroll-manga-sets-october-9-launch-one-piece-jujutsu-kaisen-more
36. https://en.wikipedia.org/wiki/Crunchyroll_Manga
37. https://news.animenomics.com/p/crunchyroll-relaunches-digital-manga-service
38. https://www.animenewsnetwork.com/news/2025-09-25/crunchyroll-manga-app-launches-in-u.s-canada-on-october-9-for-ios-android/.229269
39. https://www.crunchyroll.com/games/ ; https://games.help.crunchyroll.com/hc/en-us
40. https://www.crunchyroll.com/news/guides/2025/10/22/crunchyroll-game-vault-games-list
41. https://www.crunchyroll.com/news/announcements/2023/11/7/crunchyroll-game-vault-free-games
42. https://github.com/AniTrend/anitrend-v2/issues/377
43. https://feeder.co/discover/site/crunchyroll.com
44. https://docs.rs/crunchyroll-rs/latest/src/crunchyroll_rs/release_calendar.rs.html
45. https://help.crunchyroll.com/article/is-there-a-release-calendar-available
46. https://www.casestudies.com/company/telescope/case-study/crunchyroll-launches-a-9-language-anime-awards-vote-with-telescope
47. https://prtimes.jp/main/html/rd/p/000000014.000114805.html
48. https://github.com/yt-dlp/commit/ff44ed53061e065804da6275d182d7928cc03a5e
49. crunchyroll-jellyfin commits (403/429 handling): 8d4ad5d, 166a32f
50. crunchyroll-jellyfin CDP/FlareSolverr overhaul: 17121a0
51. https://github.com/hama3254/Crunchyroll-Downloader-v3.0/issues/961
52. https://github.com/crunchy-labs/crunchyroll-rs/issues/44
53. https://forum.dvdfab.cn/d/472460-crunchyroll-stuck-on-analyzing-indefinitely-error-107--http-429
54. https://www.security.org/vpn/change-crunchyroll-location/
55. https://fixyourvpn.com/advice/crunchyroll-vpn-not-working
56. https://bearvpn.com/blog/crunchyroll-not-working-in-japan/
