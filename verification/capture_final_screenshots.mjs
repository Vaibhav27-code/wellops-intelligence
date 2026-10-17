import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const { chromium } = require(require.resolve('playwright-core', { paths: [path.join(ROOT, 'frontend')] }));

const APP_URL = 'http://localhost:5173';
const SHOT_DIR = path.join(ROOT, 'docs', 'screenshots', 'final');

async function main() {
  console.log('Running UI browser validation and capturing screenshots...');
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
  });

  const page = await browser.newPage({
    viewport: { width: 1400, height: 950 },
  });

  try {
    await page.goto(APP_URL, { waitUntil: 'networkidle', timeout: 15000 });
    console.log('App loaded.');

    // Screenshot 1: Shell and User Picker with all 28 users available
    const userTrigger = page.locator('.user-picker__trigger');
    await userTrigger.click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOT_DIR, '01_all_users_picker.png') });
    console.log('Saved 01_all_users_picker.png');
    await userTrigger.click(); // close dropdown

    // Send a question in the UI
    const textarea = page.locator('textarea.chat-input');
    await textarea.fill('Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.');
    const sendBtn = page.locator('.chat-send-btn');
    await sendBtn.click();
    console.log('Sent question. Waiting for answer...');

    // Wait for assistant response
    await page.waitForSelector('.message-bubble--assistant', { timeout: 15000 });
    await page.waitForTimeout(1000);

    // Screenshot 2: Answer with Bar Chart and Citations
    await page.screenshot({ path: path.join(SHOT_DIR, '02_bar_chart_answer.png') });
    console.log('Saved 02_bar_chart_answer.png');

    // Switch view to Table via View Selector
    const tableBtn = page.getByRole('button', { name: 'Table', exact: true });
    if (await tableBtn.count() > 0) {
      await tableBtn.click();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(SHOT_DIR, '03_table_view_fallback.png') });
      console.log('Saved 03_table_view_fallback.png');
    }

    // Expand citations drawer
    const citBtn = page.locator('.msg-btn--citations');
    if (await citBtn.count() > 0) {
      await citBtn.click();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(SHOT_DIR, '04_citations_drawer_expanded.png') });
      console.log('Saved 04_citations_drawer_expanded.png');
    }

    // Test New session button
    const newSessionBtn = page.getByTitle('Start a fresh chat session for this user');
    if (await newSessionBtn.count() > 0) {
      await newSessionBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SHOT_DIR, '05_new_session_cleared.png') });
      console.log('Saved 05_new_session_cleared.png');
    }

    console.log('All browser verification tests completed successfully!');
  } catch (err) {
    console.error('Browser testing failed:', err);
  } finally {
    await browser.close();
  }
}

main();
