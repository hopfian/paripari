#!/usr/bin/env node
/**
 * 03_fetch_api_full.mjs
 * ----------------------
 * Deterministic full crawl of the Crunchyroll "Popular" feed using the exact API
 * the website itself uses (discovered & verified via headless-Chrome network capture):
 *
 *   GET https://www.crunchyroll.com/content/v2/discover/browse
 *         ?start=N&n=36&sort_by=popularity&ratings=true&locale=en-US
 *   Authorization: Bearer <anonymous token from POST /auth/v1/token, grant_type=client_id>
 *
 * NOTE: HTTP is done via `curl` (child process) because Cloudflare challenges
 * Node's native fetch TLS fingerprint, while curl is accepted.
 *
 * - Pages are fetched SEQUENTIALLY to preserve the popularity ordering (rank order)
 *   and to avoid pagination drift.
 * - Every raw page is archived to local/work/browse-crawl/api_pages/ immediately (crash-safe).
 * - Crawls until the API returns an empty page (proves the feed is exhausted),
 *   cross-checked against the `total` reported by the API.
 */

import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORK = process.env.PARI_WORK || join(ROOT, 'local', 'work');
const CENSUS = process.env.PARI_CENSUS || join(ROOT, 'census', '2026.10-BD');
const BROWSE_CRAWL = join(WORK, 'browse-crawl');
const PAGES_DIR = join(BROWSE_CRAWL, 'api_pages');
mkdirSync(PAGES_DIR, { recursive: true });

const UA =
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
const TOKEN_URL = 'https://www.crunchyroll.com/auth/v1/token';
const BROWSE_URL = 'https://www.crunchyroll.com/content/v2/discover/browse';
const PAGE_SIZE = 36; // the site requests pages of 36
const INTERPAGE_DELAY_MS = 350; // gentle on the API; still completes 31 pages in ~15s

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- curl-backed HTTP ----------
/**
 * Runs curl and returns { status, body }.
 * @param {string[]} args curl arguments (url, -H headers, -d data, ...)
 */
function curl(args, timeoutMs = 30000) {
  const out = spawnSync(
    'curl',
    ['-s', '-S', '--compressed', '--max-time', String(Math.ceil(timeoutMs / 1000)), ...args],
    { encoding: 'buffer', maxBuffer: 200 * 1024 * 1024 }
  );
  if (out.error) throw out.error;
  if (out.stderr.length) process.stderr.write('[curl] ' + out.stderr.toString());
  return { status: null, raw: out.stdout };
}

/** curl a URL with headers; returns { status, body } using a sentinel status line. */
function curlJson(url, headers, { method = 'GET', data = null } = {}) {
  const args = ['-X', method, url, '-H', `User-Agent: ${UA}`, '-H', 'Accept: application/json'];
  for (const [k, v] of Object.entries(headers || {})) args.push('-H', `${k}: ${v}`);
  if (data) {
    args.push('-H', 'Content-Type: application/x-www-form-urlencoded');
    args.push('--data-raw', data);
  }
  // status sentinel: last line of stdout is __STATUS__:<code>
  args.push('-w', '\n__STATUS__:%{http_code}');
  const res = curl(args);
  const text = res.raw.toString('utf8');
  const m = text.match(/\n__STATUS__:(\d+)\s*$/);
  const status = m ? parseInt(m[1], 10) : 0;
  const body = m ? text.slice(0, m.index) : text;
  return { status, body };
}

// ---------- anonymous token ----------
let token = null;
let tokenFetches = 0;
async function getToken() {
  for (let attempt = 1; attempt <= 8; attempt++) {
    tokenFetches++;
    try {
      const { status, body } = curlJson(TOKEN_URL, { Authorization: 'Basic Y3Jfd2ViOg==' }, {
        method: 'POST',
        data: 'grant_type=client_id',
      });
      if (status !== 200) throw new Error(`HTTP ${status}: ${body.slice(0, 160)}`);
      const j = JSON.parse(body);
      if (!j.access_token) throw new Error('no access_token in response');
      console.log(`[fetch] got anonymous token (attempt ${attempt})`);
      token = j.access_token;
      return;
    } catch (e) {
      console.error(`[fetch] token attempt ${attempt} failed: ${e.message}`);
      await sleep(2000 * attempt);
    }
  }
  throw new Error('could not obtain anonymous token');
}

// ---------- API GET with retries + token refresh on 401 ----------
async function apiGet(start, n) {
  const url = `${BROWSE_URL}?start=${start}&n=${n}&sort_by=popularity&ratings=true&locale=en-US`;
  for (let attempt = 1; attempt <= 8; attempt++) {
    const { status, body } = curlJson(
      url,
      {
        Authorization: `Bearer ${token}`,
        'Accept-Language': 'en-US,en;q=0.9',
        Referer: 'https://www.crunchyroll.com/videos/popular',
      },
      { method: 'GET' }
    );
    if (status === 401 || status === 403) {
      console.log(`[fetch] HTTP ${status} at start=${start} -> refreshing token`);
      await getToken();
      await sleep(1000);
      continue;
    }
    if (status === 429 || status >= 500) {
      const wait = 3000 * attempt;
      console.warn(`[fetch] HTTP ${status} at start=${start} -> retrying in ${wait}ms (attempt ${attempt})`);
      await sleep(wait);
      continue;
    }
    if (status !== 200) throw new Error(`HTTP ${status}: ${body.slice(0, 200)}`);
    const j = JSON.parse(body);
    if (!Array.isArray(j.data)) throw new Error(`unexpected shape: keys=${Object.keys(j)}`);
    return { json: j, status, url };
  }
  throw new Error(`API GET failed permanently for start=${start}`);
}

// ---------- crawl ----------
await getToken();

const manifest = {
  crawl_started_at: new Date().toISOString(),
  endpoint: BROWSE_URL,
  page_size: PAGE_SIZE,
  pages: [],
  notes: [],
};

let start = 0;
let total = null;
let collected = 0;
let seq = 0;

while (true) {
  const { json, status, url } = await apiGet(start, PAGE_SIZE);
  const data = json.data;

  if (total !== null && json.total !== total) {
    manifest.notes.push(`API total changed during crawl: ${total} -> ${json.total} at start=${start}`);
    console.warn(`[fetch] total changed: ${total} -> ${json.total}`);
  }
  total = json.total;

  const pageMeta = {
    seq: ++seq,
    start,
    requested: PAGE_SIZE,
    received: data.length,
    status,
    total,
    fetched_at: new Date().toISOString(),
    url,
    first_id: data[0]?.id ?? null,
    last_id: data[data.length - 1]?.id ?? null,
  };

  if (data.length > 0) {
    const fname = `page_${String(pageMeta.seq).padStart(3, '0')}_start_${start}.json`;
    writeFileSync(join(PAGES_DIR, fname), JSON.stringify(json, null, 2));
    pageMeta.file = `browse-crawl/api_pages/${fname}`;
  }

  manifest.pages.push(pageMeta);
  collected += data.length;
  console.log(
    `[fetch] page #${seq}: start=${start} received=${data.length} (running total ${collected}/${total})`
  );

  if (data.length === 0) {
    console.log(`[fetch] empty page at start=${start} -> feed exhausted`);
    break;
  }
  start += data.length;

  if (start >= total) {
    // confirm exhaustion with one extra (overflow) page — recorded in the manifest
    const { json: over, status: overStatus } = await apiGet(start, PAGE_SIZE);
    manifest.pages.push({
      seq: ++seq,
      start,
      requested: PAGE_SIZE,
      received: over.data.length,
      status: overStatus,
      total: over.total,
      fetched_at: new Date().toISOString(),
      url: `${BROWSE_URL}?start=${start}&n=${PAGE_SIZE}&sort_by=popularity&ratings=true&locale=en-US`,
      first_id: over.data[0]?.id ?? null,
      last_id: over.data[over.data.length - 1]?.id ?? null,
      overflow: true,
    });
    if (Array.isArray(over.data) && over.data.length === 0) {
      console.log(`[fetch] overflow page at start=${start} is empty -> confirmed complete`);
      break;
    } else {
      manifest.notes.push(`overflow page at start=${start} returned ${over.data?.length} items; continuing`);
      console.warn(`[fetch] overflow page returned ${over.data?.length} items -> continuing`);
      total = over.total;
    }
  }
  await sleep(INTERPAGE_DELAY_MS);
}

manifest.crawl_finished_at = new Date().toISOString();
manifest.token_fetches = tokenFetches;
manifest.final_total = total;
manifest.collected = collected;

// sanity summary
const starts = manifest.pages.map((p) => p.start);
let contiguous = true;
let prevEnd = 0;
for (const p of manifest.pages) {
  if (p.start !== prevEnd) contiguous = false;
  prevEnd = p.start + p.received;
}
manifest.pagination_contiguous = contiguous;

writeFileSync(join(BROWSE_CRAWL, 'api_crawl_manifest.json'), JSON.stringify(manifest, null, 2));

console.log('\n[fetch] CRAWL SUMMARY');
console.log(`  pages fetched:     ${manifest.pages.length}`);
console.log(`  items collected:   ${collected}`);
console.log(`  API total:         ${total}`);
console.log(`  contiguous:        ${contiguous}`);
console.log(`  token fetches:     ${tokenFetches}`);
if (collected !== total) {
  console.error('  !! MISMATCH: collected != total');
  process.exit(2);
}
if (!contiguous) {
  console.error('  !! PAGINATION NOT CONTIGUOUS');
  process.exit(3);
}
console.log('[fetch] OK');
