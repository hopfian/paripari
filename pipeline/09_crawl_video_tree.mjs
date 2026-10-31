#!/usr/bin/env node
/**
 * 09_crawl_video_tree.mjs
 * ------------------------
 * The main full-catalog crawl: for EVERY known series id (union of sitemap series ids,
 * refreshed browse catalog, and the original popular-page crawl), fetch:
 *   1. GET /content/v2/cms/series/{id}                     -> series/{id}.json
 *   2. GET /content/v2/cms/series/{id}/seasons             -> seasons/{id}.json
 *   3. GET /content/v2/cms/seasons/{sid}/episodes  (per season, when it has episodes)
 *                                                          -> episodes/{sid}.json
 * Envelope: {status, fetched_at, body} — resumable (skips existing files), paced,
 * exponential backoff, token auto-refresh. Writes a ledger with progress + errors.
 *
 * Output: local/work/full-crawl/{series,seasons,episodes}/
 * Run: node pipeline/09_crawl_video_tree.mjs
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORK = process.env.PARI_WORK || join(ROOT, 'local', 'work');
const CENSUS = process.env.PARI_CENSUS || join(ROOT, 'census', '2026.10-BD');
const CR = join(WORK, 'full-crawl');
const D_SERIES = join(CR, 'series');
const D_SEASONS = join(CR, 'seasons');
const D_EPISODES = join(CR, 'episodes');
for (const d of [D_SERIES, D_SEASONS, D_EPISODES]) mkdirSync(d, { recursive: true });

const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
const BASE = 'https://www.crunchyroll.com/content/v2/cms';
const LOCALE = 'en-US';
const PACE_MS = 350;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

// ---------------- token ----------------
let token = null, tokenAt = 0, tokenCountry = null;
async function getToken(force = false) {
  if (!force && token && Date.now() - tokenAt < 45 * 60 * 1000) return;
  for (let a = 1; a <= 8; a++) {
    const { status, body } = curlJson('https://www.crunchyroll.com/auth/v1/token',
      { Authorization: 'Basic Y3Jfd2ViOg==' }, 'POST', 'grant_type=client_id');
    if (status === 200 && JSON.parse(body).access_token) {
      const j = JSON.parse(body);
      token = j.access_token; tokenAt = Date.now();
      if (j.country) tokenCountry = j.country;
      return;
    }
    console.error(`[tree] token attempt ${a} failed: HTTP ${status}`);
    await sleep(4000 * a);
  }
  throw new Error('no token');
}
const HDRS = () => ({ Authorization: `Bearer ${token}`, Referer: 'https://www.crunchyroll.com/videos/popular' });

// ---------------- robust GET returning envelope ----------------
async function fetchEnvelope(url) {
  for (let a = 1; a <= 7; a++) {
    await getToken();
    const { status, body } = curlJson(url, HDRS());
    if (status === 401 || status === 403) { await getToken(true); await sleep(2000); continue; }
    if (status === 429 || status >= 500) {
      console.warn(`[tree] HTTP ${status} on ${url.slice(-60)} — backoff ${8000 * a}ms (attempt ${a})`);
      await sleep(8000 * a);
      continue;
    }
    if (status === 404) return { status, fetched_at: new Date().toISOString(), body: null };
    if (status !== 200) {
      console.warn(`[tree] unexpected HTTP ${status} on ${url.slice(-80)} (attempt ${a})`);
      await sleep(4000 * a);
      continue;
    }
    try {
      return { status, fetched_at: new Date().toISOString(), body: JSON.parse(body) };
    } catch (e) {
      console.warn(`[tree] JSON parse fail on ${url.slice(-80)} (attempt ${a}): ${e.message}`);
      await sleep(3000 * a);
    }
  }
  return { status: 0, fetched_at: new Date().toISOString(), body: null, error: 'exhausted retries' };
}

// ---------------- id universe ----------------
const universe = new Set();
// sitemap series ids
for (const l of readFileSync(join(WORK, 'sitemaps', 'series_ids.txt'), 'utf8').split('\n')) {
  if (l.trim()) universe.add(l.trim());
}
// refreshed catalog pages
const catDir = join(CR, 'catalog');
let catalogTiles = 0;
for (const f of spawnSync('ls', [catDir], { encoding: 'utf8' }).stdout.split('\n')) {
  if (!f.endsWith('.json') || !f.startsWith('page_')) continue;
  const j = JSON.parse(readFileSync(join(catDir, f), 'utf8'));
  for (const item of j.data) { universe.add(item.id); catalogTiles++; }
}
// original popular crawl pages (supersets/extra entrants safety)
const oldDir = join(WORK, 'browse-crawl', 'api_pages');
try {
  for (const f of spawnSync('ls', [oldDir], { encoding: 'utf8' }).stdout.split('\n')) {
    if (!f.endsWith('.json')) continue;
    const j = JSON.parse(readFileSync(join(oldDir, f), 'utf8'));
    for (const item of j.data) universe.add(item.id);
  }
} catch {}

let ids = [...universe].sort();

// sharding: node 09_crawl_video_tree.mjs <shardIndex> <shardCount>
const SHARD = parseInt(process.argv[2] || '0', 10);
const SHARDS = parseInt(process.argv[3] || '1', 10);
ids = ids.filter((_, i) => i % SHARDS === SHARD);
console.log(`[tree] series id universe: ${universe.size} -> shard ${SHARD}/${SHARDS}: ${ids.length} (sitemap + ${catalogTiles} catalog tiles)`);

// ---------------- ledger ----------------
const LEDGER = join(CR, `ledger_shard${SHARD}.json`);
let ledger = { started_at: new Date().toISOString(), shard: SHARD, series: { done: 0, failed: [] },
  seasons: { done: 0, skipped: 0 }, episodes: { done: 0, skipped: 0 }, requests: 0 };
try { ledger = JSON.parse(readFileSync(LEDGER, 'utf8')); ledger.requests = ledger.requests || 0; } catch {}
function saveLedger() { ledger.updated_at = new Date().toISOString(); writeFileSync(LEDGER, JSON.stringify(ledger, null, 2)); }

const envOK = (f) => { try { const j = JSON.parse(readFileSync(f, 'utf8')); return typeof j.status === 'number'; } catch { return false; } };
const writeEnv = (f, env) => writeFileSync(f, JSON.stringify(env, null, 1));

// ---------------- main loop ----------------
const t0 = Date.now();
let nSeries = 0;
for (const sid of ids) {
  const fSeries = join(D_SERIES, `${sid}.json`);
  if (!envOK(fSeries)) {
    const env = await fetchEnvelope(`${BASE}/series/${sid}?locale=${LOCALE}`);
    writeEnv(fSeries, env);
    ledger.requests++;
    if (env.status === 200) ledger.series.done++; else ledger.series.failed.push({ id: sid, status: env.status });
    await sleep(PACE_MS);
  }

  const fSeasons = join(D_SEASONS, `${sid}.json`);
  let seasons = [];
  if (!envOK(fSeasons)) {
    const env = await fetchEnvelope(`${BASE}/series/${sid}/seasons?locale=${LOCALE}`);
    writeEnv(fSeasons, env);
    ledger.requests++;
    if (env.status === 200) { seasons = env.body?.data || []; ledger.seasons.done++; }
    else if (env.status !== 200) ledger.seasons.skipped++;
    await sleep(PACE_MS);
  } else {
    try { const j = JSON.parse(readFileSync(fSeasons, 'utf8')); if (j.status === 200) seasons = j.body.data || []; } catch {}
  }

  for (const season of seasons) {
    const sId = season.id;
    if (!sId) continue;
    const nEp = season.number_of_episodes ?? 0;
    const fEp = join(D_EPISODES, `${sId}.json`);
    if (nEp <= 0) { ledger.episodes.skipped++; continue; } // empty seasons verified in build phase
    if (!envOK(fEp)) {
      const env = await fetchEnvelope(`${BASE}/seasons/${sId}/episodes?locale=${LOCALE}`);
      writeEnv(fEp, env);
      ledger.requests++;
      if (env.status === 200) { ledger.episodes.done++; } else { ledger.series.failed.push({ id: `episodes:${sId}`, status: env.status }); }
      await sleep(PACE_MS);
    }
  }

  nSeries++;
  if (nSeries % 25 === 0) {
    const elapsed = (Date.now() - t0) / 1000;
    const eta = elapsed / nSeries * (ids.length - nSeries);
    console.log(`[tree] ${nSeries}/${ids.length} series | seasons done=${ledger.seasons.done || '?'} eps done=${ledger.episodes.done} | ${Math.round(elapsed)}s elapsed, ~${Math.round(eta / 60)}m left`);
    saveLedger();
  }
}

saveLedger();
console.log(`[tree] COMPLETE: series=${ledger.series.done} seasons-lists, episodes files=${ledger.episodes.done}, requests=${ledger.requests}, failures=${ledger.series.failed.length}`);
if (tokenCountry) console.log(`[tree] token country: ${tokenCountry}`);
if (ledger.series.failed.length) console.log('[tree] failures:', JSON.stringify(ledger.series.failed.slice(0, 10)));
