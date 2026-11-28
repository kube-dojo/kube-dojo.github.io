#!/usr/bin/env node
/**
 * Daily Dojo Slice 1 end-to-end browser verification (#3919).
 *
 * Uses Node built-ins + headless Chrome DevTools Protocol (CDP) with zero extra
 * npm dependencies:
 * 1. Verifies built dist/daily/index.html contains zero count.js / goatcounter.
 * 2. Verifies all 10 unit parent anchors exist as real heading IDs in the built
 *    parent module HTML.
 * 3. Serves dist/ on 127.0.0.1 (ephemeral port) and runs a real headless Chrome
 *    walkthrough:
 *    - Parent module banner -> /daily/
 *    - Open /daily/ -> answer Unit 1 (correct) -> reload persistence
 *    - Answer Unit 2 (wrong option explanation + miss scheduling)
 *    - Advance browser date by +1 day -> due review + 5-min choice UI
 *    - Switch between new unit and due review, complete due review -> interval advances
 *    - Verify parent anchor link navigation and Killercoda lab link
 * 4. Records every network request on /daily/ and fails if ANY analytics or
 *    external request occurs.
 */

import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const distDir = path.join(repoRoot, 'dist');
const dailyHtmlPath = path.join(distDir, 'daily', 'index.html');
const parentModulePath = '/k8s/cka/part5-troubleshooting/module-5.1-methodology/';
const parentHtmlPath = path.join(
  distDir,
  'k8s',
  'cka',
  'part5-troubleshooting',
  'module-5.1-methodology',
  'index.html',
);

const EXPECTED_ANCHORS = [
  '11-observe-the-symptom-without-mutating-the-cluster',
  '13-isolate-by-layer-not-by-guess',
  '14-inspect-evidence-in-an-order-that-matches-the-lifecycle',
  '32-describe-before-logs',
  '33-logs-and-previous-logs',
  '43-exit-codes-and-termination-reasons',
  '44-running-does-not-mean-ready',
  'service-path-debugging',
  'storage-triage',
  '16-validate-the-workload-path-not-just-the-object-status',
];

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
};

function findChromeBinary() {
  if (process.env.CHROME_BIN) {
    return process.env.CHROME_BIN;
  }
  for (const candidate of ['google-chrome', 'chromium', 'chromium-browser']) {
    const res = spawnSync('which', [candidate], { encoding: 'utf8' });
    if (res.status === 0 && res.stdout.trim()) return res.stdout.trim();
  }
  throw new Error('No Chrome/Chromium binary found (set CHROME_BIN to override).');
}

function readStaticFile(rootDir, urlPath) {
  const resolvedRoot = path.resolve(rootDir);
  const decoded = decodeURIComponent(urlPath);
  const safeRel = path.normalize(decoded).replace(/^(\.\.(\/|\\|$))+/, '').replace(/^[/\\]+/, '');
  const candidate = path.resolve(resolvedRoot, safeRel);
  if (candidate !== resolvedRoot && !candidate.startsWith(`${resolvedRoot}${path.sep}`)) {
    return null;
  }
  const tryPaths = candidate === resolvedRoot ? [path.join(resolvedRoot, 'index.html')] : [candidate, path.join(candidate, 'index.html')];
  for (const target of tryPaths) {
    try {
      return { filePath: target, body: readFileSync(target) };
    } catch (err) {
      if (err && (err.code === 'ENOENT' || err.code === 'EISDIR' || err.code === 'ENOTDIR')) {
        continue;
      }
      throw err;
    }
  }
  return null;
}

function startStaticServer(rootDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = new URL(req.url ?? '/', 'http://127.0.0.1').pathname;
      const file = readStaticFile(rootDir, urlPath);
      if (!file) {
        res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
      }
      const ext = path.extname(file.filePath).toLowerCase();
      res.writeHead(200, { 'content-type': MIME_TYPES[ext] ?? 'application/octet-stream' });
      res.end(file.body);
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address();
      if (!addr || typeof addr === 'string') {
        reject(new Error('Failed to bind ephemeral port'));
        return;
      }
      resolve({ server, baseUrl: `http://127.0.0.1:${addr.port}` });
    });
  });
}

async function waitForDevToolsPort(proc, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    let stderrBuf = '';
    const timer = setTimeout(() => {
      reject(new Error(`Timed out waiting for Chrome DevTools WS URL. stderr:\n${stderrBuf}`));
    }, timeoutMs);

    const onData = (chunk) => {
      stderrBuf += chunk.toString('utf8');
      const match = /DevTools listening on (ws:\/\/[^\s]+)/.exec(stderrBuf);
      if (match) {
        clearTimeout(timer);
        proc.stderr.off('data', onData);
        resolve(match[1]);
      }
    };
    proc.stderr.on('data', onData);
    proc.once('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome exited early with code ${code}. stderr:\n${stderrBuf}`));
    });
  });
}

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener('open', () => resolve());
      this.ws.addEventListener('error', (err) => reject(err));
    });
    this.ws.addEventListener('message', (event) => {
      const msg = JSON.parse(String(event.data));
      if (msg.id) {
        const entry = this.pending.get(msg.id);
        if (entry) {
          this.pending.delete(msg.id);
          if (msg.error) entry.reject(new Error(`CDP ${entry.method}: ${msg.error.message}`));
          else entry.resolve(msg.result);
        }
      } else if (msg.method) {
        const handlers = this.listeners.get(msg.method) ?? [];
        for (const handler of handlers) handler(msg.params, msg.sessionId);
      }
    });
  }

  on(method, handler) {
    const list = this.listeners.get(method) ?? [];
    list.push(handler);
    this.listeners.set(method, list);
  }

  async send(method, params = {}, sessionId = undefined) {
    await this.ready;
    const id = this.nextId++;
    const payload = sessionId ? { id, method, params, sessionId } : { id, method, params };
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.ws.send(JSON.stringify(payload));
    });
  }

  async close() {
    this.ws.close();
  }
}

async function waitForCondition(cdp, sessionId, expression, label, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await cdp.send(
      'Runtime.evaluate',
      { expression: `Boolean(${expression})`, returnByValue: true },
      sessionId,
    );
    if (res.result?.value === true) return;
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error(`Timed out waiting for condition: ${label}`);
}

async function evalValue(cdp, sessionId, expression) {
  const res = await cdp.send(
    'Runtime.evaluate',
    { expression, returnByValue: true, awaitPromise: true },
    sessionId,
  );
  if (res.exceptionDetails) {
    throw new Error(`Page evaluation failed: ${res.exceptionDetails.text}`);
  }
  return res.result?.value;
}

async function main() {
  const startTime = Date.now();

  // 1. Static built HTML assertions (AC-01 + parent anchor check)
  let dailyHtml;
  try {
    dailyHtml = readFileSync(dailyHtmlPath, 'utf8');
  } catch (err) {
    throw new Error(`Missing built Daily Dojo page: ${dailyHtmlPath} (run npm run build first)`, { cause: err });
  }
  assert(!/count\.js/i.test(dailyHtml), 'Built dist/daily/index.html must NOT reference count.js');
  assert(!/goatcounter/i.test(dailyHtml), 'Built dist/daily/index.html must NOT reference goatcounter');

  let parentHtml;
  try {
    parentHtml = readFileSync(parentHtmlPath, 'utf8');
  } catch (err) {
    throw new Error(`Missing built parent module page: ${parentHtmlPath}`, { cause: err });
  }
  for (const anchor of EXPECTED_ANCHORS) {
    assert(
      parentHtml.includes(`id="${anchor}"`),
      `Built parent module HTML is missing expected anchor id="${anchor}"`,
    );
  }

  const chromeBin = findChromeBinary();
  const userDataDir = mkdtempSync(path.join(os.tmpdir(), 'kubedojo-daily-e2e-'));
  const { server, baseUrl } = await startStaticServer(distDir);

  const chrome = spawn(
    chromeBin,
    [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--remote-debugging-port=0',
      `--user-data-dir=${userDataDir}`,
      'about:blank',
    ],
    { stdio: ['ignore', 'ignore', 'pipe'], detached: true },
  );

  let cdp;
  try {
    const browserWsUrl = await waitForDevToolsPort(chrome);
    cdp = new CdpClient(browserWsUrl);

    const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
    await cdp.send('Page.enable', {}, sessionId);
    await cdp.send('Runtime.enable', {}, sessionId);
    await cdp.send('Network.enable', {}, sessionId);

    const allRequests = [];
    let recordingDaily = false;
    const dailyRequests = [];
    const dailyHttpErrors = [];

    cdp.on('Network.requestWillBeSent', (params) => {
      const url = params.request?.url ?? '';
      allRequests.push(url);
      if (recordingDaily) dailyRequests.push(url);
    });
    cdp.on('Network.responseReceived', (params) => {
      if (!recordingDaily) return;
      const status = params.response?.status ?? 0;
      const url = params.response?.url ?? '';
      if (status >= 400) dailyHttpErrors.push({ url, status });
    });

    // Step 1: Open parent module and click the Daily Dojo banner link -> /daily/
    await cdp.send('Page.navigate', { url: `${baseUrl}${parentModulePath}` }, sessionId);
    await waitForCondition(
      cdp,
      sessionId,
      'document.readyState === "complete" && document.querySelector(\'a[href="/daily/"]\')',
      'parent module banner link',
    );
    const bannerText = await evalValue(
      cdp,
      sessionId,
      'document.querySelector(\'a[href="/daily/"]\').textContent.trim()',
    );
    assert.equal(bannerText, 'Daily Dojo');

    // Start recording /daily/ network traffic right before clicking the banner link
    recordingDaily = true;
    await evalValue(cdp, sessionId, 'document.querySelector(\'a[href="/daily/"]\').click()');
    await waitForCondition(
      cdp,
      sessionId,
      'window.location.pathname === "/daily/" && document.querySelector("[data-daily-root]")?.dataset.dailyMounted === "true"',
      '/daily/ mounted after clicking banner',
    );

    const unitCount = await evalValue(cdp, sessionId, 'document.querySelectorAll("[data-unit-select]").length');
    assert.equal(unitCount, 10, 'Expected 10 pilot units rendered on /daily/');

    // Step 2: Answer Unit 1 correctly -> feedback + localStorage saved
    await evalValue(
      cdp,
      sessionId,
      'document.querySelector(\'[data-check-option][data-correct="true"]\').click()',
    );
    await waitForCondition(
      cdp,
      sessionId,
      'document.querySelector(\'[data-feedback-status="correct"]\') && document.querySelector(\'[data-unit-result="correct"]\')',
      'Unit 1 correct feedback and completion',
    );

    const savedAfterUnit1 = JSON.parse(
      await evalValue(cdp, sessionId, 'window.localStorage.getItem("kubedojo-daily-v1")'),
    );
    assert.equal(savedAfterUnit1.version, 1);
    assert.equal(savedAfterUnit1.streak.current, 1);
    const unit1NextReview = savedAfterUnit1.units['observe-before-mutating'].nextReviewAt;
    assert.match(unit1NextReview, /^\d{4}-\d{2}-\d{2}$/);

    // Step 3: Reload /daily/ and confirm persistence across reload
    await cdp.send('Page.reload', {}, sessionId);
    await waitForCondition(
      cdp,
      sessionId,
      'document.querySelector("[data-daily-root]")?.dataset.dailyMounted === "true"',
      '/daily/ mounted after reload',
    );
    const completedAfterReload = await evalValue(
      cdp,
      sessionId,
      'document.querySelector(\'[data-stat="completed"] .dd-stat-value\').textContent.trim()',
    );
    assert.equal(completedAfterReload, '1 / 10');
    const activeAfterReload = await evalValue(
      cdp,
      sessionId,
      'document.querySelector("[data-unit-id]").getAttribute("data-unit-id")',
    );
    assert.equal(activeAfterReload, 'isolate-by-layer');

    // Step 4: Answer Unit 2 with a distractor (wrong option) -> wrong explanation + missed outcome
    await evalValue(
      cdp,
      sessionId,
      'document.querySelector(\'[data-check-option][data-correct="false"]\').click()',
    );
    await waitForCondition(
      cdp,
      sessionId,
      'document.querySelector(\'[data-feedback-status="incorrect"]\') && document.querySelector(\'[data-unit-result="missed"]\')',
      'Unit 2 incorrect feedback and missed schedule',
    );

    // Step 5: Advance browser date by +1 day (to tomorrow = unit1NextReview) and reload
    const [y, m, d] = unit1NextReview.split('-').map(Number);
    const tomorrowIso = new Date(y, m - 1, d, 10, 0, 0).toISOString();
    const { identifier: clockScriptId } = await cdp.send(
      'Page.addScriptToEvaluateOnNewDocument',
      {
        source: `(() => {
          const fixedMs = Date.parse(${JSON.stringify(tomorrowIso)});
          const RealDate = Date;
          class MockDate extends RealDate {
            constructor(...args) {
              if (args.length === 0) super(fixedMs);
              else super(...args);
            }
            static now() { return fixedMs; }
          }
          window.Date = MockDate;
        })();`,
      },
      sessionId,
    );

    await cdp.send('Page.reload', {}, sessionId);
    await waitForCondition(
      cdp,
      sessionId,
      'document.querySelector("[data-daily-root]")?.dataset.dailyMounted === "true" && document.querySelector(\'[data-plan-mode="choice"]\')',
      'due review + 5-min choice UI on tomorrow',
    );

    const dueCount = await evalValue(
      cdp,
      sessionId,
      'document.querySelector(\'[data-stat="due"] .dd-stat-value\').textContent.trim()',
    );
    assert.equal(dueCount, '2', 'Both Unit 1 and Unit 2 should be due tomorrow');

    // Test review-or-new choice switching
    await evalValue(cdp, sessionId, 'document.querySelector(\'[data-plan-action="new"]\').click()');
    const chosenNewUnit = await evalValue(
      cdp,
      sessionId,
      'document.querySelector("[data-unit-id]").getAttribute("data-unit-id")',
    );
    assert.equal(chosenNewUnit, 'follow-pod-lifecycle');

    await evalValue(cdp, sessionId, 'document.querySelector(\'[data-plan-action="review"]\').click()');
    const chosenReviewUnit = await evalValue(
      cdp,
      sessionId,
      'document.querySelector("[data-unit-id]").getAttribute("data-unit-id")',
    );
    assert.equal(chosenReviewUnit, 'observe-before-mutating');

    // Complete due review of Unit 1 correctly -> interval advances from 0 (1d) to 1 (3d), streak -> 2
    await evalValue(
      cdp,
      sessionId,
      'document.querySelector(\'[data-check-option][data-correct="true"]\').click()',
    );
    await waitForCondition(
      cdp,
      sessionId,
      'document.querySelector(\'[data-unit-result="correct"]\')',
      'due review completed',
    );
    const savedAfterReview = JSON.parse(
      await evalValue(cdp, sessionId, 'window.localStorage.getItem("kubedojo-daily-v1")'),
    );
    assert.equal(savedAfterReview.streak.current, 2);
    assert.equal(savedAfterReview.units['observe-before-mutating'].intervalIndex, 1);

    // Step 6: Verify parent anchor link and Killercoda lab link on the active unit
    const links = await evalValue(
      cdp,
      sessionId,
      `(() => ({
        parentHref: document.querySelector('[data-parent-link]').getAttribute('href'),
        labHref: document.querySelector('[data-lab-link]').getAttribute('href'),
      }))()`,
    );
    assert.equal(
      links.parentHref,
      `${parentModulePath}#11-observe-the-symptom-without-mutating-the-cluster`,
    );
    assert.equal(links.labHref, 'https://killercoda.com/kubedojo/scenario/cka-5.1-methodology');

    // Remove date shim before navigating back to parent anchor
    await cdp.send('Page.removeScriptToEvaluateOnNewDocument', { identifier: clockScriptId }, sessionId);

    // Stop recording /daily/ network traffic BEFORE navigating back to the Starlight parent module
    recordingDaily = false;

    // Follow parent anchor link and verify target heading exists in DOM
    await evalValue(cdp, sessionId, 'document.querySelector("[data-parent-link]").click()');
    await waitForCondition(
      cdp,
      sessionId,
      'window.location.pathname === "/k8s/cka/part5-troubleshooting/module-5.1-methodology/" && Boolean(document.getElementById("11-observe-the-symptom-without-mutating-the-cluster"))',
      'parent module anchor target',
    );

    // Assert ZERO analytics or external requests occurred throughout /daily/
    const analyticsHits = dailyRequests.filter((url) => /count\.js|goatcounter/i.test(url));
    const externalHits = dailyRequests.filter((url) => !url.startsWith(baseUrl) && !url.startsWith('data:'));

    assert.deepEqual(analyticsHits, [], `Analytics requests detected on /daily/: ${JSON.stringify(analyticsHits)}`);
    assert.deepEqual(externalHits, [], `External requests detected on /daily/: ${JSON.stringify(externalHits)}`);
    assert.deepEqual(dailyHttpErrors, [], `HTTP >=400 responses on /daily/: ${JSON.stringify(dailyHttpErrors)}`);

    const summary = {
      ok: true,
      durationMs: Date.now() - startTime,
      unitsRendered: unitCount,
      parentAnchorsVerified: EXPECTED_ANCHORS.length,
      dailyNetworkRequestsTotal: dailyRequests.length,
      dailyAnalyticsRequests: analyticsHits.length,
      dailyExternalRequests: externalHits.length,
      dailyHttpErrors: dailyHttpErrors.length,
      dailyRequestUrls: dailyRequests,
      streakAfterDueReview: savedAfterReview.streak.current,
      unit1IntervalIndexAfterDueReview: savedAfterReview.units['observe-before-mutating'].intervalIndex,
      unit1NextReviewAfterDueReview: savedAfterReview.units['observe-before-mutating'].nextReviewAt,
    };
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } finally {
    if (cdp) {
      await cdp.send('Browser.close').catch(() => {});
      await cdp.close().catch(() => {});
    }
    if (chrome.exitCode === null) {
      const exited = new Promise((resolve) => chrome.once('exit', resolve));
      const termTimer = setTimeout(() => {
        if (chrome.exitCode === null && chrome.pid) {
          try {
            process.kill(-chrome.pid, 'SIGTERM');
          } catch {}
        }
      }, 1500);
      const killTimer = setTimeout(() => {
        if (chrome.exitCode === null && chrome.pid) {
          try {
            process.kill(-chrome.pid, 'SIGKILL');
          } catch {}
        }
      }, 4000);
      await exited;
      clearTimeout(termTimer);
      clearTimeout(killTimer);
    }
    await new Promise((resolve) => server.close(() => resolve()));
    rmSync(userDataDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  }
}

main().catch((err) => {
  process.stderr.write(`${err.stack ?? err.message}\n`);
  process.exit(1);
});
