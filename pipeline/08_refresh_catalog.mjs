#!/usr/bin/env node
/**
 * 08_refresh_catalog.mjs
 * -----------------------
 * Refresh crawl of the full discover/browse catalog (popularity-sorted feed),
 * into local/work/full-crawl/catalog/. Same rigor as stage 03:
 * sequential pages, exhaustion proof, per-page archive, manifest.
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORK = process.env.PARI_WORK || join(ROOT, 'local', 'work');
const CENSUS = process.env.PARI_CENSUS || join(ROOT, 'census', '2026.10-BD');
const OUT_DIR = join(WORK, 'full-crawl', 'catalog');
mkdirSync(OUT_DIR, { recursive: true });

const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
const BROWSE = 'https://www.crunchyroll.com/content/v2/discover/browse';
const PAGE_SIZE = 36;
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

let token = null, tokenAt = 0;
async function getToken(force = false) {
  if (!force && token && Date.now() - tokenAt < 45 * 60 * 1000) return;
  for (let a = 1; a <= 8; a++) {
    const { status, body } = curlJson('https://www.crunchyroll.com/auth/v1/token',
      { Authorization: 'Basic Y3Jfd2ViOg==' }, 'POST', 'grant_type=client_id');
    if (status === 200) {
      const j = JSON.parse(body);
      if (j.access_token) { token = j.access_token; tokenAt = Date.now(); console.log('[catalog] token refreshed'); return; }
    }
    console.error(`[catalog] token attempt ${a} failed: HTTP ${status}`);
    await sleep(3000 * a);
  }
  throw new Error('no token');
}

async function apiGet(url) {
  for (let a = 1; a <= 8; a++) {
    await getToken();
    const { status, body } = curlJson(url, {
      Authorization: `Bearer ${token}`,
      Referer: 'https://www.crunchyroll.com/videos/popular',
    });
    if (status === 401 || status === 403) { await getToken(true); await sleep(1500); continue; }
    if (status === 429 || status >= 500) { await sleep(3000 * a); continue; }
    if (status !== 200) throw new Error(`HTTP ${status}: ${body.slice(0, 150)}`);
    return JSON.parse(body);
  }
  throw new Error(`API GET failed: ${url}`);
}

await getToken();
const manifest = { started_at: new Date().toISOString(), page_size: PAGE_SIZE, pages: [], notes: [] };
let start = 0, total = null, collected = 0, seq = 0;

while (true) {
  const j = await apiGet(`${BROWSE}?start=${start}&n=${PAGE_SIZE}&sort_by=popularity&ratings=true&locale=en-US`);
  const data = j.data;
  if (total !== null && j.total !== total) manifest.notes.push(`total changed ${total} -> ${j.total} at start=${start}`);
  total = j.total;
  const meta = { seq: ++seq, start, received: data.length, total, fetched_at: new Date().toISOString() };
  if (data.length > 0) {
    const fname = `page_${String(seq).padStart(3, '0')}_start_${start}.json`;
    writeFileSync(join(OUT_DIR, fname), JSON.stringify(j, null, 2));
    meta.file = fname;
  }
  manifest.pages.push(meta);
  collected += data.length;
  console.log(`[catalog] page #${seq}: start=${start} received=${data.length} (${collected}/${total})`);
  if (data.length === 0) break;
  start += data.length;
  if (start >= total) {
    const over = await apiGet(`${BROWSE}?start=${start}&n=${PAGE_SIZE}&sort_by=popularity&ratings=true&locale=en-US`);
    manifest.pages.push({ seq: ++seq, start, received: over.data.length, total: over.total, overflow: true,
      fetched_at: new Date().toISOString() });
    if (over.data.length === 0) { console.log('[catalog] overflow empty -> complete'); break; }
    total = over.total;
  }
  await sleep(350);
}

manifest.finished_at = new Date().toISOString();
manifest.final_total = total;
manifest.collected = collected;
writeFileSync(join(OUT_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`[catalog] done: ${collected} tiles, total=${total}`);
if (collected !== total) { console.error('MISMATCH'); process.exit(2); }
