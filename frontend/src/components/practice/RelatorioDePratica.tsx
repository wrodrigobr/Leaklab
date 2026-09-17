import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { practice, type PracticeHand, type PracticeReport } from "@/lib/api";
import { NIVEIS, SIMBOLO_DO_NIVEL, type Nivel } from "@/lib/pratica";
import { cn } from "@/lib/utils";

/**
 * O relatório do treino: o placar da sessão, os cortes por posição e por cenário, e a tabela das
 * últimas mãos praticadas.
 *
 * ── O pedido (16/09) ──────────────────────────────────────────────────────────────────────────
 *
 * O dono: "seria interessante armazenar este treino, para ficar no historico das ultimas maos
 * treinadas, e ter a possibilidade de gerar um relatorio como o do gto wizard".
 *
 * ── Por que os números NÃO são calculados aqui ────────────────────────────────────────────────
 *
 * Nem o veredito de cada mão nem os agregados. Os dois vêm do servidor (`/practice/report`), e o
 * motivo é a regra 5 da casa: a régua dos quatro níveis já morou no front, e com o histórico
 * gravando no banco havia duas contas para o mesmo julgamento. Aqui só se PINTA.
 *
 * O placar da sessão em curso continua no painel lateral, porque ele conta o que está acontecendo
 * agora e não precisa de ida ao servidor a cada mão. Os dois números podem diferir por um instante
 * (a mão que acabou de ser respondida), e isso é por desenho: um é ao vivo, o outro é o que está
 * guardado.
 */

const COR_DO_NIVEL: Record<Nivel, string> = {
  correta: "text-emerald-300",
  imprecisao: "text-amber-300",
  errada: "text-red-300",
  grave: "text-red-400",
};

/** Quantas mãos a tabela pede por vez. */
const PAGINA = 50;

function Numero({ valor, rotulo, tom, id }: {
  valor: string; rotulo: string; tom?: string; id?: string;
}) {
  return (
    <div className="rounded border border-border bg-hud-surface px-2.5 py-1.5" data-testid={id}>
      <div className={cn("font-mono text-lg font-bold leading-none tabular-nums", tom || "text-foreground")}>
        {valor}
      </div>
      <div className="mt-1 font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
        {rotulo}
      </div>
    </div>
  );
}

/** Uma linha de corte (por posição, por cenário): quantas mãos, quanto acertou, quanto custou. */
function Corte({ titulo, dados }: {
  titulo: string;
  dados: Record<string, { maos: number; corretas: number; bb: number }>;
}) {
  const linhas = Object.entries(dados).sort((a, b) => b[1].maos - a[1].maos);
  if (!linhas.length) return null;
  return (
    <div className="min-w-0">
      <div className="mb-1 font-mono text-[9.5px] uppercase tracking-widest-2 text-muted-foreground">
        {titulo}
      </div>
      <div className="space-y-0.5">
        {linhas.map(([k, v]) => (
          <div key={k} className="flex items-baseline gap-2 font-mono text-[11px]">
            <span className="w-14 shrink-0 truncate font-bold text-foreground">{k}</span>
            <span className="tabular-nums text-muted-foreground">{v.maos}</span>
            {/* a barra é a taxa de acerto: ela lê antes do número, e é o que o olho compara
                entre posições */}
            <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-border">
              <span className="block h-full rounded-full bg-primary"
                    style={{ width: `${v.maos ? (100 * v.corretas) / v.maos : 0}%` }} />
            </span>
            <span className="w-10 shrink-0 text-right tabular-nums text-muted-foreground">
              {v.maos ? Math.round((100 * v.corretas) / v.maos) : 0}%
            </span>
            <span className="w-14 shrink-0 text-right tabular-nums text-red-400/80">
              {v.bb ? `−${v.bb.toFixed(2)}` : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RelatorioDePratica({ aberto, onFechar }: {
  aberto: boolean;
  onFechar: () => void;
}) {
  const { t } = useTranslation("practice");
  const [relatorio, setRelatorio] = useState<PracticeReport | null>(null);
  const [maos, setMaos] = useState<PracticeHand[]>([]);
  const [proximo, setProximo] = useState<number | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(false);
    try {
      const [r, h] = await Promise.all([practice.report(200), practice.history(PAGINA)]);
      setRelatorio(r);
      setMaos(h.maos);
      setProximo(h.maos.length >= PAGINA ? h.proximo : null);
    } catch {
      setErro(true);
    } finally {
      setCarregando(false);
    }
  }, []);

  // Recarrega a cada ABERTURA, e não uma vez só: o jogador abre isto DEPOIS de praticar, e um
  // relatório em cache diria menos mãos do que ele acabou de jogar.
  useEffect(() => {
    if (aberto) void carregar();
  }, [aberto, carregar]);

  const mais = useCallback(async () => {
    if (!proximo || carregando) return;
    setCarregando(true);
    try {
      const h = await practice.history(PAGINA, proximo);
      setMaos((m) => [...m, ...h.maos]);
      setProximo(h.maos.length >= PAGINA ? h.proximo : null);
    } catch {
      setErro(true);
    } finally {
      setCarregando(false);
    }
  }, [proximo, carregando]);

  if (!aberto) return null;

  const r = relatorio;
  const julgadas = r?.julgadas ?? 0;

  return (
    // ── Fundo OPACO, e z ACIMA do painel lateral ────────────────────────────────────────────
    //
    // O dono abriu o relatorio e ele saiu transparente sobre as quatro mesas, com o painel de
    // configuracao por cima. Duas causas, e uma licao.
    //
    // A do z e simples: o painel lateral vem depois no DOM e pintava em cima; `z-40` resolve.
    //
    // A do fundo era `bg-background/97`. A minha primeira explicacao foi que o token
    // `hsl(var(--background))` nao aceita alpha e o Tailwind descartaria a classe -- e eu quase
    // escrevi um guarda com essa teoria. A medicao a derrubou: o projeto tem 1.164 usos de
    // opacidade sobre tokens do tema e todos funcionam. O que sobra como causa e o CSS gerado nao
    // ter a classe no momento em que ele abriu a tela, porque `/97` era um valor novo no projeto
    // e o JIT precisa reprocessar.
    //
    // Entao o fundo passa a ser uma classe que o projeto JA usa em varios lugares, opaca e sem
    // valor arbitrario nenhum: nada a gerar, nada a reprocessar. Um painel que cobre a tela nao
    // ganha nada com 3% de transparencia.
    <div data-testid="pratica-relatorio"
         className="absolute inset-0 z-40 flex flex-col overflow-hidden bg-background">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2">
        <span className="font-mono text-[11px] uppercase tracking-widest-2 text-primary">
          {t("relatorio.titulo")}
        </span>
        <button onClick={onFechar} data-testid="pratica-relatorio-fechar"
                className="rounded border border-border p-1 text-muted-foreground transition-colors hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-hud p-3">
        {erro && (
          <div data-testid="pratica-relatorio-erro"
               className="rounded border border-border bg-hud-surface p-3 text-center font-mono text-[11px] text-muted-foreground">
            {t("relatorio.erro")}
          </div>
        )}

        {!erro && r && r.maos === 0 && (
          <div data-testid="pratica-relatorio-vazio"
               className="rounded border border-border bg-hud-surface p-4 text-center font-mono text-[11px] leading-relaxed text-muted-foreground">
            {t("relatorio.vazio")}
          </div>
        )}

        {!erro && r && r.maos > 0 && (
          <>
            {/* ── o placar ─────────────────────────────────────────────────────────────── */}
            <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
              <Numero id="placar-maos" valor={String(r.maos)} rotulo={t("relatorio.maos")} />
              <Numero id="placar-acerto" valor={r.acerto != null ? `${r.acerto}%` : "—"}
                      rotulo={t("relatorio.acerto")} tom="text-primary" />
              <Numero id="placar-bb" valor={`−${r.bb_perdidos.toFixed(2)}`}
                      rotulo={t("relatorio.bbPerdidos")} tom="text-red-400" />
              <Numero id="placar-bb-mao"
                      valor={r.bb_por_mao != null ? `−${r.bb_por_mao.toFixed(3)}` : "—"}
                      rotulo={t("relatorio.bbPorMao")} tom="text-red-400/90" />
            </div>

            {/* ── a distribuição dos vereditos ─────────────────────────────────────────── */}
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              {NIVEIS.map((n) => {
                const q = r.por_nivel[n] ?? 0;
                return (
                  <span key={n}
                        className="inline-flex items-center gap-1.5 rounded border border-border bg-hud-surface px-2 py-1 font-mono text-[10.5px]">
                    <span className={cn("font-bold", COR_DO_NIVEL[n])}>{SIMBOLO_DO_NIVEL[n]}</span>
                    <span className="text-muted-foreground">{t(`nivel.${n}`)}</span>
                    <b className={cn("tabular-nums", COR_DO_NIVEL[n])}>{q}</b>
                    <span className="tabular-nums text-muted-foreground/60">
                      {julgadas ? `${Math.round((100 * q) / julgadas)}%` : "0%"}
                    </span>
                  </span>
                );
              })}
              {/* As mãos sem veredito aparecem SEPARADAS dos quatro níveis, e não espalhadas
                  neles: contar como erro inventaria acusação, como acerto inventaria mérito. */}
              {r.sem_avaliacao > 0 && (
                <span data-testid="pratica-relatorio-sem-avaliacao"
                      className="inline-flex items-center gap-1.5 rounded border border-dashed border-border px-2 py-1 font-mono text-[10.5px] text-muted-foreground">
                  {t("relatorio.semAvaliacao")} <b className="tabular-nums">{r.sem_avaliacao}</b>
                </span>
              )}
            </div>

            {/* ── os cortes ────────────────────────────────────────────────────────────── */}
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Corte titulo={t("relatorio.porPosicao")} dados={r.por_posicao} />
              <Corte titulo={t("relatorio.porCenario")} dados={r.por_cenario} />
            </div>

            {/* ── a tabela das mãos ────────────────────────────────────────────────────── */}
            <div className="mt-3 overflow-x-auto scrollbar-hud">
              <table className="w-full min-w-[640px] border-collapse font-mono text-[11px]">
                <thead>
                  <tr className="border-b border-border text-left text-[9px] uppercase tracking-widest-2 text-muted-foreground">
                    <th className="py-1.5 pr-2 font-normal">{t("relatorio.col.mao")}</th>
                    <th className="py-1.5 pr-2 font-normal">{t("relatorio.col.spot")}</th>
                    <th className="py-1.5 pr-2 font-normal">{t("relatorio.col.stack")}</th>
                    <th className="py-1.5 pr-2 font-normal">{t("relatorio.col.suaAcao")}</th>
                    <th className="py-1.5 pr-2 font-normal">{t("relatorio.col.gto")}</th>
                    <th className="py-1.5 pr-2 text-right font-normal">{t("relatorio.col.freq")}</th>
                    <th className="py-1.5 pr-2 font-normal">{t("relatorio.col.veredito")}</th>
                    <th className="py-1.5 text-right font-normal">{t("relatorio.col.custo")}</th>
                  </tr>
                </thead>
                <tbody data-testid="pratica-relatorio-tabela">
                  {maos.map((m) => {
                    const nivel = (m.nivel && (NIVEIS as readonly string[]).includes(m.nivel)
                      ? m.nivel : null) as Nivel | null;
                    return (
                      <tr key={m.id} className="border-b border-border/40">
                        <td className="py-1.5 pr-2 font-bold text-foreground">{m.mao}</td>
                        <td className="py-1.5 pr-2 truncate text-muted-foreground">
                          {m.resumo || m.cenario || "—"}
                        </td>
                        <td className="py-1.5 pr-2 tabular-nums text-muted-foreground">
                          {m.stack_bb != null ? `${m.stack_bb}bb` : "—"}
                        </td>
                        <td className="py-1.5 pr-2 uppercase text-foreground">{m.acao}</td>
                        <td className="py-1.5 pr-2 uppercase text-muted-foreground">
                          {m.acao_gto || "—"}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums text-muted-foreground">
                          {m.freq_da_acao != null ? `${Math.round(m.freq_da_acao * 100)}%` : "—"}
                        </td>
                        <td className={cn("py-1.5 pr-2 font-bold",
                                          nivel ? COR_DO_NIVEL[nivel] : "text-muted-foreground/60")}>
                          {nivel
                            ? <>{SIMBOLO_DO_NIVEL[nivel]} {t(`nivel.${nivel}`)}</>
                            : t("relatorio.semAvaliacao")}
                        </td>
                        <td className="py-1.5 text-right tabular-nums text-red-400/90">
                          {m.ev_loss_bb ? `−${Math.abs(m.ev_loss_bb).toFixed(2)}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {proximo && (
              <button onClick={() => void mais()} disabled={carregando}
                      data-testid="pratica-relatorio-mais"
                      className="mt-2 w-full rounded border border-border py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50">
                {carregando ? t("carregando") : t("relatorio.mais")}
              </button>
            )}
          </>
        )}

        {!erro && !r && (
          <div className="p-4 text-center font-mono text-[11px] text-muted-foreground">
            {t("carregando")}
          </div>
        )}
      </div>
    </div>
  );
}
