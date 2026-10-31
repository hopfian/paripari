#!/usr/bin/env node
/**
 * 06_surface_prober.mjs
 * ---------------------
 * Loads a list of URLs in one headless-Chrome session (CDP) and records, for each
 * page, every XHR/fetch API request (URL, method, POST body, status) plus the JSON
 * response bodies of API-looking calls. No scrolling — this is a surface prober.
 *
 * Usage:
 *   node pipeline/06_surface_prober.mjs <urls-file.txt> [outDirName]
 * URLs file: one URL per line. Output: local/work/research-probes/<outDirName>/<NN>.json per page.
 */

import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, rmSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORK = process.env.PARI_WORK || join(ROOT, 'local', 'work');
const urlsFile = process.argv[2];
const outName = process.argv[3] || 'surface_probes';
if (!urlsFile) {
  console.error('usage: node 06_surface_prober.mjs <urls-file.txt> [outDirName]');
  process.exit(1);
}
const URLS = readFileSync(urlsFile, 'utf8').split('\n').map((l) => l.trim()).filter(Boolean);
const OUT = join(WORK, 'research-probes', outName);
mkdirSync(OUT, { recursive: true });

const PORT = 9334;
const PER_PAGE_WAIT_MS = 7000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let chromeVersion = 'unknown';
try { chromeVersion = execSync('google-chrome --version').toString().trim(); } catch {}
const major = chromeVersion.match(/(\d+)\./)?.[1] || '131';
const UA = `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;

const PROFILE = join(WORK, '.chrome-profile-probe');
if (existsSync(PROFILE)) rmSync(PROFILE, { recursive: true, force: true });
const chrome = spawn('google-chrome', [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`,
  '--remote-allow-origins=*', '--no-first-run', '--no-default-browser-check',
  '--disable-blink-features=AutomationControlled', '--window-size=1440,2200',
  '--hide-scrollbars', '--lang=en-US', 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] });

async function waitForEndpoint() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`, { signal: AbortSignal.timeout(1000) });
      if (r.ok) return;
    } catch {}
    await sleep(500);
  }
  throw new Error('devtools endpoint never came up');
}
await waitForEndpoint();
const target = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' }).then((r) => r.json());
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.addEventListener('open', res, { once: true });
  ws.addEventListener('error', () => rej(new Error('ws error')), { once: true });
});

let nextId = 1;
const pending = new Map();
const handlers = new Map();
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id !== undefined) {
    const p = pending.get(msg.id);
    if (p) { pending.delete(msg.id); msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result); }
  } else if (msg.method) {
    (handlers.get(msg.method) || new Set()).forEach((fn) => fn(msg.params));
  }
});
function send(method, params = {}, timeoutMs = 60000) {
  const id = nextId++;
  return new Promise((res, rej) => {
    const t = setTimeout(() => { pending.delete(id); rej(new Error('timeout ' + method)); }, timeoutMs);
    pending.set(id, { res: (v) => { clearTimeout(t); res(v); }, rej: (e) => { clearTimeout(t); rej(e); } });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
function on(method, fn) { if (!handlers.has(method)) handlers.set(method, new Set()); handlers.get(method).add(fn); }

await send('Network.enable', { maxTotalBufferSize: 200 * 1024 * 1024, maxResourceBufferSize: 100 * 1024 * 1024 });
await send('Page.enable');
await send('Emulation.setUserAgentOverride', { userAgent: UA, acceptLanguage: 'en-US,en;q=0.9', platform: 'Linux x86_64' });

const isApi = (url, mime, type) =>
  (/crunchyroll\.com\/(content|auth|index|subs|cr-lab|catalog|music|games|datalist|cms)/.test(url) ||
   /static\.crunchyroll\.com\/config\//.test(url) ||
   (type === 'Fetch' && (mime || '').includes('json')));

const results = [];
for (let i = 0; i < URLS.length; i++) {
  const url = URLS[i];
  console.log(`[probe ${i + 1}/${URLS.length}] ${url}`);
  const apiCalls = new Map(); // requestId -> record
  const bodies = [];
  const record = (id, patch) => {
    if (!apiCalls.has(id)) apiCalls.set(id, {});
    Object.assign(apiCalls.get(id), patch);
  };
  const onReq = (p) => record(p.requestId, { url: p.request.url, method: p.request.method, resourceType: p.type, postData: p.request.postData ?? null });
  const onResp = (p) => record(p.requestId, { status: p.response.status, mimeType: p.response.mimeType });
  const onFin = (p) => {
    const rec = apiCalls.get(p.requestId);
    if (!rec) return;
    send('Network.getResponseBody', { requestId: p.requestId }, 20000)
      .then((r) => {
        const rec2 = apiCalls.get(p.requestId);
        if (!rec2) return;
        const body = r.base64Encoded ? Buffer.from(r.body, 'base64').toString('utf8') : r.body;
        if (isApi(rec2.url, rec2.mimeType, rec2.resourceType) && body.length < 3_000_000) {
          rec2.body = body;
          bodies.push({ url: rec2.url, method: rec2.method, status: rec2.status, mimeType: rec2.mimeType, length: body.length, body });
        }
      }).catch(() => {});
  };
  on('Network.requestWillBeSent', onReq);
  on('Network.responseReceived', onResp);
  on('Network.loadingFinished', onFin);

  let finalUrl = url, title = '';
  try {
    await send('Page.navigate', { url }, 60000);
    await sleep(PER_PAGE_WAIT_MS);
    const st = await send('Runtime.evaluate', { expression: 'JSON.stringify({url: location.href, title: document.title})', returnByValue: true });
    ({ url: finalUrl, title } = JSON.parse(st.result.value || '{}'));
  } catch (e) { console.error('  nav error:', e.message); }
  await sleep(1500); // let trailing bodies be captured

  for (const m of ['Network.requestWillBeSent', 'Network.responseReceived', 'Network.loadingFinished']) {
    handlers.get(m)?.clear();
  }
  const calls = [...apiCalls.values()].filter((c) => isApi(c.url, c.mimeType, c.resourceType))
    .map(({ url: u, method, status, mimeType, resourceType, postData }) => ({ url: u, method, status, mimeType, resourceType, postData }));
  results.push({ requestedUrl: url, finalUrl, title, apiCalls: calls, capturedBodies: bodies.map(({ body, ...rest }) => rest) });
  const out = { requestedUrl: url, finalUrl, title, apiCalls: calls, bodies };
  writeFileSync(join(OUT, `${String(i + 1).padStart(2, '0')}_${url.replace(/[^a-z0-9]+/gi, '_').slice(-80)}.json`), JSON.stringify(out, null, 2));
  console.log(`  -> final: ${finalUrl}\n  -> ${calls.length} API calls, ${bodies.length} bodies captured`);
}

writeFileSync(join(OUT, '_summary.json'), JSON.stringify(results.map(({ apiCalls, capturedBodies, ...r }) => ({ ...r, nApiCalls: apiCalls.length, nBodies: capturedBodies.length })), null, 2));
console.log(`\n[probe] done: ${URLS.length} pages probed -> ${OUT}`);
ws.close();
chrome.kill();
await sleep(800);
process.exit(0);
