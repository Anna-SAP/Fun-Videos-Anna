// Render every .svg in a folder to a transparent .png of the same size (headless Chromium via Playwright).
//   node scripts/render_svg.mjs work/assets/props [scale]
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const dir = process.argv[2];
const scale = Number(process.argv[3] || 1);
const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: scale });
for (const f of fs.readdirSync(dir).filter((f) => f.endsWith('.svg'))) {
  const svg = fs.readFileSync(path.join(dir, f), 'utf8');
  const w = Number(svg.match(/width="(\d+)"/)[1]);
  const h = Number(svg.match(/height="(\d+)"/)[1]);
  await page.setViewportSize({ width: w, height: h });
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
  await page.locator('svg').screenshot({ path: path.join(dir, f.replace('.svg', '.png')), omitBackground: true });
}
await browser.close();
console.log('rendered');
