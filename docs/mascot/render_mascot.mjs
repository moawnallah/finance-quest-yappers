// Renders svg/<pose>.svg to transparent PNGs (512 px) and a contact sheet, with Playwright.
import { chromium } from 'playwright';
import fs from 'fs';
const [svgDir, outDir, sheet] = process.argv.slice(2);
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: 1 });
const names = fs.readdirSync(svgDir).filter(f => f.endsWith('.svg')).sort();
for (const f of names) {
  await p.setContent(`<html><body style="margin:0;background:transparent">${fs.readFileSync(svgDir + '/' + f, 'utf8')}</body></html>`);
  await p.screenshot({ path: `${outDir}/${f.replace('.svg', '.png')}`, omitBackground: true, clip: { x: 0, y: 0, width: 512, height: 512 } });
}
await p.setViewportSize({ width: 1560, height: 560 });
await p.setContent(`<html><body style="margin:0;display:flex;gap:8px;background:#1D1D1D;padding:16px;font:14px sans-serif;color:#ccc">${names.map(f => `<figure style="margin:0;text-align:center;background:#F4F7F2;border-radius:12px;padding:6px"><img src="data:image/svg+xml;base64,${fs.readFileSync(svgDir + '/' + f).toString('base64')}" width="240"><figcaption style="color:#333">${f.replace('.svg','')}</figcaption></figure>`).join('')}</body></html>`);
await p.screenshot({ path: sheet, fullPage: true });
await b.close();
