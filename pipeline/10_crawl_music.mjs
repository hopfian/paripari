#!/usr/bin/env node
/**
 * 10_crawl_music.mjs
 * ------------------
 * Best-effort complete crawl of the Crunchyroll Music domain.
 *
 * IMPORTANT (research finding): there is NO global enumeration endpoint for music
 * (`music/artists?`, `music/music_videos?`, `music/concerts?` all 404). The reachable
 * discovery surfaces are:
 *   1. discover/search?type=music (title search)  -> discover items (musicVideo/concert)
 *   2. music/landing_feed (curated, 14 items)
 *   3. per-artist listings: music/artists/{id}, /music_videos, /concerts (complete lists)
 * Strategy: search with a broad query set (letters a-z, digits 0-9, common words),
 * union all discovered items, then expand EVERY discovered artist fully.
 * Completeness is search-coverage-based; the DB will document this explicitly.
 *
 * Output: local/work/full-crawl/music/{search,artists,music_videos,concerts}/
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORK = process.env.PARI_WORK || join(ROOT, 'local', 'work');
const M = join(WORK, 'full-crawl', 'music');
for (const d of ['search', 'artists', 'music_videos', 'concerts', 'landing']) {
  mkdirSync(join(M, d), { recursive: true });
}

const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PACE = 350;

function curlJson(url, headers, method = 'GET', data = null) {
  const args = ['-s', '-S', '--compressed', '--max-time', '30', '-X', method, url,
    '-H', `User-Agent: ${UA}`, '-H', 'Accept: application/json'];
  for (const [k, v] of Object.entries(headers || {})) args.push('-H', `${k}: ${v}`);
  if (data) { args.push('-H', 'Content-Type: application/x-www-form-urlencoded'); args.push('--data-raw', data); }
  args.push('-w', '\n__STATUS__:%{http_code}');
  const out = spawnSync('curl', args, { encoding: 'buffer', maxBuffer: 300 * 1024 * 1024 });
  const text = out.stdout.toString('utf8');
  const m = text.match(/\n__STATUS__:(\d+)\s*$/);
  return { status: m ? parseInt(m[1], 10) : 0, body: m ? text.slice(0, m.index) : text };
}

let token = null, tokenAt = 0;
async function getToken(force = false) {
  if (!force && token && Date.now() - tokenAt < 45 * 60 * 1000) return;
  for (let a = 1; a <= 8; a++) {
    const { status, body } = curlJson('https://www.crunchyroll.com/auth/v1/token',
      { Authorization: 'Basic Y3Jfd2ViOg==' }, 'POST', 'grant_type=client_id');
    if (status === 200 && JSON.parse(body).access_token) { token = JSON.parse(body).access_token; tokenAt = Date.now(); return; }
    console.error(`[music] token attempt ${a}: HTTP ${status}`);
    await sleep(4000 * a);
  }
  throw new Error('no token');
}

async function apiGet(url) {
  for (let a = 1; a <= 6; a++) {
    await getToken();
    const { status, body } = curlJson(url, { Authorization: `Bearer ${token}` });
    if (status === 401 || status === 403) { await getToken(true); await sleep(2000); continue; }
    if (status === 429 || status >= 500) { console.warn(`[music] HTTP ${status}, backoff`); await sleep(6000 * a); continue; }
    if (status === 404) return null;
    if (status !== 200) { console.warn(`[music] HTTP ${status} on ${url.slice(-70)}`); await sleep(3000 * a); continue; }
    try { return JSON.parse(body); } catch { console.warn(`[music] parse fail ${url.slice(-70)}`); await sleep(3000 * a); }
  }
  return null;
}

const slug = (s) => s.replace(/[^a-z0-9]+/gi, '-').slice(0, 60).replace(/^-|-$/g, '');
const envOK = (f) => { try { return typeof JSON.parse(readFileSync(f, 'utf8')).status === 'number'; } catch { return false; } };
const writeEnv = (f, env) => writeFileSync(f, JSON.stringify(env, null, 1));

// ---------------- phase 1: search discovery ----------------
const QUERIES = [
  ...'abcdefghijklmnopqrstuvwxyz'.split(''),
  ...'0123456789'.split(''),
  'the', 'a', 'i', 'no', 'live', 'tv', 'short', 'movie', 'special', 'fes', 'song',
  'love', 'star', 'night', 'dream', 'world', 'one', 'my', 'you', 'it', 'ao', 'akb',
];
const discovered = new Map(); // id -> {type, from}
const artistsSeen = new Set();

function harvest(items, from) {
  for (const it of items) {
    if (!it?.id) continue;
    const kind = it.type === 'musicVideo' ? 'MV' : it.type === 'concert' ? 'MC' :
      String(it.id).startsWith('MV') ? 'MV' : String(it.id).startsWith('MC') ? 'MC' : null;
    if (kind) discovered.set(it.id, { type: kind, from });
    const aid = it?.artist?.id;
    if (aid) artistsSeen.add(aid);
  }
}

console.log(`[music] phase 1: search discovery over ${QUERIES.length} queries`);
for (const q of QUERIES) {
  const f = join(M, 'search', `q_${slug(q)}.json`);
  let combined = [];
  if (!envOK(f)) {
    let start = 0;
    for (let page = 0; page < 20; page++) {
      const j = await apiGet(
        `https://www.crunchyroll.com/content/v2/discover/search?q=${encodeURIComponent(q)}&type=music&n=100&start=${start}&locale=en-US`);
      if (!j) break;
      const items = [];
      for (const group of j.data || []) { for (const it of group.items || []) items.push(it); }
      if (items.length === 0) break;
      combined.push(...items);
      start += items.length;
      await sleep(PACE);
    }
    writeEnv(f, { status: 200, fetched_at: new Date().toISOString(),
      body: { query: q, total_collected: combined.length, items: combined } });
  } else {
    try { combined = JSON.parse(readFileSync(f, 'utf8')).body.items; } catch { combined = []; }
  }
  harvest(combined, `search:${q}`);
  console.log(`[music]   q='${q}' -> ${combined.length} items (universe: ${discovered.size})`);
}

// landing feed
const fLand = join(M, 'landing', 'landing_feed.json');
if (!envOK(fLand)) {
  const j = await apiGet('https://www.crunchyroll.com/content/v2/music/landing_feed?locale=en-US&n=14&start=0');
  writeEnv(fLand, { status: j ? 200 : 0, fetched_at: new Date().toISOString(), body: j });
}
try {
  const land = JSON.parse(readFileSync(fLand, 'utf8')).body;
  const items = land?.data || [];
  for (const it of items) {
    for (const key of ['musicVideos', 'concerts', 'artists']) {
      for (const x of it[key] || []) {
        if (x?.id) {
          if (key === 'artists') artistsSeen.add(x.id);
          else discovered.set(x.id, { type: x.id.startsWith('MV') ? 'MV' : 'MC', from: 'landing' });
        }
      }
    }
  }
} catch {}

console.log(`[music] discovered items: ${discovered.size} (MV/MC); artists seen: ${artistsSeen.size}`);

// artists from discovered items need full artist objects — also collect artist ids from item details later
// ---------------- phase 2: per-artist expansion ----------------
const artistQueue = [...artistsSeen];
const processedArtists = new Set();
const musicVideos = new Map();
const concerts = new Map();

let ai = 0;
while (artistQueue.length) {
  const aid = artistQueue.shift();
  if (!aid || processedArtists.has(aid)) continue;
  processedArtists.add(aid);
  ai++;

  const fA = join(M, 'artists', `${aid}.json`);
  if (!envOK(fA)) {
    const j = await apiGet(`https://www.crunchyroll.com/content/v2/music/artists/${aid}?locale=en-US`);
    if (j) {
      writeEnv(fA, { status: 200, fetched_at: new Date().toISOString(), body: j });
      const a = Array.isArray(j.data) ? j.data[0] : null;
      if (a?.id) artistsSeen.add(a.id);
    } else {
      writeEnv(fA, { status: 404, fetched_at: new Date().toISOString(), body: null });
    }
    await sleep(PACE);
  }

  const fMV = join(M, 'music_videos', `artist_${aid}.json`);
  if (!envOK(fMV)) {
    const j = await apiGet(`https://www.crunchyroll.com/content/v2/music/artists/${aid}/music_videos?locale=en-US`);
    if (j) {
      writeEnv(fMV, { status: 200, fetched_at: new Date().toISOString(), body: j });
      for (const mv of j.data || []) {
        if (mv?.id) musicVideos.set(mv.id, mv);
        if (mv?.artist?.id) artistQueue.push(mv.artist.id);
      }
    } else writeEnv(fMV, { status: 404, fetched_at: new Date().toISOString(), body: null });
    await sleep(PACE);
  } else {
    try { for (const mv of JSON.parse(readFileSync(fMV, 'utf8')).body?.data || []) { if (mv?.id) musicVideos.set(mv.id, mv); if (mv?.artist?.id) artistQueue.push(mv.artist.id); } } catch {}
  }

  const fMC = join(M, 'concerts', `artist_${aid}.json`);
  if (!envOK(fMC)) {
    const j = await apiGet(`https://www.crunchyroll.com/content/v2/music/artists/${aid}/concerts?locale=en-US`);
    if (j) {
      writeEnv(fMC, { status: 200, fetched_at: new Date().toISOString(), body: j });
      for (const c of j.data || []) {
        if (c?.id) concerts.set(c.id, c);
        if (c?.artist?.id) artistQueue.push(c.artist.id);
      }
    } else writeEnv(fMC, { status: 404, fetched_at: new Date().toISOString(), body: null });
    await sleep(PACE);
  } else {
    try { for (const c of JSON.parse(readFileSync(fMC, 'utf8')).body?.data || []) { if (c?.id) concerts.set(c.id, c); if (c?.artist?.id) artistQueue.push(c.artist.id); } } catch {}
  }

  if (ai % 25 === 0) console.log(`[music] artists processed: ${processedArtists.size} (queue ${artistQueue.length}) | MVs ${musicVideos.size} | concerts ${concerts.size}`);
}

console.log(`[music] phase 2 done: artists=${processedArtists.size} MVs=${musicVideos.size} concerts=${concerts.size}`);

// ---------------- phase 3: orphan item details ----------------
// items discovered by search but not covered by any artist listing need detail fetches
const coveredMV = new Set(musicVideos.keys());
const coveredMC = new Set(concerts.keys());
const orphans = [...discovered.values()].length;
let fetchedOrphans = 0;
for (const [id, info] of discovered) {
  if (id.startsWith('MV') && !coveredMV.has(id)) {
    const f = join(M, 'music_videos', `${id}.json`);
    if (!envOK(f)) {
      const j = await apiGet(`https://www.crunchyroll.com/content/v2/music/music_videos/${id}?locale=en-US`);
      if (j) { writeEnv(f, { status: 200, fetched_at: new Date().toISOString(), body: j }); musicVideos.set(id, Array.isArray(j.data) ? j.data[0] : j); if (j?.data?.[0]?.artist?.id) artistQueue.push(j.data[0].artist.id); }
      else writeEnv(f, { status: 404, fetched_at: new Date().toISOString(), body: null });
      await sleep(PACE); fetchedOrphans++;
    }
  }
  if (id.startsWith('MC') && !coveredMC.has(id)) {
    const f = join(M, 'concerts', `${id}.json`);
    if (!envOK(f)) {
      const j = await apiGet(`https://www.crunchyroll.com/content/v2/music/concerts/${id}?locale=en-US`);
      if (j) { writeEnv(f, { status: 200, fetched_at: new Date().toISOString(), body: j }); concerts.set(id, Array.isArray(j.data) ? j.data[0] : j); if (j?.data?.[0]?.artist?.id) artistQueue.push(j.data[0].artist.id); }
      else writeEnv(f, { status: 404, fetched_at: new Date().toISOString(), body: null });
      await sleep(PACE); fetchedOrphans++;
    }
  }
}

writeFileSync(join(M, 'summary.json'), JSON.stringify({
  finished_at: new Date().toISOString(),
  queries_used: QUERIES.length,
  discovered_items: discovered.size,
  artists_processed: processedArtists.size,
  music_videos: musicVideos.size,
  concerts: concerts.size,
  orphan_details_fetched: fetchedOrphans,
  note: 'No global enumeration endpoint exists (404-probed); universe = search coverage + full per-artist expansion.',
}, null, 2));

console.log(`[music] DONE: MVs=${musicVideos.size} concerts=${concerts.size} artists=${processedArtists.size} orphan fetches=${fetchedOrphans}`);
