// Capturas da landing: as telas do produto que a seção "O produto" mostra.
//
// ── Por que existe (28/08) ──────────────────────────────────────────────────────────────────
//
// A seção referenciava `/landing/*.webp` e a pasta nunca existiu: o `main-*.js` publicado continha
// "captura pendente" e o caminho do arquivo, e o visitante via três caixas tracejadas.
//
// ── As duas regras que decidem o que entra ──────────────────────────────────────────────────
//
// **1. Só entra tela com dado REAL.** A `evolucao` ficou de fora de propósito: o banco de captura
// tem um torneio só e `/player/career` responde `insufficient_data`. Semear torneios para desenhar
// uma curva de melhora seria fabricar, numa imagem de marketing, exatamente o número que o produto
// se recusa a inventar na tela do jogador.
//
// **2. Nenhuma identidade real.** O histórico é de um torneio de verdade, com 43 screen names de
// pessoas que não concordaram em aparecer num site aberto. O banco de captura é uma CÓPIA com todos
// eles trocados por "Jogador N", conferida com varredura em toda coluna de texto -- e foi a
// varredura que achou `opponent_profiles.player_name`, a fonte do HUD, que meu filtro por nome de
// coluna tinha deixado passar.
//
// O usuário 990051 é sintético e o banco vive em pasta temporária. Nada de produção.
//
// ── Uso ─────────────────────────────────────────────────────────────────────────────────────
//   LL_TOKEN=<token local> node scripts/landing_shots.mjs
// com o backend em :5000 apontado para o banco de captura e o front em :8080.
import { chromium } from 'playwright';
import fs from 'fs';

const TOKEN = process.env.LL_TOKEN;
if (!TOKEN) { console.error('LL_TOKEN ausente'); process.exit(1); }
const OUT = 'public/landing';
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();

async function novaAba() {
  const ctx = await browser.newContext({
    viewport: { width: 1360, height: 960 }, deviceScaleFactor: 2, colorScheme: 'dark',
  });
  await ctx.addInitScript((t) => {
    try { sessionStorage.setItem('ll_token', t); } catch (e) { /* sem storage */ }
  }, TOKEN);
  const page = await ctx.newPage();
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
  await sleep(1200);
  await fecharOnboarding(page);
  return { ctx, page };
}

/** Fecha o onboarding, se ele aparecer. Ele bloqueou uma rodada inteira de captura: a tela
 *  ficou em "PASSO 1 DE 3" e o card nunca apareceu. O flag no banco resolve, mas um contexto
 *  novo pode trazê-lo de volta, e a captura não pode depender disso. */
async function fecharOnboarding(page) {
  const pular = page.getByRole('button', { name: /pular|skip|omitir/i });
  for (let i = 0; i < 3; i++) {
    if (await pular.count()) {
      await pular.first().click({ force: true }).catch(() => {});
      await sleep(700);
    } else break;
  }
}

async function irPara(page, rota) {
  await page.evaluate((r) => {
    window.history.pushState({}, '', r);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, rota);
}

/** PNG -> WebP usando o próprio Chromium. Evita uma dependência nova para uma conversão só. */
async function paraWebp(png, destino, qualidade = 0.92) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const b64 = await page.evaluate(async ({ dados, q }) => {
    const img = new Image();
    img.src = 'data:image/png;base64,' + dados;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    c.getContext('2d').drawImage(img, 0, 0);
    return c.toDataURL('image/webp', q).split(',')[1];
  }, { dados: png.toString('base64'), q: qualidade });
  fs.writeFileSync(destino, Buffer.from(b64, 'base64'));
  await ctx.close();
  const kb = (fs.statSync(destino).size / 1024).toFixed(0);
  console.log(`  ${destino}  ${kb} KB`);
}

// ── veredito: o card de uma decisão de verdade ──────────────────────────────────────────────
//
// Passo 16 da mão 257048102410: ERRO de -6,5bb, julgado pelo SOLVER, com "você jogou FOLD / GTO
// recomenda CALL" e a estratégia da mão. Foi escolhido porque é o caso que o TEXTO do bloco
// afirma (a fonte do julgamento aparece; o custo em bb sai da própria mão) -- a imagem confirma a
// frase em vez de só decorá-la.
{
  const { ctx, page } = await novaAba();
  await irPara(page, '/replayer?t=3910307458&h=257048102410');
  await page.waitForSelector('[aria-label^="Passo "]', { timeout: 30000 }).catch(() => {});
  await sleep(2500);
  await page.locator('[aria-label="Passo 16"]').first().click({ force: true }).catch(() => {});
  await sleep(1500);
  const det = page.getByText(/detalhes/i);
  if (await det.count()) { await det.first().click({ force: true }).catch(() => {}); }
  // ESPERA o card, em vez de dormir um tanto e torcer. Com `sleep` fixo esta captura falhou uma
  // rodada e passou na seguinte, sem eu mudar nada: script intermitente produz "a captura nao
  // saiu hoje" e ninguem descobre por que.
  await page.waitForFunction(() => {
    const f = [...document.querySelectorAll('*')]
      .filter((e) => e.children.length === 0 && /ESTRAT.GIA DO SOLVER/i.test(e.textContent || ''));
    return f.some((e) => e.getBoundingClientRect().width > 0);
  }, null, { timeout: 20000 }).catch(() => {});
  await sleep(800);

  // O card, não a tela: a moldura da vitrine já dá o contexto de "isto é uma tela do produto".
  //
  // A caixa é medida em tempo de execução, e o filtro `width > 0` NÃO é zelo: a tela renderiza
  // DUAS árvores do card, a do desktop e o bottom-sheet do mobile, e a primeira que o seletor
  // encontra é a escondida. A primeira versão apontou para ela e o Playwright ficou tentando
  // rolar até um elemento de 0x0 até estourar o timeout.
  const caixa = await page.evaluate(() => {
    const folhas = [...document.querySelectorAll('*')]
      .filter((e) => e.children.length === 0 && /ESTRAT.GIA DO SOLVER/i.test(e.textContent || ''));
    const vis = folhas.find((e) => e.getBoundingClientRect().width > 0);
    if (!vis) return null;
    // Sobe até a SECTION do card, e NÃO até o modal: o modal carrega o "X" de fechar e o rodapé
    // "layout: clássico (experimentar o novo)", que é um seletor interno de teste. Controle de
    // janela e alternador de experimento não pertencem a uma imagem de vitrine.
    let n = vis;
    while (n && !(n.tagName === 'SECTION' && n.getBoundingClientRect().width > 300)) {
      n = n.parentElement;
    }
    if (!n) return null;
    const r = n.getBoundingClientRect();
    const p = 10;
    return { x: r.x - p, y: r.y - p, width: r.width + p * 2, height: r.height + p * 2 };
  });
  if (!caixa) {
    const txt = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 400);
    console.error('card de veredito não encontrado. Tela diz:', txt);
    await page.screenshot({ path: `${OUT}/_diag.png` });
    process.exit(1);
  }
  const png = await page.screenshot({ clip: caixa });
  await paraWebp(png, `${OUT}/veredito.webp`);
  await ctx.close();
}

// ── treino: a trilha, com o leak mais caro em foco ──────────────────────────────────────────
{
  const { ctx, page } = await novaAba();
  await irPara(page, '/training');
  // ESPERA o catálogo em vez de dormir: os cards vêm do backend, e capturar antes deles chegarem
  // produz uma imagem de tela vazia que parece um produto sem conteúdo.
  await page.waitForFunction(
    () => /Escolha o que treinar/i.test(document.body.innerText), null, { timeout: 25000 },
  ).catch(() => {});
  await sleep(2500);
  // Corta a barra de navegação do app: a vitrine já desenha uma moldura de navegador em volta, e
  // duas cromas empilhadas leem como print de print. A janela começa nas duas ações de treino e
  // termina no catálogo, que é o que o texto do bloco promete.
  const cat = await page.evaluate(() => {
    const h = [...document.querySelectorAll('h2,h3')]
      .find((e) => /Escolha o que treinar/i.test(e.textContent || ''));
    return h ? Math.max(0, h.getBoundingClientRect().y - 120) : 250;
  });
  const png = await page.screenshot({ clip: { x: 0, y: cat, width: 1360, height: 640 } });
  await paraWebp(png, `${OUT}/treino.webp`);
  await ctx.close();
}

await browser.close();
console.log('DONE');
