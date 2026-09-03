const { chromium } = require('playwright');

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    await page.goto('http://localhost:3000/train-model', { waitUntil: 'networkidle', timeout: 30000 });
    await page.screenshot({ path: 'screenshot.png', fullPage: true });
    console.log('Screenshot saved to screenshot.png');
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

run();