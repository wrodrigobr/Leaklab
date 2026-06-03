// Harness de screenshots do Replayer p/ review de design.
// Injeta JWT no sessionStorage, carrega a hand fixa e captura 3 breakpoints.
import { chromium } from 'playwright';
import fs from 'fs';

const TOKEN = process.env.LL_TOKEN;
const T = '3910307458', H = '257045965983';
const URL = `http://localhost:8080/replayer?t=${T}&h=${H}`;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  { name: 'desktop', w: 1440, h: 900 },
  { name: 'tablet',  w: 820,  h: 1180 },
  { name: 'mobile',  w: 390,  h: 844 },
];

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function gotoStep(page, i1) {
  // clica o segmento de passo (aria-label="Passo N", 1-based)
  const seg = page.locator(`[aria-label="Passo ${i1}"]`);
  if (await seg.count()) { await seg.first().click({ force: true }); await sleep(700); }
}

const browser = await chromium.launch();
for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({
    viewport: { width: vp.w, height: vp.h },
    deviceScaleFactor: 2,
  });
  await ctx.addInitScript((tok) => {
    try { sessionStorage.setItem('ll_token', tok); } catch (e) {}
  }, TOKEN);
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') console.log(`[${vp.name} console.error]`, m.text().slice(0, 140)); });
  // Carrega o SPA na raiz (/) — navegar direto em /replayer colide com o proxy
  // do Vite (/replay → backend). Depois navega client-side via History API.
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 45000 }).catch(e => console.log(`[${vp.name}] goto:`, e.message));
  await sleep(1500);
  await page.evaluate(() => {
    window.history.pushState({}, '', '/replayer?t=3910307458&h=257045965983');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  // espera a mesa (svg) + render imperativo (useEffect innerHTML)
  await page.waitForSelector('svg', { timeout: 20000 }).catch(() => console.log(`[${vp.name}] no svg`));
  await sleep(2000);

  const nSteps = await page.locator('[aria-label^="Passo "]').count();
  console.log(`[${vp.name}] steps detectados: ${nSteps}`);

  // passos-alvo: início (preflop), ~meio (postflop), penúltimo (street com bet), último (showdown)
  const targets = vp.name === 'desktop'
    ? [1, Math.max(2, Math.round(nSteps * 0.5)), Math.max(2, nSteps - 1), nSteps]
    : vp.name === 'mobile'
    ? [1, Math.max(2, Math.round(nSteps * 0.6))]
    : [Math.max(2, Math.round(nSteps * 0.5))];

  let k = 0;
  for (const ti of targets) {
    await gotoStep(page, ti);
    await page.screenshot({ path: `${OUT}/${vp.name}_${k}_step${ti}.png`, fullPage: true });
    console.log(`  shot ${vp.name}_${k}_step${ti}.png`);
    k++;
  }

  // desktop extra: range panel aberto no preflop (step 1)
  if (vp.name === 'desktop') {
    await gotoStep(page, 1);
    const rangeBtn = page.getByRole('button', { name: /range/i });
    if (await rangeBtn.count()) {
      await rangeBtn.first().click({ force: true }).catch(() => {});
      await sleep(900);
      await page.screenshot({ path: `${OUT}/${vp.name}_R_rangeopen.png`, fullPage: true });
      console.log(`  shot ${vp.name}_R_rangeopen.png`);
    }
  }
  await ctx.close();
}
await browser.close();
console.log('DONE ->', OUT);
