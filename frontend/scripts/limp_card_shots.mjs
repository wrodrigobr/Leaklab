// Captura de cards em POTE LIMPADO (vs Limp, fora da cobertura GTO).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['lp_call',  '3954736118', '258867353518', 'call'],   // 64o SB @94bb call vs limp
  ['lp_raise', '3954736118', '258867407410', 'raise'],  // QJo CO @63bb iso-raise vs limp
  ['lp_shove', '3954736118', '258867824372', 'shove'],  // KQo BTN @18bb jam vs limp
  ['lp_check', '3954736118', '258867715733', 'check'],  // K6o BB @36bb check (opcao)
];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch();
for (const [tag, T, H, act] of SPOTS) {
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
    const m = raw.match(/VOC[ÊE] JOGOU\s*\n?\s*([A-Za-zÀ-ÿ]+)/i);
    const playedAct = m ? m[1].toLowerCase() : '';
    if (hasPlayed && playedAct.startsWith(act.slice(0, 4)) && txt.includes('limp')) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${raw.replace(/\n+/g, ' | ').slice(0, 200)}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card limp encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
