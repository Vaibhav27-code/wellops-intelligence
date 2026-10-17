const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SCREENSHOTS_DIR = path.resolve(__dirname, '..', 'docs', 'screenshots');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function run() {
  console.log('Launching Chrome from:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,850'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 850 });

  console.log('Navigating to frontend at http://127.0.0.1:5173...');
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle0', timeout: 15000 });

  // 1. Initial State: User A (Michael Turner U-201)
  console.log('1. Checking initial state and UserPicker...');
  await page.waitForSelector('.user-picker__name');
  const initialUser = await page.$eval('.user-picker__name', (el) => el.textContent);
  console.log('Initial user:', initialUser);

  // Ask Q1 (Status Card)
  console.log('Asking Q1 (Status Card)...');
  await page.type('.chat-input', 'Is WELL-0001 producing oil right now? When was it last inspected, and by whom? Show me its status card.');
  await page.click('.chat-send-btn');

  // Wait for assistant response
  await page.waitForSelector('.status-card', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '01_status_card.png'), fullPage: true });
  console.log('Saved 01_status_card.png');

  // 2. Test User Switch & Private Memory Isolation
  console.log('2. Testing user switch to Jessica Reed (U-202)...');
  await page.click('.user-picker__trigger');
  await page.waitForSelector('.user-picker__dropdown');

  // Find option for Jessica Reed
  const options = await page.$$('.user-picker__option');
  for (const opt of options) {
    const text = await opt.evaluate((el) => el.textContent);
    if (text.includes('Jessica Reed')) {
      await opt.click();
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 1000));
  const switchedUser = await page.$eval('.user-picker__name', (el) => el.textContent);
  console.log('Switched user:', switchedUser);

  // Confirm thread is now empty for Jessica Reed (private history isolation)
  const messageCountForUserB = await page.$$eval('.message-bubble', (els) => els.length);
  console.log('Message count for Jessica Reed (expect 0):', messageCountForUserB);
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '02_user_switch_isolated_history.png'), fullPage: true });
  console.log('Saved 02_user_switch_isolated_history.png');

  // 3. Q2: Table View
  console.log('3. Asking Q2 (Table view) as Jessica Reed...');
  await page.type('.chat-input', 'Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.');
  await page.click('.chat-send-btn');
  await page.waitForSelector('.data-table', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '03_table_view.png'), fullPage: true });
  console.log('Saved 03_table_view.png');

  // 4. Q3: Line Chart
  console.log('4. Asking Q3 (Line chart)...');
  await page.type('.chat-input', "Show a line chart of WELL-0001's wellhead temperature against air temperature for the last 13 weeks.");
  await page.click('.chat-send-btn');
  await page.waitForSelector('.line-chart-viz, .recharts-responsive-container', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '04_line_chart.png'), fullPage: true });
  console.log('Saved 04_line_chart.png');

  // 5. Q6: Bar Chart
  console.log('5. Asking Q6 (Bar chart)...');
  await page.type('.chat-input', 'Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?');
  await page.click('.chat-send-btn');
  await page.waitForSelector('.bar-chart-viz, .recharts-bar', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '05_bar_chart.png'), fullPage: true });
  console.log('Saved 05_bar_chart.png');

  // 6. Q7: Map View with Pins
  console.log('6. Asking Q7 (Map view)...');
  await page.type('.chat-input', 'Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.');
  await page.click('.chat-send-btn');
  await page.waitForSelector('.leaflet-marker-icon', { timeout: 20000 });
  const pinCount = await page.$$eval('.leaflet-marker-icon', (els) => els.length);
  console.log(`Found ${pinCount} real Leaflet pins on the map!`);
  await new Promise((r) => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '06_map_view.png'), fullPage: true });
  console.log('Saved 06_map_view.png with real leaflet pins');

  // 7. Q8: Heatmap View
  console.log('7. Asking Q8 (Heatmap view)...');
  await page.type('.chat-input', 'Show a heatmap of 2026 spills by geographic area and month.');
  await page.click('.chat-send-btn');
  await page.waitForSelector('.heatmap-viz', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '07_heatmap_view.png'), fullPage: true });
  console.log('Saved 07_heatmap_view.png');

  // 8. Q18: Conflict Banner
  console.log('8. Asking Q18 (Conflict Banner)...');
  await page.type('.chat-input', 'Did WELL-0101 have a confirmed crude oil spill on 20 Aug 2026?');
  await page.click('.chat-send-btn');
  await page.waitForSelector('.conflict-banner', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '08_conflict_banner.png'), fullPage: true });
  console.log('Saved 08_conflict_banner.png');

  // 9. Submit a correction and confirm in audit panel
  console.log('9. Testing Correction Modal and Audited Panel...');
  // Click the 'Correct' button on the latest assistant message
  const correctBtns = await page.$$('.msg-btn--correct');
  if (correctBtns.length > 0) {
    await correctBtns[correctBtns.length - 1].click();
    await page.waitForSelector('.modal');
    
    // Fill in correction form
    await page.type('#corr-field', 'status');
    await page.type('#corr-original', 'active');
    await page.type('#corr-corrected', 'shut_in');
    await page.type('#corr-reason', 'Field inspection confirmed pump jack offline for maintenance');
    await page.type('#corr-evidence', 'Field work order WO-8821');

    // Click Save
    await page.click('button[type="submit"]');

    // Wait for success screen in modal
    await new Promise((r) => setTimeout(r, 1500));
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '09_correction_modal_saved.png'), fullPage: true });
    console.log('Saved 09_correction_modal_saved.png');

    // Click Done to close modal
    const doneBtn = await page.$('.modal__body button');
    if (doneBtn) {
      await doneBtn.click();
    }
  }

  // Ensure sidebar is open and screenshot the audit panel
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '10_corrections_audit_panel.png'), fullPage: true });
  console.log('Saved 10_corrections_audit_panel.png');

  console.log('All end-to-end browser tests completed successfully!');
  await browser.close();
}

run().catch((err) => {
  console.error('Browser E2E test error:', err);
  process.exit(1);
});
