// Captura do Replayer em viewports mobile/tablet para checar layout.
import { chromium } from 'playwright';
import fs from 'fs';
const TOKEN = process.env.LL_TOKEN;
const OUT = 'C:/Users/rodri/AppData/Local/Temp/replayer_shots';
fs.mkdirSync(OUT, { recursive: true });
const T='3954736143', H='258858601917'; // AQo UTG+2 @16.5bb (RFI correct)
const VIEWPORTS=[['mobile',390,844],['tablet',820,1180]];
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
const browser=await chromium.launch();
for(const [name,w,h] of VIEWPORTS){
  const ctx=await browser.newContext({viewport:{width:w,height:h},deviceScaleFactor:2});
  await ctx.addInitScript((tok)=>{try{sessionStorage.setItem('ll_token',tok);}catch(e){}},TOKEN);
  const page=await ctx.newPage();
  await page.goto('http://localhost:8080/',{waitUntil:'networkidle',timeout:45000}).catch(()=>{});
  await sleep(1500);
  await page.evaluate(({t,hh})=>{window.history.pushState({},'',`/replayer?t=${t}&h=${hh}`);window.dispatchEvent(new PopStateEvent('popstate'));},{t:T,hh:H});
  await page.waitForSelector('[aria-label^="Passo "]',{timeout:25000}).catch(()=>{});
  await sleep(2000);
  // step da decisao RFI (passo 4 = hero abre)
  const seg=page.locator('[aria-label="Passo 4"]');
  if(await seg.count()){await seg.first().click({force:true});await sleep(900);}
  await page.screenshot({path:`${OUT}/mob_${name}.png`,fullPage:true}).catch(()=>{});
  console.log(`  mob_${name} capturado (${w}x${h})`);
  await ctx.close();
}
await browser.close();
console.log('DONE');
