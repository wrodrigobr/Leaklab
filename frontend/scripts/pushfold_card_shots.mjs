// Captura de cards PUSH/FOLD cobertos (stack curto, jam/fold/SB-complete).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['pf_jam_ok',  '3954736118', '258867961829', 'shove'],  // 77 HJ @2.5bb shove = correct (ultra-curto)
  ['pf_fold_ml', '3910307458', '257049067622', 'fold'],   // K3s BTN @6.5bb fold = major_leak (devia jammar)
  ['pf_sb_aks',  '3910307458', '257047117239', 'shove'],  // AKs SB @10.4bb shove = major_leak (SB limp data)
  ['pf_k7o',     '4002336128', '260886374797', 'shove'],  // K7o UTG @3.8bb shove = leak (softened)
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
    const actMatch = playedAct.startsWith(act.slice(0, 4));
    const isPreflopCard = /\brfi\b/.test(txt) || txt.includes('abertura') || txt.includes('push');
    if (hasPlayed && actMatch && isPreflopCard && !txt.includes('squeeze') && !txt.includes('3-bet') && !txt.includes('vs open')) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${raw.replace(/\n+/g, ' | ').slice(0, 220)}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card push/fold encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
