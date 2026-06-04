// Captura do Decision Card em spots POSTFLOP cobertos (estratégia do solver).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['pf_correct',  '3954735475', '258867044771'],  // flop check = gto_correct
  ['pf_critical', '3954735475', '258866963362'],  // flop bet = gto_critical (GTO faz check)
  ['pf_mixed',    '3954735475', '258867013425'],  // flop bet = gto_mixed (marginal)
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
    // primeiro card postflop com estratégia do solver (= flop, a 1a decisão postflop)
    if (hasPlayed && txt.includes('estratégia do solver')) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      const head = ((await aside.innerText().catch(() => '')) || '').replace(/\n+/g, ' | ').slice(0, 220);
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${head}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card postflop solver encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
