import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { RangeGrid } from "@/components/replayer/RangeGrid";
import type { RangeSet } from "@/data/ranges";
import type { PositionOpenMatrixResponse, StackBand } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Matriz 13x13 das maos que o jogador ABRIU de um assento, contra o que o solver abriria com
 * as mesmas maos nos mesmos stacks (AY-15 c, sugestao do Rullian). Abre pela celula RFI do
 * Perfil por posicao e herda o assento e a faixa de stack.
 *
 * Duas grades lado a lado, a MESMA `RangeGrid` de /ranges (nada de pintura nova): "Voce" com a
 * fracao em que abriu cada mao, "Solver" com a frequencia da carta. A terceira coluna e a lista
 * das maiores divergencias. Por que aqui e nao um item de menu: a matriz so faz sentido com
 * assento e stack escolhidos, e o perfil ja tem os dois; e a leitura que importa e "o RFI total
 * bate com o solver, a composicao nao", que so aparece ao lado da celula.
 *
 * Layout (dono, 08/09): tres colunas no desktop para a altura do modal ser a de UMA grade; a
 * lista de divergencias rola sozinha quando tem muitas linhas, em vez de esticar o modal; o
 * cabecalho da coluna do solver e curto ("Solver"), o nome longo fica no titulo da grade.
 */
const ROTULO_DA_FAIXA: Record<string, string> = { "40+": "40+ bb", "20-40": "20–40 bb", "<20": "< 20 bb" };

function comoRange(cells: PositionOpenMatrixResponse["cells"], lado: "voce" | "solver", label: string): RangeSet {
  const raise = new Set<string>();
  const frequencies: RangeSet["frequencies"] = {};
  for (const [hand, c] of Object.entries(cells)) {
    const f = lado === "voce" ? c.voce : c.solver;
    if (f == null) continue;
    // na SUA grade o limp aparece como call (azul), separado do fold: limpar AA nao e foldar AA
    frequencies[hand] = lado === "voce" && c.limp ? { raise: f, call: c.limp } : { raise: f };
    if (f > 0.001) raise.add(hand);
  }
  return { raise, label, frequencies };
}

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);

const CABECALHO = "border-b border-border/60 pb-1 font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60";
const CELULA = "border-b border-border/30 py-1";

export function MatrizDeAbertura({ position, stack, dados, erro, posicoes, faixas, onMudar }: {
  position: string; stack?: StackBand | null; dados: PositionOpenMatrixResponse | null; erro: boolean;
  /** assentos da grade (sem a BB) e faixas de stack: os chips do modal trocam os dois sem sair dele (dono, 08/09) */
  posicoes?: string[]; faixas?: StackBand[]; onMudar?: (position: string, stack: StackBand | null) => void;
}) {
  const { t } = useTranslation("dashboard");
  const voce = useMemo(() => (dados ? comoRange(dados.cells, "voce", "voce") : null), [dados]);
  // maos que o jogador nunca recebeu deste assento: apagadas na grade dele (nao e fold)
  const nuncaRecebidas = useMemo(() => new Set(dados ? Object.entries(dados.cells).filter(([, c]) => c.n === 0).map(([h]) => h) : []), [dados]);
  const solver = useMemo(() => (dados ? comoRange(dados.cells, "solver", "solver") : null), [dados]);
  const chip = (ativo: boolean, onClick: (() => void) | undefined, rotulo: string, testid: string) => (
    <button type="button" key={testid} data-testid={testid} aria-pressed={ativo} onClick={onClick} disabled={!onClick}
            className={cn("rounded-md border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider transition-colors",
                          ativo ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground",
                          !onClick && "cursor-default")}>
      {rotulo}
    </button>
  );
  const seletores = (
    <div className="mb-2 flex flex-wrap items-center gap-1.5" data-testid="matriz-seletores">
      {(posicoes && posicoes.length ? posicoes : [position]).map((p) => chip(p === position, onMudar ? () => onMudar(p, stack ?? null) : undefined, p, `matriz-pos-${p}`))}
      <span className="mx-1 h-3 w-px bg-border" />
      {[null, ...(faixas ?? [])].map((f) => chip((stack ?? null) === f, onMudar ? () => onMudar(position, f) : undefined, f ? ROTULO_DA_FAIXA[f] ?? f : t("posProfile.stackAll"), `matriz-stack-${f ?? "todos"}`))}
      {dados && dados.n > 0 && (
        <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{t("posProfile.matrix.opps", { n: dados.n.toLocaleString() })}</span>
      )}
    </div>
  );
  if (erro) return <div>{seletores}<p className="text-[11px] text-muted-foreground">{t("posProfile.detail.error")}</p></div>;
  if (!dados || !voce || !solver) return <div>{seletores}<p className="font-mono text-[10px] text-muted-foreground/60">…</p></div>;
  if (dados.n === 0) return <div>{seletores}<p className="text-[11px] text-muted-foreground">{t("posProfile.detail.empty")}</p></div>;
  return (
    <div className="mt-1" data-testid={`matriz-${position}`}>
      {seletores}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-[1fr_1fr_17rem]">
        <div data-testid="matriz-voce">
          <div className="mb-1.5 flex items-baseline justify-between gap-2">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("posProfile.you")}</span>
            <span className="font-heading text-sm font-bold text-foreground">{t("posProfile.matrix.opened", { pct: dados.voce_pct ?? "—" })}</span>
          </div>
          <RangeGrid range={voce} compacta semDado={nuncaRecebidas} rotuloSemDado={t("posProfile.matrix.neverDealt")} />
        </div>

        <div data-testid="matriz-solver">
          <div className="mb-1.5 flex items-baseline justify-between gap-2">
            <span className="truncate whitespace-nowrap font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("posProfile.matrix.solver")}</span>
            <span className="whitespace-nowrap font-heading text-sm font-bold text-foreground">
              {dados.solver_pct == null ? t("posProfile.matrix.noChart") : t("posProfile.matrix.wouldOpen", { pct: dados.solver_pct })}
              {dados.solver_pct != null && dados.cobertura < 100 && (
                <span className="ml-1.5 font-mono text-[9px] font-normal text-muted-foreground/70">{t("posProfile.matrix.covers", { pct: dados.cobertura })}</span>
              )}
            </span>
          </div>
          <RangeGrid range={solver} compacta />
        </div>

        <div className="min-w-0 overflow-x-hidden rounded-lg border border-border/50 bg-card/40 p-3">
          <div className="mb-1.5 font-mono text-[9px] uppercase tracking-widest text-primary">
            {t("posProfile.matrix.divergences")}
          </div>
          {dados.divergencias.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">{t("posProfile.matrix.noDivergence", { n: dados.minimo_maos, pp: Math.round(dados.divergencia_minima * 100) })}</p>
          ) : (
            // rola so na vertical: as colunas somam menos que a caixa (dono, 08/09: "rolagem horizontal e inaceitavel")
            <div className="max-h-[19rem] overflow-y-auto overflow-x-hidden">
              <div className="grid items-center gap-x-1.5" style={{ gridTemplateColumns: "2.2rem 1.8rem 2.5rem 2.6rem 3.4rem" }} data-testid="matriz-divergencias">
                <span className={CABECALHO}>{t("posProfile.matrix.hand")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.matrix.times")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.you")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.matrix.solverShort")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.matrix.diff")}</span>
                {dados.divergencias.map((d) => (
                  <div key={d.hand} className="contents" data-testid={`divergencia-${d.hand}`}>
                    <span className={`${CELULA} font-mono text-[11px] font-bold text-foreground`}>{d.hand}</span>
                    <span className={`${CELULA} font-mono text-[10px] tabular-nums text-muted-foreground text-right`}>{d.n}</span>
                    <span className={`${CELULA} font-mono text-[11px] tabular-nums text-foreground text-right`}>{pct(d.voce)}</span>
                    <span className={`${CELULA} font-mono text-[11px] tabular-nums text-foreground text-right`}>{pct(d.solver)}</span>
                    <span className={`${CELULA} whitespace-nowrap font-mono text-[11px] font-bold tabular-nums text-right text-red-400`}>
                      {d.delta > 0 ? "+" : ""}{Math.round(d.delta * 100)} pp
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <p className="mt-2 font-mono text-[9px] leading-snug text-muted-foreground/60">
            {t("posProfile.matrix.divergencesNote", { n: dados.minimo_maos, pp: Math.round(dados.divergencia_minima * 100) })}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end gap-3">
        <Link to="/ranges" className="shrink-0 rounded-md border border-primary/40 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/10">
          {t("posProfile.matrix.study")}
        </Link>
      </div>
    </div>
  );
}
