// Captura do Decision Card em spots vs_rfi (hero defende vs um open).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['vsrfi_ako', '3954735475', '258867321381'],  // AKo UTG+2 vs UTG @23.4bb call = major_leak
  ['vsrfi_76s', '3954736118', '258867209170'],  // 76s UTG+2 vs UTG+1 @166bb call = acceptable
  ['vsrfi_32o', '3954735475', '258866982879'],  // 32o CO vs HJ @92.7bb fold = correct
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
    if (hasPlayed && txt.includes('vs open')) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      const head = ((await aside.innerText().catch(() => '')) || '').replace(/\n+/g, ' | ').slice(0, 210);
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${head}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card vs_rfi encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
