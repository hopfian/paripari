#!/usr/bin/env node
/**
 * 01_cdp_capture.mjs
 * -------------------
 * Captures ALL network traffic (requests + response bodies) from
 * https://www.crunchyroll.com/videos/popular using headless Chrome via CDP,
 * auto-scrolling to the bottom until the infinite-scroll feed is exhausted.
 *
 * Output (under local/work/browse-capture/ by default, or $PARI_WORK/$RAW_DIR):
 *   - meta.json          : run metadata (final URL, UA, scroll stats, counts)
 *   - requests.json      : every request: url, method, headers, POST body, status, mime
 *   - bodies/<seq>.json  : saved text/JSON response bodies
 *   - bodies_index.json  : maps saved body file -> request metadata
 *   - final_page.png     : screenshot at end (verification the page rendered)
 *
 * No npm dependencies: uses Node's built-in fetch + WebSocket.
 */

import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORK = process.env.PARI_WORK || join(ROOT, 'local', 'work');
const CENSUS = process.env.PARI_CENSUS || join(ROOT, 'census', '2026.10-BD');
// RAW_DIR is relative to WORK; default captures the Most Popular page
const RAW = process.env.RAW_DIR
  ? join(WORK, process.env.RAW_DIR)
  : join(WORK, 'browse-capture');
const BODIES = join(RAW, 'bodies');
mkdirSync(BODIES, { recursive: true });

const PORT = 9333;
const TARGET_URL = process.argv[2] || 'https://www.crunchyroll.com/videos/popular';
const SCROLL_DELAY_MS = 1500;
const MAX_SCROLLS = parseInt(process.env.MAX_SCROLLS || '200', 10);
const IDLE_EXIT_MS = 20000; // stop after this long with zero new network responses
const STARTUP_WAIT_MS = 6000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- Chrome version -> realistic UA ----------
let chromeVersion = 'unknown';
try {
  chromeVersion = execSync('google-chrome --version').toString().trim();
} catch {}
const majorMatch = chromeVersion.match(/(\d+)\./);
const major = majorMatch ? majorMatch[1] : '131';
const UA = `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;

// ---------- launch chrome ----------
const PROFILE = join(WORK, '.chrome-profile');
if (existsSync(PROFILE)) rmSync(PROFILE, { recursive: true, force: true });

const chromeArgs = [
  '--headless=new',
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`,
  '--remote-allow-origins=*',
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-blink-features=AutomationControlled',
  '--disable-features=Translate,MediaRouter,OptimizationHints',
  '--window-size=1440,2200',
  '--hide-scrollbars',
  '--lang=en-US',
  'about:blank',
];
console.log(`[capture] launching: google-chrome ${chromeArgs.join(' ')}`);
const chrome = spawn('google-chrome', chromeArgs, { stdio: ['ignore', 'ignore', 'pipe'] });
let chromeStderr = '';
chrome.stderr.on('data', (d) => { chromeStderr += d.toString(); });
chrome.on('exit', (code) => { if (code) console.error(`[capture] chrome exited code=${code}`); });

async function waitForEndpoint() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`, { signal: AbortSignal.timeout(1000) });
      if (r.ok) return await r.json();
    } catch {}
    await sleep(500);
  }
  throw new Error('DevTools endpoint never came up. stderr:\n' + chromeStderr.slice(-2000));
}

const versionInfo = await waitForEndpoint();
console.log(`[capture] chrome is up: ${versionInfo.Browser}`);

// ---------- create the tab ----------
const newTarget = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(TARGET_URL)}`, { method: 'PUT' })
  .then((r) => r.json());
console.log(`[capture] target created: ${newTarget.id}`);

// ---------- CDP over WebSocket ----------
const ws = new WebSocket(newTarget.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.addEventListener('open', res, { once: true });
  ws.addEventListener('error', (e) => rej(new Error('ws error: ' + e.message || 'unknown')), { once: true });
});

let nextId = 1;
const pending = new Map();
const eventHandlers = new Map(); // method -> Set(fn)

ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id !== undefined) {
    const p = pending.get(msg.id);
    if (p) {
      pending.delete(msg.id);
      if (msg.error) p.rej(new Error(`${p.method}: ${JSON.stringify(msg.error)}`));
      else p.res(msg.result);
    }
  } else if (msg.method) {
    const hs = eventHandlers.get(msg.method);
    if (hs) for (const h of hs) h(msg.params, msg.sessionId);
  }
});

function send(method, params = {}, timeoutMs = 60000) {
  const id = nextId++;
  return new Promise((res, rej) => {
    const timer = setTimeout(() => { pending.delete(id); rej(new Error(`CDP timeout: ${method}`)); }, timeoutMs);
    pending.set(id, { res: (v) => { clearTimeout(timer); res(v); }, rej: (e) => { clearTimeout(timer); rej(e); }, method });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
function on(method, fn) {
  if (!eventHandlers.has(method)) eventHandlers.set(method, new Set());
  eventHandlers.get(method).add(fn);
}
function once(method, timeoutMs = 60000) {
  return new Promise((res, rej) => {
    const timer = setTimeout(() => rej(new Error(`timeout waiting for ${method}`)), timeoutMs);
    const fn = (params) => { clearTimeout(timer); eventHandlers.get(method)?.delete(fn); res(params); };
    on(method, fn);
  });
}
async function evalJS(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true });
  if (r.exceptionDetails) throw new Error('page eval failed: ' + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails));
  return r.result?.value;
}

// ---------- state we collect ----------
/** @type {Map<string, any>} */
const requests = new Map(); // requestId -> record
let bodySeq = 0;
const bodiesIndex = [];
let mainFrameId = null;
let finalURL = TARGET_URL;
let lastNetworkActivity = Date.now();

function recordRequest(id, patch) {
  if (!requests.has(id)) requests.set(id, { requestId: id });
  Object.assign(requests.get(id), patch);
}

// ---------- enable domains ----------
await send('Network.enable', { maxTotalBufferSize: 400 * 1024 * 1024, maxResourceBufferSize: 200 * 1024 * 1024 });
await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setUserAgentOverride', { userAgent: UA, acceptLanguage: 'en-US,en;q=0.9', platform: 'Linux x86_64' });
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
await send('Network.setCacheDisabled', { cacheDisabled: true });

// ---------- event listeners ----------
on('Network.requestWillBeSent', (p) => {
  lastNetworkActivity = Date.now();
  recordRequest(p.requestId, {
    url: p.request.url,
    method: p.request.method,
    resourceType: p.type,
    requestHeaders: p.request.headers,
    postData: p.request.postData ?? null,
    hasMorePostData: !!p.request.hasMorePostData,
    initiatedAt: p.timestamp,
    initiator: p.initiator?.type ?? null,
  });
  if (p.request.hasMorePostData && !p.request.postData) {
    send('Network.getRequestPostData', { requestId: p.requestId })
      .then((r) => recordRequest(p.requestId, { postData: r.requestPostData }))
      .catch(() => {});
  }
  if (p.redirectResponse) {
    recordRequest(p.requestId, { redirectedFrom: p.redirectResponse.url, redirectStatus: p.redirectResponse.status });
  }
});

on('Network.responseReceived', (p) => {
  lastNetworkActivity = Date.now();
  recordRequest(p.requestId, {
    status: p.response.status,
    statusText: p.response.statusText,
    mimeType: p.response.mimeType,
    responseHeaders: p.response.headers,
    fromDiskCache: p.response.fromDiskCache,
    protocol: p.response.protocol,
  });
});

on('Network.loadingFailed', (p) => {
  recordRequest(p.requestId, { failed: true, errorText: p.errorText, canceled: p.canceled });
});

on('Network.loadingFinished', (p) => {
  lastNetworkActivity = Date.now();
  const rec = requests.get(p.requestId);
  if (!rec || rec.bodySaved || rec.failed) return;
  rec.encodedDataLength = p.encodedDataLength;
  // fetch body promptly while it is still buffered
  send('Network.getResponseBody', { requestId: p.requestId }, 30000)
    .then((r) => {
      if (!requests.has(p.requestId)) return;
      const rec2 = requests.get(p.requestId);
      if (rec2.bodySaved) return;
      const mime = rec2.mimeType || '';
      if (/^(image\/|font\/|audio\/|video\/)/i.test(mime) || rec2.resourceType === 'Media') {
        rec2.bodySaved = 'skipped-binary';
        return;
      }
      const isText = /json|text|javascript|xml|x-www-form-urlencoded/i.test(mime) || mime === '';
      if (!isText) { rec2.bodySaved = 'skipped-mime:' + mime; return; }
      const body = r.base64Encoded ? Buffer.from(r.body, 'base64').toString('utf8') : r.body;
      if (body.length > 80 * 1024 * 1024) { rec2.bodySaved = 'skipped-too-big'; return; }
      const seq = ++bodySeq;
      const file = join('bodies', `${String(seq).padStart(4, '0')}.json`);
      const host = (() => { try { return new URL(rec2.url).host; } catch { return 'unknown'; } })();
      writeFileSync(join(BODIES, `${String(seq).padStart(4, '0')}.json`), body);
      rec2.bodySaved = 'saved';
      rec2.bodyFile = file;
      rec2.bodyLength = body.length;
      bodiesIndex.push({
        seq,
        file,
        url: rec2.url,
        host,
        method: rec2.method,
        status: rec2.status,
        mimeType: rec2.mimeType,
        resourceType: rec2.resourceType,
        length: body.length,
        sha256: createHash('sha256').update(body).digest('hex').slice(0, 16),
      });
    })
    .catch((e) => { if (requests.has(p.requestId)) requests.get(p.requestId).bodyError = String(e.message || e); });
});

on('Page.frameNavigated', (p) => {
  if (!p.frame.parentId) { mainFrameId = p.frame.id; finalURL = p.frame.url; }
});

// ---------- navigate ----------
console.log(`[capture] navigating to ${TARGET_URL}`);
const navResult = await send('Page.navigate', { url: TARGET_URL }, 90000);
if (navResult.errorText) throw new Error('navigation failed: ' + navResult.errorText);
try { await once('Page.loadEventFired', 90000); } catch { console.error('[capture] load event timeout, continuing'); }
console.log(`[capture] page loaded; final URL: ${finalURL}`);
await sleep(STARTUP_WAIT_MS);

// ---------- auto-scroll loop ----------
async function dismissConsent() {
  return evalJS(`(() => {
    const tries = [
      '#onetrust-accept-btn-handler',
      'button[id*="accept"]',
      'button[title*="Accept"]',
    ];
    for (const sel of tries) {
      const b = document.querySelector(sel);
      if (b && b.offsetParent !== null) { b.click(); return 'clicked:' + sel; }
    }
    return null;
  })()`).catch(() => null);
}

let scrollStats = { scrolls: 0, lastHeight: 0, sameHeightStreak: 0 };
let lastBodyCount = bodiesIndex.length;
let done = false;

for (let s = 1; s <= MAX_SCROLLS && !done; s++) {
  const clicked = await dismissConsent();
  const state = await evalJS(`JSON.stringify({
    h: document.documentElement.scrollHeight,
    y: window.scrollY,
    tiles: document.querySelectorAll('a[href*="/series/"]').length
         + document.querySelectorAll('a[href*="/watch/"]').length,
    ready: document.readyState
  })`).catch(() => '{}');
  const st = JSON.parse(state || '{}');

  await evalJS('window.scrollTo(0, document.documentElement.scrollHeight)').catch(() => {});

  scrollStats.scrolls = s;
  if (st.h === scrollStats.lastHeight) scrollStats.sameHeightStreak++;
  else scrollStats.sameHeightStreak = 0;
  scrollStats.lastHeight = st.h;
  lastBodyCount = bodiesIndex.length;

  console.log(`[capture] scroll #${String(s).padStart(3)}: height=${st.h} y=${st.y} tiles=${st.tiles} bodies=${bodiesIndex.length}${clicked ? ' [' + clicked + ']' : ''}`);

  await sleep(SCROLL_DELAY_MS);

  const newBodies = bodiesIndex.length - lastBodyCount;
  if (newBodies > 0) lastNetworkActivity = Date.now();

  const idleFor = Date.now() - lastNetworkActivity;
  if (idleFor > IDLE_EXIT_MS && s > 4) { console.log(`[capture] idle for ${idleFor}ms -> feed exhausted`); done = true; }
  if (scrollStats.sameHeightStreak >= 8 && idleFor > IDLE_EXIT_MS / 2) { console.log('[capture] page height stable + idle -> done'); done = true; }
}
if (!done) console.log('[capture] stopped: MAX_SCROLLS reached');

// small settle window for final in-flight requests
await sleep(5000);

// ---------- screenshot for verification ----------
try {
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, fromSurface: true }, 60000);
  writeFileSync(join(RAW, 'final_page.png'), Buffer.from(shot.data, 'base64'));
  console.log('[capture] screenshot saved');
} catch (e) { console.error('[capture] screenshot failed:', e.message); }

// final page state
const finalState = await evalJS(`JSON.stringify({ url: location.href, title: document.title, height: document.documentElement.scrollHeight, tiles: document.querySelectorAll('a[href*="/series/"]').length + document.querySelectorAll('a[href*="/watch/"]').length })`).catch(() => '{}');
console.log('[capture] final state:', finalState);

// ---------- dump everything ----------
const meta = {
  capturedAt: new Date().toISOString(),
  targetUrl: TARGET_URL,
  finalUrl: finalURL,
  userAgent: UA,
  chromeVersion,
  scroll: scrollStats,
  finalPageState: JSON.parse(finalState || '{}'),
  totalRequests: requests.size,
  savedBodies: bodiesIndex.length,
};
writeFileSync(join(RAW, 'meta.json'), JSON.stringify(meta, null, 2));
writeFileSync(join(RAW, 'bodies_index.json'), JSON.stringify(bodiesIndex, null, 2));
const reqList = [...requests.values()].map((r) => {
  const { requestId, url, method, resourceType, requestHeaders, postData, status, mimeType, bodyFile, bodyLength, failed, errorText, redirectedFrom, redirectStatus, initiator, responseHeaders, bodySaved, bodyError, protocol, encodedDataLength } = r;
  return { requestId, url, method, resourceType, initiator, status, mimeType, protocol, encodedDataLength, requestHeaders, postData, responseHeaders, bodyFile, bodyLength, bodySaved, bodyError, failed, errorText, redirectedFrom, redirectStatus };
});
writeFileSync(join(RAW, 'requests.json'), JSON.stringify(reqList, null, 2));

console.log(`[capture] done: ${requests.size} requests captured, ${bodiesIndex.length} bodies saved`);

// ---------- cleanup ----------
ws.close();
chrome.kill();
await sleep(1000);
process.exit(0);
