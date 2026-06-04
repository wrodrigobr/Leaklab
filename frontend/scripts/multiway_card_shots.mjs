// Captura de cards POSTFLOP MULTIWAY cobertos (solver HU aplicado a pote 3+ way).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
// pega o PRIMEIRO solver card que bate (flop = 1a decisao postflop)
const SPOTS = [
  ['mw_4way',     '3954735475', '258867044771', 'check'],  // flop 4-way check = gto_correct
  ['mw_critical', '3954735475', '258866926485', 'bet'],    // flop 3-way bet = gto_critical
  ['mw_uncov',    '3954736118', '258867578789', 'fold'],   // flop 3-way fold = sem cobertura (controle)
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
    // flop = primeiro hero-action com board de 3 cartas; aproxima pela 1a ocorrência da ação
    if (hasPlayed && playedAct.startsWith(act.slice(0, 4))) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${raw.replace(/\n+/g, ' | ').slice(0, 220)}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
