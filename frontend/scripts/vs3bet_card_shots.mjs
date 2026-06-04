// Captura focada do Decision Card (aside) em spots vs_3bet cobertos.
import { chromium } from 'playwright';
import fs from 'fs';

const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });

// [tag, t, h] — spots vs_3bet cobertos
const SPOTS = [
  ['v3_jj_call', '3910307458', '257047726285'],  // JJ UTG+1 vs BB @28bb call = correct
  ['v3_qq_call', '3910307458', '257046644346'],  // QQ HJ vs CO @14.4bb call = major_leak
  ['v3_aqo_shove', '3954736143', '258858601917'], // AQo UTG+2 vs SB @15.5bb shove = correct
];

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const browser = await chromium.launch();
for (const [tag, T, H] of SPOTS) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addInitScript((tok) => { try { sessionStorage.setItem('ll_token', tok); } catch (e) {} }, TOKEN);
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') console.log(`[${tag} err]`, m.text().slice(0, 120)); });
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 45000 }).catch(e => console.log(`[${tag}] goto:`, e.message));
  await sleep(1500);
  await page.evaluate(({ t, h }) => {
    window.history.pushState({}, '', `/replayer?t=${t}&h=${h}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, { t: T, h: H });
  await page.waitForSelector('[aria-label^="Passo "]', { timeout: 25000 }).catch(() => console.log(`[${tag}] no steps`));
  await sleep(2000);
  const nSteps = await page.locator('[aria-label^="Passo "]').count();
  console.log(`[${tag}] steps=${nSteps}`);

  // varre todos os passos; captura o aside no passo cujo card é vs_3bet
  let shot = false;
  for (let i = 1; i <= nSteps; i++) {
    const seg = page.locator(`[aria-label="Passo ${i}"]`);
    if (await seg.count()) { await seg.first().click({ force: true }); await sleep(500); }
    const aside = page.locator('aside').first();
    if (!(await aside.count())) continue;
    const txt = ((await aside.innerText().catch(() => '')) || '').toLowerCase();
    const isVs3 = txt.includes('3-bet') || txt.includes('3 bet') || txt.includes('vs 3');
    if (isVs3 && (txt.includes('você jogou') || txt.includes('voce jogou'))) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(e => console.log(`  [${tag} s${i}]`, e.message.slice(0,80)));
      console.log(`  [${tag}] vs_3bet card no step ${i} -> ${tag}.png`);
      shot = true;
      break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card vs_3bet encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE ->', OUT);
