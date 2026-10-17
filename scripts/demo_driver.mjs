import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const { chromium } = require(require.resolve('playwright-core', { paths: [path.join(ROOT, 'frontend')] }));
const APP_URL = process.env.DEMO_APP_URL || 'http://localhost:5173';
const API_URL = process.env.ASSET_INTELLIGENCE_API || 'http://127.0.0.1:8000';
const PAUSE_SECONDS = Math.max(0, Number(process.env.DEMO_PAUSE || 4));
const TYPE_DELAY_MS = Math.max(10, Number(process.env.DEMO_TYPE_DELAY_MS || 38));
const DRY_RUN = process.argv.includes('--dry-run');
const SCREENSHOT_DIR = path.join(ROOT, 'docs', 'screenshots', 'demo');
const VIDEO_DIR = path.join(ROOT, 'dist');
const VIDEO_FINAL = path.join(VIDEO_DIR, 'demo_raw.webm');
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

const questions = {
  areaDowntime: 'Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.',
  conflictStatus: 'Tyler Hughes says WELL-0175 is running fine and not shut in. Is that correct? Show its status card.',
  areaStatus: 'Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.',
  privateRecall: 'For the three wells we discussed yesterday, what have repairs cost this year?',
  generalization: 'Which wells in Southwest Block 23 had the highest repair costs in 2026?',
};

const steps = {
  architecture: { title: 'Architecture overview', targetSeconds: 25 },
  downtime: { title: 'Downtime chart, citations, calculation, and table', targetSeconds: 50 },
  status: { title: 'Status card, conflict, and data freshness', targetSeconds: 35 },
  correction: { title: 'Audited correction and shared area result', targetSeconds: 35 },
  memory: { title: 'Private memory isolation and recall', targetSeconds: 20 },
  generalization: { title: 'Unchipped repair-cost question', targetSeconds: 15 },
};

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function pressEnter(prompt) {
  if (DRY_RUN) return;
  await new Promise((resolve) => rl.question(`${prompt} Press Enter to continue. `, resolve));
}

async function finishStep(step, startedAt) {
  const elapsed = Date.now() - startedAt;
  if (DRY_RUN) {
    const target = step.targetSeconds * 1000;
    await sleep(Math.max(PAUSE_SECONDS * 1000, target - elapsed));
    return;
  }
  await sleep(PAUSE_SECONDS * 1000);
  await pressEnter(`Next: ${step.title}`);
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    process.platform === 'win32' ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : undefined,
    process.platform === 'win32' ? 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe' : undefined,
    process.platform === 'win32' ? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' : undefined,
    process.platform === 'darwin' ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : undefined,
    process.platform === 'darwin' ? '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge' : undefined,
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      require('node:fs').accessSync(candidate);
      return candidate;
    } catch {
      // Try the next system browser path.
    }
  }
  throw new Error('No Chrome or Chromium executable found; set CHROME_PATH.');
}

async function verifyDemoBackend() {
  const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error('Demo backend health check failed.');
  const health = await response.json();
  if (health.status !== 'ok' || health.demo_mode !== true || health.demo_db_safe !== true) {
    throw new Error('Backend did not confirm the isolated demo database and cache.');
  }
  const requestedProvider = process.env.DEMO_PROVIDER?.toLowerCase();
  if (requestedProvider && health.llm_provider !== requestedProvider) {
    throw new Error('Backend provider does not match DEMO_PROVIDER.');
  }
  console.log(`Demo provider: ${health.llm_provider}.`);
}

async function addVisibleCursor(page) {
  await page.evaluate(() => {
    if (document.getElementById('__demo-cursor')) return;
    const style = document.createElement('style');
    style.textContent = `
      html, body, body * { cursor: none !important; }
      #__demo-cursor { position: fixed; z-index: 2147483647; left: 0; top: 0; width: 26px; height: 26px;
        border: 2px solid #ff5d61; border-radius: 50%; background: #ff5d6133; pointer-events: none;
        transform: translate(-50%, -50%); box-shadow: 0 0 0 2px #07111f99, 0 0 14px #ff5d61aa; }
      #__demo-cursor::after { content: ''; position: absolute; width: 5px; height: 5px; left: 50%; top: 50%;
        border-radius: 50%; background: #fff; transform: translate(-50%, -50%); }
      #__demo-cursor.down { width: 38px; height: 38px; background: #ff5d6166; transition: width .12s, height .12s; }
    `;
    document.head.appendChild(style);
    const cursor = document.createElement('div');
    cursor.id = '__demo-cursor';
    document.body.appendChild(cursor);
    document.addEventListener('mousemove', (event) => {
      cursor.style.left = `${event.clientX}px`;
      cursor.style.top = `${event.clientY}px`;
      cursor.style.opacity = '1';
    });
    document.addEventListener('mousedown', () => {
      cursor.classList.add('down');
      window.setTimeout(() => cursor.classList.remove('down'), 180);
    });
    cursor.style.opacity = '0.85';
  });
}

async function screenshot(page, name) {
  const destination = path.join(SCREENSHOT_DIR, name);
  await page.screenshot({ path: destination, fullPage: true, animations: 'disabled' });
  console.log(`Screenshot saved: docs/screenshots/demo/${name}`);
}

async function selectUser(page, displayName) {
  const trigger = page.locator('.user-picker__trigger');
  await trigger.click();
  const option = page.locator('.user-picker__option').filter({ hasText: displayName }).first();
  await option.waitFor({ state: 'visible', timeout: 10000 });
  await option.click();
  await page.waitForFunction(
    (name) => document.querySelector('.user-picker__name')?.textContent?.includes(name),
    displayName,
    { timeout: 10000 },
  );
}

async function ask(page, question, expected) {
  const answers = page.locator('.message-bubble--assistant .message-bubble__text');
  const priorCount = await answers.count();
  const input = page.locator('.chat-input');
  await input.click();
  await page.keyboard.type(question, { delay: TYPE_DELAY_MS });
  await page.locator('.chat-send-btn').click();
  await page.waitForFunction(
    (count) => document.querySelectorAll('.message-bubble--assistant .message-bubble__text').length > count
      && !document.querySelector('.typing-indicator'),
    priorCount,
    { timeout: 60000 },
  );
  const latest = page.locator('.message-bubble--assistant').last();
  const text = await latest.locator('.message-bubble__text').innerText();
  if (expected && !expected(text)) throw new Error('Rendered answer did not match the expected real-data check.');
  return latest;
}

async function saveRecording(page, context, browser) {
  let temporaryVideo;
  try {
    const video = page?.video();
    await context?.close();
    if (video) temporaryVideo = await video.path();
  } catch {
    // Preserve the browser error as the primary failure if a video cannot be finalized.
  }
  try { await browser?.close(); } catch { /* Browser may already be closed. */ }
  if (temporaryVideo) {
    await fs.mkdir(VIDEO_DIR, { recursive: true });
    await fs.copyFile(temporaryVideo, VIDEO_FINAL);
    await fs.rm(temporaryVideo, { force: true });
    console.log('Silent browser backup saved: dist/demo_raw.webm');
  }
}

async function run() {
  const totalStartedAt = Date.now();
  let browser;
  let context;
  let page;
  let activeStep = 'startup';
  try {
    await verifyDemoBackend();
    await fs.mkdir(SCREENSHOT_DIR, { recursive: true });
    await fs.mkdir(VIDEO_DIR, { recursive: true });

    browser = await chromium.launch({
      headless: false,
      executablePath: findChrome(),
      args: ['--window-size=1600,900', '--disable-features=Translate'],
    });
    context = await browser.newContext({
      viewport: { width: 1600, height: 900 },
      recordVideo: { dir: VIDEO_DIR, size: { width: 1600, height: 900 } },
    });
    await context.addInitScript(() => {
      const install = () => {
        if (document.getElementById('__demo-cursor')) return;
        const style = document.createElement('style');
        style.textContent = 'html,body,body *{cursor:none!important}#__demo-cursor{position:fixed;z-index:2147483647;left:0;top:0;width:26px;height:26px;border:2px solid #ff5d61;border-radius:50%;background:#ff5d6133;pointer-events:none;transform:translate(-50%,-50%);box-shadow:0 0 0 2px #07111f99,0 0 14px #ff5d61aa}#__demo-cursor::after{content:"";position:absolute;width:5px;height:5px;left:50%;top:50%;border-radius:50%;background:#fff;transform:translate(-50%,-50%)}#__demo-cursor.down{width:38px;height:38px;background:#ff5d6166;transition:width .12s,height .12s}';
        document.head.appendChild(style);
        const cursor = document.createElement('div');
        cursor.id = '__demo-cursor';
        document.body.appendChild(cursor);
        document.addEventListener('mousemove', (event) => {
          cursor.style.left = `${event.clientX}px`;
          cursor.style.top = `${event.clientY}px`;
          cursor.style.opacity = '1';
        });
        document.addEventListener('mousedown', () => {
          cursor.classList.add('down');
          setTimeout(() => cursor.classList.remove('down'), 180);
        });
      };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
      else install();
    });
    page = await context.newPage();

    activeStep = 'architecture';
    let startedAt = Date.now();
    const slide = pathToFileURL(path.join(ROOT, 'docs', 'demo_slide.html')).href;
    await page.goto(slide, { waitUntil: 'domcontentloaded' });
    await addVisibleCursor(page);
    await screenshot(page, '00_architecture.png');
    console.log('Step 1/6: architecture slide.');
    await finishStep(steps.architecture, startedAt);

    activeStep = 'downtime';
    startedAt = Date.now();
    await page.goto(APP_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.locator('.user-picker__name').waitFor({ state: 'visible', timeout: 30000 });
    await addVisibleCursor(page);
    await selectUser(page, 'Michael Turner');
    let latest = await ask(page, questions.areaDowntime, (text) => /Northeast Block 7/i.test(text));
    await latest.locator('.bar-chart-viz, .recharts-bar').first().waitFor({ state: 'visible', timeout: 30000 });
    await latest.locator('.msg-btn--citations').click();
    await latest.locator('.citations-drawer').waitFor({ state: 'visible', timeout: 10000 });
    const calc = latest.locator('details.calculation-explanation');
    await calc.locator('summary').click();
    await page.locator('details.calculation-explanation[open]').waitFor({ state: 'visible' });
    await screenshot(page, '01_downtime_bar_evidence.png');
    await latest.locator('.viz-view-selector button').filter({ hasText: /^Table$/ }).click();
    await latest.locator('.data-table-wrapper, .data-table').first().waitFor({ state: 'visible', timeout: 15000 });
    await screenshot(page, '02_downtime_table.png');
    console.log('Step 2/6: Q6 downtime bar, sources, calculation rule, and table view.');
    await finishStep(steps.downtime, startedAt);

    activeStep = 'status';
    startedAt = Date.now();
    await selectUser(page, 'Tyler Hughes');
    latest = await ask(page, questions.conflictStatus, (text) => /WELL-0175/i.test(text));
    await latest.locator('.conflict-banner').waitFor({ state: 'visible', timeout: 15000 });
    await latest.locator('.status-card').waitFor({ state: 'visible', timeout: 15000 });
    if (!/Data evaluated as of:\s*\d{4}-\d{2}-\d{2}/.test(await latest.innerText())) {
      throw new Error('Status answer did not render the database-derived freshness label.');
    }
    await screenshot(page, '03_status_conflict_card.png');
    console.log('Step 3/6: status card with the real inspection conflict and reference date.');
    await finishStep(steps.status, startedAt);

    activeStep = 'correction';
    startedAt = Date.now();
    await selectUser(page, 'Michael Turner');
    latest = page.locator('.message-bubble--assistant').last();
    await latest.locator('.msg-btn--correct').click();
    await page.locator('.modal').waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('input[value="well"]').check();
    await page.locator('#corr-well-id').fill('WELL-0164');
    await page.locator('#corr-field').fill('wellhead_temp_c');
    await page.locator('#corr-original').fill('24.0');
    await page.locator('#corr-corrected').fill('41.0');
    await page.locator('#corr-reason').fill('Handheld thermal gun was faulty; field crew re-measured the wellhead.');
    await page.locator('#corr-evidence').fill('15 Oct 2026 field re-measurement');
    await page.locator('.modal button[type="submit"]').click();
    await page.getByText('Correction Audited & Recorded to Shared Memory').waitFor({ state: 'visible', timeout: 15000 });
    await screenshot(page, '04_correction_original_preserved.png');
    await page.getByRole('button', { name: 'Done' }).click();
    await page.locator('.corrections-sidebar .correction-item').waitFor({ state: 'visible', timeout: 10000 });
    await screenshot(page, '05_correction_audit_panel.png');

    await selectUser(page, 'Jessica Reed');
    latest = await ask(page, questions.areaStatus, (text) => /shared corrections applied/i.test(text) && /WELL-0164/i.test(text));
    await latest.locator('.conflict-banner').waitFor({ state: 'visible', timeout: 15000 });
    await latest.locator('.data-table-wrapper, .data-table').first().waitFor({ state: 'visible', timeout: 15000 });
    const tableText = await latest.locator('.data-table-wrapper, .data-table').first().innerText();
    if (tableText.includes('WELL-0164')) throw new Error('Corrected well still appeared in the non-producing table.');
    await screenshot(page, '06_shared_correction_area.png');
    console.log('Step 4/6: scoped correction, audit trail, and Jessica’s shared area result.');
    await finishStep(steps.correction, startedAt);

    activeStep = 'memory';
    startedAt = Date.now();
    latest = await ask(page, questions.privateRecall, (text) => /no record|no earlier conversation/i.test(text));
    await screenshot(page, '07_jessica_private_no_history.png');
    await selectUser(page, 'Michael Turner');
    latest = await ask(page, questions.privateRecall, (text) => /WELL-0121/i.test(text) && /25,794/i.test(text));
    await latest.locator('.data-table-wrapper, .data-table').first().waitFor({ state: 'visible', timeout: 15000 });
    await screenshot(page, '08_michael_private_recall_costs.png');
    console.log('Step 5/6: Jessica has no prior three-well exchange; Michael recalls his own wells and costs.');
    await finishStep(steps.memory, startedAt);

    activeStep = 'generalization';
    startedAt = Date.now();
    await selectUser(page, 'Jessica Reed');
    latest = await ask(page, questions.generalization, (text) => /Southwest Block 23/i.test(text) && /repair cost/i.test(text));
    await latest.locator('.bar-chart-viz, .recharts-bar').first().waitFor({ state: 'visible', timeout: 30000 });
    await screenshot(page, '09_unseen_area_repair_costs.png');
    console.log('Step 6/6: a non-chip question across a different area and metric.');
    await finishStep(steps.generalization, startedAt);

    console.log('Final screen is ready.');
    if (!DRY_RUN) await pressEnter('Stop your voice recording, then close the demo');
    await saveRecording(page, context, browser);
    const totalSeconds = (Date.now() - totalStartedAt) / 1000;
    console.log(`Measured driver run: ${totalSeconds.toFixed(1)} seconds (${(totalSeconds / 60).toFixed(2)} minutes).`);
    console.log('All scripted checks used live app responses from the isolated sample-data demo database.');
  } catch (error) {
    console.error(`Demo stopped during ${activeStep}: ${error?.name || 'Error'}.`);
    await saveRecording(page, context, browser);
    process.exitCode = 1;
  } finally {
    rl.close();
  }
}

run();
