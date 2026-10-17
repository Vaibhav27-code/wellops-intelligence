const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SCREENSHOTS_DIR = path.resolve(__dirname, '..', 'docs', 'screenshots');

async function testUnseen() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,850'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 850 });
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle0', timeout: 15000 });

  const unseenQuestions = [
    'Which wells in Southwest Block 23 had maintenance repairs in 2026, and what was the total cost?',
    'How much downtime did T200 wells have in 2025?',
    'How many oil spills occurred in Southwest Block 24 in 2025, and what was the total volume?'
  ];

  for (let i = 0; i < unseenQuestions.length; i++) {
    const q = unseenQuestions[i];
    console.log(`Sending unseen question ${i + 1}: ${q}`);
    await page.type('.chat-input', q);
    await page.click('.chat-send-btn');
    
    // Wait for the new message bubble to appear
    await new Promise((r) => setTimeout(r, 3000));
  }

  // Confirm 6 bubbles (3 user + 3 assistant)
  const count = await page.$$eval('.message-bubble', (els) => els.length);
  console.log(`Total message bubbles in thread: ${count} (expected: 6)`);

  // Verify "Copy as Markdown" exists on all assistant messages
  const copyBtns = await page.$$eval('.msg-btn--copy', (els) => els.length);
  console.log(`Copy as Markdown buttons found: ${copyBtns} (expected: 3)`);

  // Click Copy on the last message
  const lastCopyBtn = (await page.$$('.msg-btn--copy'))[copyBtns - 1];
  if (lastCopyBtn) {
    await lastCopyBtn.click();
    await new Promise((r) => setTimeout(r, 500));
    const btnText = await lastCopyBtn.evaluate((el) => el.textContent);
    console.log(`Copy button state after click: "${btnText}"`);
  }

  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '11_unseen_questions_check.png'), fullPage: true });
  console.log('Saved 11_unseen_questions_check.png');

  await browser.close();
}

testUnseen().catch((err) => {
  console.error('Error in testUnseen:', err);
  process.exit(1);
});
