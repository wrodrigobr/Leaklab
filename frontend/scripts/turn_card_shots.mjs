// Captura do Decision Card em spots de TURN cobertos (estratégia do solver).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
// [tag, t, h, heroAction] — pega o ÚLTIMO card solver cuja ação bate (turn vem depois do flop)
const SPOTS = [
  ['turn_correct',  '3910307458', '257046644346', 'shove'],  // turn shove = gto_correct
  ['turn_critical', '3910307458', '257048102410', 'fold'],   // turn fold vs GTO allin = gto_critical
  ['turn_mixed',    '3954736118', '258867373219', 'bet'],    // turn bet vs GTO check = gto_mixed
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
  let lastShot = null, lastHead = null;
  for (let i = 1; i <= n; i++) {
    const seg = page.locator(`[aria-label="Passo ${i}"]`);
    if (await seg.count()) { await seg.first().click({ force: true }); await sleep(420); }
    const aside = page.locator('aside').first();
    if (!(await aside.count())) continue;
    const raw = (await aside.innerText().catch(() => '')) || '';
    const txt = raw.toLowerCase();
    const hasPlayed = txt.includes('você jogou') || txt.includes('voce jogou');
    const isSolver = txt.includes('estratégia do solver') || txt.includes('equity necessária');
    // ação do hero: "VOCÊ JOGOU\n<ACT>"
    const m = raw.match(/VOC[ÊE] JOGOU\s*\n?\s*([A-Za-zÀ-ÿ]+)/i);
    const playedAct = m ? m[1].toLowerCase() : '';
    const actMatch = playedAct.startsWith(act.slice(0,4)) || (act==='shove' && (playedAct.includes('shove')||playedAct.includes('all')));
    if (hasPlayed && isSolver && actMatch) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      lastShot = i; lastHead = raw.replace(/\n+/g, ' | ').slice(0, 220);
    }
  }
  if (lastShot) console.log(`  [${tag}] step ${lastShot} -> ${tag}.png :: ${lastHead}`);
  else console.log(`  [${tag}] NENHUM card turn encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
