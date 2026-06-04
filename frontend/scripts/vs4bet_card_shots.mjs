// Captura do Decision Card em spots vs_4bet (hero 3betou, responde a um 4-bet).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['v4b_aa',  'VS4BSWEEP1', 'V4B001'],  // AA jam = major_leak (GTO cala)
  ['v4b_ako', 'VS4BSWEEP1', 'V4B002'],  // AKo jam = correct
  ['v4b_aks', 'VS4BSWEEP1', 'V4B003'],  // AKs jam = acceptable
  ['v4b_kqo', '3954735475', '258867107801'],  // KQo HJ vs UTG+1 @34bb call = major_leak (real)
];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch();
for (const [tag, T, H] of SPOTS) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addInitScript((tok) => { try { sessionStorage.setItem('ll_token', tok); } catch (e) {} }, TOKEN);
  const page = await ctx.newPage();
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
  await sleep(1500);
  await page.evaluate(({ t, h }) => { window.history.pushState({}, '', `/replayer?t=${t}&h=${h}`); window.dispatchEvent(new PopStateEvent('popstate')); }, { t: T, h: H });
  await page.waitForSelector('[aria-label^="Passo "]', { timeout: 25000 }).catch(() => {});
  await sleep(2000);
  const n = await page.locator('[aria-label^="Passo "]').count();
  let shot = false;
  for (let i = 1; i <= n; i++) {
    const seg = page.locator(`[aria-label="Passo ${i}"]`);
    if (await seg.count()) { await seg.first().click({ force: true }); await sleep(420); }
    const aside = page.locator('aside').first();
    if (!(await aside.count())) continue;
    const raw = (await aside.innerText().catch(() => '')) || '';
    const txt = raw.toLowerCase();
    const hasPlayed = txt.includes('você jogou') || txt.includes('voce jogou');
    if (hasPlayed && txt.includes('4-bet')) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${raw.replace(/\n+/g, ' | ').slice(0, 220)}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card vs_4bet encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
