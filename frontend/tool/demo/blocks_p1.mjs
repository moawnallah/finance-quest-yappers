// Demo: build Ania's monthly plan (hard task P1) from blocks only, in a visible browser, with a caption
// for each step, then press Run tests. Records a video.
//
//   cd frontend/tool/demo && npm i playwright@1 && npx playwright install chromium
//   node blocks_p1.mjs [--url https://crococash.xyz] [--video out.webm] [--fast]
//
// The plan it builds:
//   if buffer_months < 2:            save_to_buffer(cash)
//   else: save_to_pot((next_bill - pot) / months_to_next_bill)
//         if card_debt > 0: pay_debt(cash)
//         elif buffer_months < 3: save_to_buffer(cash)
//         else: invest_in(cash * 0.7, fund); invest_in(cash, bond)
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : dflt; };
const URL = arg('--url', 'https://crococash.xyz');
const VIDEO = arg('--video', 'crococash-blocks-demo.webm');
const FAST = process.argv.includes('--fast');
const PAUSE = FAST ? 150 : 650;

const browser = await chromium.launch({ headless: false, slowMo: FAST ? 0 : 60 });
const videoDir = fs.mkdtempSync(path.join(process.cwd(), '.video-'));
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: videoDir, size: { width: 1440, height: 900 } } });
const p = await ctx.newPage();

// ---- helpers (Flutter draws on a canvas; its accessibility tree tells us where each block is)
const sem = async () => { await p.evaluate(() => document.querySelector('flt-semantics-placeholder')?.click()); await p.waitForTimeout(100); };
const boxes = re => p.evaluate(src => { const r = new RegExp(src); return [...document.querySelectorAll('flt-semantics')]
  .filter(e => r.test((e.getAttribute('aria-label') || '') + '\n' + (e.childElementCount ? '' : e.textContent || '')))
  .map(e => { const b = e.getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width, h: b.height }; })
  .filter(b => b.w > 0 && b.h > 0); }, re.source);
const caption = text => p.evaluate(t => {
  let el = document.getElementById('demo-caption');
  if (!el) { el = document.createElement('div'); el.id = 'demo-caption';
    el.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:99999;background:rgba(14,132,48,.95);color:#fff;'
      + 'font:600 18px/1.35 system-ui,sans-serif;padding:12px 20px;border-radius:14px;box-shadow:0 6px 24px rgba(0,0,0,.25);max-width:80vw;text-align:center;pointer-events:none';
    document.body.appendChild(el); }
  el.textContent = t; }, text);
const palette = async re => { // tap a block in the palette, scrolling the palette until it is visible
  for (let k = 0; k < 25; k++) { await sem(); const r = (await boxes(re)).filter(x => x.x < 690)[0];
    if (r && r.y > 105 && r.y < 630) { await p.mouse.click(r.x, r.y); await p.waitForTimeout(PAUSE); return; }
    await p.mouse.move(520, 400); await p.mouse.wheel(0, r && r.y <= 105 ? -160 : 160); await p.waitForTimeout(150); }
  throw new Error('palette block not reachable ' + re); };
const tap = async (re, pick = 0) => { // tap something in the workspace (pick -1 = the last match)
  for (let k = 0; k < 20; k++) { await sem(); const xs = await boxes(re); const r = xs[pick < 0 ? xs.length + pick : pick];
    if (r) { await p.mouse.click(r.x, r.y); await p.waitForTimeout(PAUSE); return; } await p.waitForTimeout(250); }
  throw new Error('not found ' + re); };
const down = async () => { await p.mouse.move(1000, 400); for (let i = 0; i < 6; i++) { await p.mouse.wheel(0, 400); await p.waitForTimeout(60); } await p.waitForTimeout(250); };
const blocks = async list => { for (const re of list) await palette(re); };
const number = async v => { await palette(/a number.*\nnumber$/); await down(); await tap(/\n1000$/, -1);
  await p.keyboard.press('ControlOrMeta+A'); await p.keyboard.type(v, { delay: FAST ? 0 : 90 }); await p.keyboard.press('Enter'); await p.waitForTimeout(PAUSE); };

// ---- open the task (CanvasKit can take a while to download on slow networks)
await p.goto(`${URL}/#/hard/p1.h1`, { waitUntil: 'load' });
for (let i = 0; i < 120 && !(await p.$('flt-semantics-placeholder')); i++) await p.waitForTimeout(1000);
await p.waitForTimeout(2500);
await caption('Ania\'s monthly money plan, built from blocks only'); await p.waitForTimeout(PAUSE * 3);
await sem(); while ((await boxes(/Remove this block/)).length) await tap(/Remove this block/, 0); // a clean workspace

await caption('1. Safety first: if the buffer covers less than 2 months, save to the buffer');
await palette(/if … :$/); await blocks([/\nbuffer_months$/, /is less than\n<$/]); await number('2');
await palette(/save_to_buffer$/);

await caption('2. Otherwise: set money aside for the next known bill, spread over the months left');
await palette(/else:$/);
await palette(/save_to_pot$/);
await tap(/Tap to change or remove\ncash$/, -1); await tap(/^Remove\n?$|\nRemove$/, -1);
await blocks([/\($/, /\nnext_bill$/, /minus\n-$/, /\npot$/, /\)$/, /divided by\n\/$/, /\nmonths_to_next_bill$/]);

await caption('3. Expensive card debt goes before investing (a sure 20% saved)');
await tap(/Slot: put a line here/, -2);
await palette(/if … :$/); await blocks([/\ncard_debt$/, /is more than\n>$/]); await number('0');
await palette(/pay_debt$/);

await caption('4. Then grow the buffer to 3 months');
await palette(/elif … :$/); await blocks([/\nbuffer_months$/, /is less than\n<$/]); await number('3');
await palette(/save_to_buffer$/);

await caption('5. Only then invest: 70% in a broad fund, the rest in a bond (diversified)');
await palette(/else:$/);
await palette(/invest_in$/);
await down(); await tap(/Gap: put a condition or an amount here/, -1);
await palette(/times\n\*$/); await number('0.7');
await down(); await tap(/Slot: put a line here/, -3);
await palette(/invest_in$/);
await down(); await tap(/Asset: fund/, -1); await tap(/^bond\n?$/, -1);

await caption('The code the blocks make');
await tap(/Code/, -1); await p.waitForTimeout(PAUSE * 4);
await caption('Run the public tests: a 2-month job loss, a normal 24 months, a car repair');
await tap(/Run tests/, 0); await p.waitForTimeout(4000); await tap(/Test results/, -1); await p.waitForTimeout(800); await sem();
const ok = await p.evaluate(() => [...document.querySelectorAll('flt-semantics')].some(e => /All required public tests pass/.test(e.textContent || '')));
await caption(ok ? 'All required tests pass. Submit to face 6 hidden events and 200 possible futures.' : 'Some tests failed: check the plan');
await p.waitForTimeout(FAST ? 1500 : 5000);
console.log(ok ? 'PASS: all required public tests pass' : 'FAIL: tests did not pass');

const video = await p.video().path();
await ctx.close(); await browser.close();
fs.renameSync(video, VIDEO); fs.rmSync(videoDir, { recursive: true, force: true });
console.log('video:', path.resolve(VIDEO));
