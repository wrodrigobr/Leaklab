// Captura do RangePanel (grade 13x13) em spots cobertos.
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['rp_rfi',  '3954736143', '258858601917', 1],   // AQo UTG+2 @16.5bb RFI -> grade abertura
  ['rp_vs3b', '3910307458', '257047653989', 10],  // AQs UTG+2 vs BTN 3bet -> grade vs 3bet (#28)
];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const browser = await chromium.launch();
for (const [tag, T, H, stepN] of SPOTS) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addInitScript((tok) => { try { sessionStorage.setItem('ll_token', tok); } catch (e) {} }, TOKEN);
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') console.log(`[${tag} err]`, m.text().slice(0, 110)); });
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
  await sleep(1500);
  await page.evaluate(({ t, h }) => { window.history.pushState({}, '', `/replayer?t=${t}&h=${h}`); window.dispatchEvent(new PopStateEvent('popstate')); }, { t: T, h: H });
  await page.waitForSelector('[aria-label^="Passo "]', { timeout: 25000 }).catch(() => {});
  await sleep(2000);
  // navega ao passo da decisão
  const seg = page.locator(`[aria-label="Passo ${stepN}"]`);
  if (await seg.count()) { await seg.first().click({ force: true }); await sleep(700); }
  // abre o painel de range
  const rangeBtn = page.getByRole('button', { name: /range|grade/i });
  if (await rangeBtn.count()) {
    await rangeBtn.first().click({ force: true }).catch(() => {});
    await sleep(1200);
    await page.screenshot({ path: `${OUT}/${tag}.png`, fullPage: false }).catch(() => {});
    console.log(`  [${tag}] capturado (botao range encontrado)`);
  } else {
    console.log(`  [${tag}] botao range NAO encontrado`);
  }
  await ctx.close();
}
await browser.close();
console.log('DONE');
