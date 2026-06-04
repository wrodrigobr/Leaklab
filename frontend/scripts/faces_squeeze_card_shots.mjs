// Captura focada do Decision Card (aside) em spots faces_squeeze.
import { chromium } from 'playwright';
import fs from 'fs';

const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });

// [tag, t, h, matcher] — matcher: substrings (lower) que identificam o card-alvo
const SPOTS = [
  ['fs_jj_fold',   '3954735475', '258867310602', ['squeeze']],          // JJ HJ vs UTG+2 @23.6bb fold = major_leak
  ['fs_73o_fold',  '3954735475', '258867236307', ['squeeze']],          // 73o BB vs BTN @26.6bb fold = correct
  ['fs_kjo_nocov', '3910307458', '257048851115', ['squeeze', 'veredito', 'cobertura']], // KJo BTN @5.4bb call = no-coverage
];

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const browser = await chromium.launch();
for (const [tag, T, H, needles] of SPOTS) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addInitScript((tok) => { try { sessionStorage.setItem('ll_token', tok); } catch (e) {} }, TOKEN);
  const page = await ctx.newPage();
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

  let shot = false;
  for (let i = 1; i <= nSteps; i++) {
    const seg = page.locator(`[aria-label="Passo ${i}"]`);
    if (await seg.count()) { await seg.first().click({ force: true }); await sleep(500); }
    const aside = page.locator('aside').first();
    if (!(await aside.count())) continue;
    const txt = ((await aside.innerText().catch(() => '')) || '').toLowerCase();
    const hasPlayed = txt.includes('você jogou') || txt.includes('voce jogou');
    const match = needles.some(n => txt.includes(n));
    if (hasPlayed && match) {
      await aside.screenshot({ path: `${OUT}/${tag}.png` }).catch(e => console.log(`  [${tag} s${i}]`, e.message.slice(0,80)));
      console.log(`  [${tag}] card no step ${i} -> ${tag}.png`);
      shot = true;
      break;
    }
  }
  if (!shot) console.log(`  [${tag}] NENHUM card-alvo encontrado`);
  await ctx.close();
}
await browser.close();
console.log('DONE ->', OUT);
