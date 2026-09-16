// @vitest-environment jsdom
/**
 * A fila de upload no fluxo ASSÍNCRONO, montada de verdade e olhada no DOM (14/09).
 *
 * ── Por que este arquivo existe ──────────────────────────────────────────────────────────────
 *
 * Os guardas que já havia em `uploadQueueVariosTorneios.test.ts` leem o FONTE do componente e
 * conferem a fiação por texto. Eles pegaram dois defeitos meus hoje (a frase da fila de análise
 * desaparecendo e o XP dobrado), então valem. Mas nenhum deles monta a tela.
 *
 * E a lição registrada da casa é que bug de vitrine escapa: o modal de primeiro acesso existia,
 * o estado era `true`, e o ramo que o renderizava nunca rodava. Um teste de estado teria passado
 * verde com o defeito em produção.
 *
 * Aqui a tela é montada e o DOM é lido nas DUAS fases, com as respostas na forma exata que a
 * homologação devolveu contra Postgres (recibo 202, andamento, conclusão, e o caso da cota).
 *
 * ── O que ele defende ────────────────────────────────────────────────────────────────────────
 *
 * 1. Que o arquivo entra e a tela diz que foi recebido, SEM esperar o processamento.
 * 2. Que o andamento aparece ("analisando N de M"), porque é isso que substitui a espera.
 * 3. Que a conclusão mostra o que entrou e o que já estava.
 * 4. Que a cota estourada NÃO aparece como erro, e diz quantos ficaram esperando.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor, act } from "@testing-library/react";

const estado = vi.hoisted(() => ({
  aoReceber: null as unknown,
  recibos: [] as unknown[],
  i: 0,
  xp: [] as unknown[],
}));

vi.mock("@/lib/api", () => ({
  tournaments: {
    // A rota nova: devolve recibo e NAO processa.
    receber: () => Promise.resolve(estado.aoReceber),
    // Cada consulta devolve o proximo retrato do recibo, simulando o worker trabalhando.
    recibo: () => Promise.resolve(estado.recibos[Math.min(estado.i++, estado.recibos.length - 1)]),
    recibosPendentes: () => Promise.resolve({ recibos: [] }),
  },
  metrics: {
    addXp: (...args: unknown[]) => { estado.xp.push(args); return Promise.resolve({}); },
  },
  // A fila le o teto de tamanho do PLANO antes de enviar (16/09). `pro` aqui para os arquivos
  // pequenos destes casos passarem; o teto em si e coberto em `tetoDeUpload.test.ts`.
  subscription: {
    status: () => Promise.resolve({ plan: 'pro', limits: { upload_mb: 40 } }),
  },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    // Devolve chave + argumentos: o teste procura a CHAVE, então ele falha se a tela parar de
    // pedir a frase ao i18n (copy cravada no código é defeito registrado da casa).
    t: (k: string, o?: Record<string, unknown>) =>
      o && typeof o === "object" ? `${k}|${JSON.stringify(o)}` : k,
  }),
  Trans: ({ i18nKey }: { i18nKey?: string }) => <span>{i18nKey}</span>,
}));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ invalidateQueries: () => {} }) }));
vi.mock("@/lib/refreshOnImport", () => ({ EVENTO_LOTE: "lote", invalidarAposImport: () => {} }));

import { UploadQueueProvider, useUploadQueue } from "./UploadQueue";

const TEXTO = "PokerStars Hand #1: Tournament #2";

/** Um arquivo com `text()`.
 *
 * Este jsdom NAO implementa `File.prototype.text` (conferido: `undefined`), e sem o calco o
 * `await file.text()` estoura, a fila marca erro e os cinco casos abaixo falhariam por causa do
 * ambiente em vez do produto. No navegador `File.text` existe -- isto e calco de teste, nao
 * mascara de defeito.
 */
function arquivoFalso() {
  const f = new File([TEXTO], "mao.txt");
  (f as unknown as { text: () => Promise<string> }).text = () => Promise.resolve(TEXTO);
  return f;
}

/** Um botão que enfileira um arquivo, para o teste usar a MESMA porta que o dashboard usa. */
function Gatilho() {
  const { enqueue } = useUploadQueue();
  return <button onClick={() => enqueue([arquivoFalso()])}>soltar</button>;
}

const montar = () =>
  render(<UploadQueueProvider><Gatilho /></UploadQueueProvider>);

const recibo = (extra: Record<string, unknown>) => ({
  id: 7, user_id: 1, filename: "mao.txt", bytes_total: 3215070,
  status: "processando", tentativas: 1,
  torneios_no_arquivo: null, torneios_gravados: 0,
  torneios_ja_estavam: 0, torneios_com_erro: 0,
  detalhe: null, erro: null,
  recebido_em: null, iniciado_em: null, concluido_em: null,
  ...extra,
});

beforeEach(() => { estado.i = 0; estado.xp = []; });
afterEach(() => { cleanup(); });

async function soltarArquivo() {
  montar();
  await act(async () => { screen.getByText("soltar").click(); });
}

describe("a fila de upload com recibo", () => {
  it("diz que o arquivo foi RECEBIDO, sem esperar o processamento", async () => {
    // Forma exata do que a homologacao devolveu: 202 com recibo e sem contagem ainda.
    estado.aoReceber = { recibo: 7, status: "recebido", repetido: false, bytes: 3215070 };
    estado.recibos = [recibo({})];
    await soltarArquivo();
    await waitFor(() => expect(screen.getByText("uploadQueue.recebido")).toBeTruthy());
  });

  it("mostra o ANDAMENTO enquanto o worker trabalha", { timeout: 20000 }, async () => {
    // "8 de 18" e "14 de 18" foram os numeros que a homologacao imprimiu de verdade.
    estado.aoReceber = { recibo: 7, status: "recebido", repetido: false };
    estado.recibos = [
      recibo({ torneios_no_arquivo: 18, torneios_gravados: 8 }),
      recibo({ torneios_no_arquivo: 18, torneios_gravados: 14 }),
    ];
    await soltarArquivo();
    await waitFor(() => {
      const el = screen.getByText(/uploadQueue\.progresso/);
      expect(el.textContent).toContain('"feitos":8');
      expect(el.textContent).toContain('"total":18');
    }, { timeout: 8000 });
  });

  it("na CONCLUSAO diz o que entrou e o que ja estava", { timeout: 20000 }, async () => {
    estado.aoReceber = { recibo: 7, status: "recebido", repetido: false };
    estado.recibos = [recibo({
      status: "concluido", torneios_no_arquivo: 18,
      torneios_gravados: 4, torneios_ja_estavam: 14, detalhe: [],
    })];
    await soltarArquivo();
    // A frase e a de sempre (`variosTorneiosJaEstavam`), com a copy que ja esta nas 3 locales:
    // "ja estava no historico" NAO e perda de dado.
    await waitFor(() => {
      const el = screen.getByText(/uploadQueue\.variosTorneios/);
      expect(el.textContent).toContain('"ok":4');
      expect(el.textContent).toContain('"ja":14');
    }, { timeout: 8000 });
    // e o XP foi pela quantidade de torneios NOVOS, uma vez
    await waitFor(() => expect(estado.xp.length).toBe(1));
    expect(estado.xp[0]).toEqual(["tournament_imported", undefined, 4]);
  });

  it("cota estourada NAO aparece como erro, e diz quantos esperam", { timeout: 20000 }, async () => {
    // O caso que o dono levantou: teto do mes menor que o arquivo. Numeros da homologacao
    // contra Postgres com o arquivo real: 5 de 18 entraram, 13 esperando.
    estado.aoReceber = { recibo: 7, status: "recebido", repetido: false };
    estado.recibos = [recibo({
      status: "aguardando_cota", torneios_no_arquivo: 18,
      torneios_gravados: 5, torneios_ja_estavam: 0, detalhe: [],
    })];
    await soltarArquivo();
    await waitFor(() => {
      const el = screen.getByText(/uploadQueue\.aguardandoCota/);
      expect(el.textContent).toContain('"entraram":5');
      expect(el.textContent).toContain('"esperando":13');
    }, { timeout: 8000 });
    // E o item NAO pode estar pintado de erro: ele nao errou, bateu o teto. Afirmo pela COR,
    // e nao pelo rotulo de status, porque o painel mostra o rotulo so quando NAO ha nota
    // (`item.note ?? item.error ?? t(STATUS_KEY[...])`) -- foi o DOM que me corrigiu aqui.
    const linha = screen.getByText(/uploadQueue\.aguardandoCota/).closest("li")!;
    expect(linha.innerHTML, "a cota estourada foi pintada como erro")
      .not.toContain("text-destructive");
    expect(linha.innerHTML, "o item nao ficou marcado como concluido")
      .toContain("text-primary");
  });

  it("erro de PROCESSAMENTO aparece com o motivo do recibo", { timeout: 20000 }, async () => {
    // O controle do caso acima: erro de verdade tem de continuar aparecendo como erro, senao
    // um tratamento que nunca mostra erro passaria no teste da cota e engoliria falha real.
    estado.aoReceber = { recibo: 7, status: "recebido", repetido: false };
    estado.recibos = [recibo({ status: "erro", erro: "nao conseguimos ler este arquivo" })];
    await soltarArquivo();
    await waitFor(() => {
      expect(screen.getByText("nao conseguimos ler este arquivo")).toBeTruthy();
    }, { timeout: 8000 });
    // e AQUI a pintura de erro tem de aparecer: e o contraste que da valor ao caso da cota.
    const linha = screen.getByText("nao conseguimos ler este arquivo").closest("li")!;
    expect(linha.innerHTML, "erro de verdade parou de ser mostrado como erro")
      .toContain("text-destructive");
  });
});
