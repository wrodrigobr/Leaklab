// Captura focada do Decision Card (aside) em spots vs_shove_fallback.
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['vsh_kk',  '4002336128', '260886370275'],  // KK HJ @26.4bb call = correct (in_range)
  ['vsh_qts', '3995547877', '260605903016'],  // QTs UTG @9.2bb call = leak (in_range) CONTRADIÇÃO
  ['vsh_q3o', '3954736118', '258867272112'],  // Q3o SB @118bb call = leak (NOT in range) legit
  ['vsh_64s', '3954736118', '258867817765'],  // 64s SB @21.5bb call = acceptable (in_range)
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
  console.log(`[${tag}] steps=${n}`);
  let shot = false;
  for (let i = 1; i <= n; i++) {
    const seg = page.locator(`[aria-label="Passo ${i}"]`);
    if (await seg.count()) { await seg.first().click({ force: true }); await sleep(450); }
    const aside = page.locator('aside').first();
    if (!(await aside.count())) continue;
    const txt = ((await aside.innerText().catch(() => '')) || '').toLowerCase();
    const hasPlayed = txt.includes('você jogou') || txt.includes('voce jogou');
    if (hasPlayed && (txt.includes('shove') || txt.includes('heur'))) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      console.log(`  [${tag}] card no step ${i} -> ${tag}.png`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card vs_shove encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
