// Vendored from https://github.com/gpenessot/streamlit-keep-alive @ main (audited 2026-11-12).
// Visits public Streamlit URLs only; no secrets or outbound calls besides the target app.

const fs = require('fs');
const puppeteer = require('puppeteer');

const SLEEP_TEXT = /gone to sleep|zzzz/i;
const WAKE_TEXT = /get this app back up/i;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseUrls(raw) {
  return (raw || '')
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function writeSummary(lines) {
  const file = process.env.GITHUB_STEP_SUMMARY;
  if (!file) return;
  try {
    fs.appendFileSync(file, lines.join('\n') + '\n');
  } catch (e) {
    console.warn(`Could not write job summary: ${e.message}`);
  }
}

async function pageText(page) {
  const texts = [];
  for (const frame of page.frames()) {
    try {
      texts.push(await frame.evaluate(() => (document.body ? document.body.innerText : '')));
    } catch (e) {
      // Frame detached during navigation: ignore it.
    }
  }
  return texts.join('\n');
}

async function findWakeButton(page) {
  for (const frame of page.frames()) {
    let buttons = [];
    try {
      buttons = await frame.$$('button');
    } catch (e) {
      continue;
    }
    for (const button of buttons) {
      const text = await frame.evaluate((el) => el.innerText || '', button);
      if (WAKE_TEXT.test(text)) return { button, text: text.trim() };
    }
  }
  return null;
}

async function probe(browser, url, timeoutMs) {
  const page = await browser.newPage();
  try {
    await page.setUserAgent(
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    );
    await page.goto(url, { waitUntil: 'networkidle2', timeout: timeoutMs });
    await sleep(5000);

    if (!SLEEP_TEXT.test(await pageText(page))) return 'awake';

    const wake = await findWakeButton(page);
    if (!wake) throw new Error('sleep page detected but no wake-up button found');

    console.log(`  Sleeping. Clicking "${wake.text}"`);
    await wake.button.click();

    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      await sleep(5000);
      if (!SLEEP_TEXT.test(await pageText(page))) return 'woken up';
    }
    throw new Error('wake-up button clicked but the app still shows the sleep page');
  } finally {
    await page.close();
  }
}

(async () => {
  const urls = parseUrls(process.argv[2] || process.env.APP_URL);
  const timeoutMs = (parseInt(process.argv[3], 10) || 60) * 1000;

  if (urls.length === 0) {
    console.error('Usage: node probe.js "<URL>[,<URL>...]" [timeout-seconds]');
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    headless: true,
  });

  const rows = [];
  let failures = 0;
  try {
    for (const url of urls) {
      console.log(`Probing ${url}`);
      try {
        const status = await probe(browser, url, timeoutMs);
        console.log(`  ${status}`);
        rows.push(`| ${url} | ${status} |`);
      } catch (e) {
        failures += 1;
        console.error(`  failed: ${e.message}`);
        rows.push(`| ${url} | failed: ${e.message} |`);
      }
    }
  } finally {
    await browser.close();
  }

  writeSummary(['### Streamlit Keep Alive', '', '| App | Status |', '|---|---|', ...rows]);
  process.exit(failures > 0 ? 1 : 0);
})();
