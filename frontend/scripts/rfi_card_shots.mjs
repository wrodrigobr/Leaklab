// Captura do Decision Card em spots RFI (hero abre primeiro).
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const SPOTS = [
  ['rfi_aqo', '3954736143', '258858601917'],  // AQo UTG+2 @16.5bb raise = correct
  ['rfi_t8s', '3954735475', '258866971409'],  // T8s UTG+1 @93bb fold = major_leak (deve abrir)
  ['rfi_85s', '280605609',  'SG3812283537'],  // 85s BTN @15bb raise = major_leak (deve foldar)
  ['rfi_ato', '3910307458', '257046368387'],  // ATo CO @17.9bb raise = acceptable (mix raise/jam)
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
    // RFI: scenario chip "RFI" e header "Range de abertura"; exclui squeeze/3-bet/open/shove-heur
    if (hasPlayed && txt.includes('rfi') && !txt.includes('squeeze') && !txt.includes('3-bet') && !txt.includes('vs open')) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(() => {});
      const head = ((await aside.innerText().catch(() => '')) || '').replace(/\n+/g, ' | ').slice(0, 210);
      console.log(`  [${tag}] step ${i} -> ${tag}.png :: ${head}`);
      shot = true; break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card RFI encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
