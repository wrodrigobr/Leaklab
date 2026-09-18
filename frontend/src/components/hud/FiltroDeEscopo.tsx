import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { SlidersHorizontal, X } from "lucide-react";

import { TETO_DE_MAOS_DO_ESCOPO, type EscopoDoDashboard } from "@/lib/escopo";
import { escopoValido, pisoDaFaixa } from "@/lib/escopoGuardado";
import { cn } from "@/lib/utils";

/**
 * O filtro de ESCOPO do dashboard: um ícone, um popup, três dimensões.
 *
 * ── O pedido (17/09) ──────────────────────────────────────────────────────────────────────────
 *
 * "pensei em ao invés dos botões dos ultimos torneios, podiamos criar um icone de filtro, e abrir
 * um popup para o jogador escolher como quer filtrar 'ultimos torneios, ultimas x mãos (com limite
 * de 30 mil mãos), por data de inicio e fim (com limite de x meses)'...e ao selecionar, aí ficaria
 * exposto neste bloco verde a opção do filtro do usuario...e devemos manter sessao, sempre usar a
 * ultima escolha dele."
 *
 * ── Por que o popup, e não mais botões ────────────────────────────────────────────────────────
 *
 * Eram quatro botões (20, 50, 100, histórico) e três dimensões não cabem em botões: viraria uma
 * fileira de doze. O ícone devolve a largura para a FRASE, que é quem diz o escopo -- e a frase é
 * o conserto de 05/09 ("este filtro esta muito escondido, temos que pensar uma forma de ficar mais
 * evidente"), que não pode regredir para caber no controle.
 */

type Aba = EscopoDoDashboard["tipo"];

/** As opções de "últimos N torneios". `0` é histórico, e fica por último porque é o mais largo. */
const TORNEIOS = [20, 50, 100, 0] as const;

/** As opções de mãos. O teto vem do servidor e é o mesmo dos dois lados. */
const MAOS = [1000, 5000, 10000, TETO_DE_MAOS_DO_ESCOPO] as const;

/** A aparencia dos dois campos de data. So a APARENCIA e comum: os limites sao diferentes. */
const CAMPO_DE_DATA =
  "w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground outline-none focus:border-primary";

/** O escopo em UMA frase, que é o que a faixa verde mostra. Exportada para ter teste próprio. */
export function fraseDoEscopo(
  escopo: EscopoDoDashboard,
  t: (k: string, o?: Record<string, unknown>) => string,
  torneiosNoTotal?: number,
): string {
  if (escopo.tipo === "maos") {
    return t("volumeFilter.scopeMaos", { maos: escopo.n.toLocaleString() });
  }
  if (escopo.tipo === "periodo") {
    return t("volumeFilter.scopePeriodo", { de: escopo.de, ate: escopo.ate });
  }
  // `0` é histórico genuíno, e a frase declara o TAMANHO do acervo -- sem isso "histórico" não
  // diz sobre quantos torneios o jogador está olhando.
  return escopo.n
    ? t("volumeFilter.scopeLastN", { n: escopo.n })
    : t("volumeFilter.scopeAll", { tourneys: (torneiosNoTotal ?? 0).toLocaleString() });
}

/**
 * Uma opcao do popup.
 *
 * Declarada FORA do componente de proposito: uma funcao de componente no corpo de outro tem
 * identidade nova a cada render, e o React desmonta e remonta a arvore em vez de atualizar. Foi o
 * defeito que o dono relatou hoje no formulario de resultado manual ("a cada digitação, ele perde
 * o foco"), e este popup tem campo de data -- o mesmo erro aqui apagaria o seletor a cada tecla.
 */
function Opcao({ ativo, onClick, children, testid }: {
  ativo: boolean; onClick: () => void; children: React.ReactNode; testid: string;
}) {
  return (
    <button type="button" onClick={onClick} data-testid={testid} aria-pressed={ativo}
            className={cn("rounded border px-2 py-1.5 font-mono text-[11px] tabular-nums transition-colors",
                          ativo ? "border-primary bg-primary/15 text-primary"
                                : "border-border text-muted-foreground hover:text-foreground")}>
      {children}
    </button>
  );
}

export function FiltroDeEscopo({ escopo, onEscopo }: {
  escopo: EscopoDoDashboard;
  onEscopo: (e: EscopoDoDashboard) => void;
}) {
  const { t } = useTranslation("dashboard");
  const [aberto, setAberto] = useState(false);
  const [aba, setAba] = useState<Aba>(escopo.tipo);
  const hoje = new Date().toISOString().slice(0, 10);
  const [de, setDe] = useState(escopo.tipo === "periodo" ? escopo.de : pisoDaFaixa());
  const [ate, setAte] = useState(escopo.tipo === "periodo" ? escopo.ate : hoje);

  // Reabrir mostra o que está VALENDO, e não o que ele mexeu e abandonou da última vez: o popup
  // é a foto do estado, senão ele "lembra" uma escolha que a tela não está usando.
  useEffect(() => {
    if (!aberto) return;
    setAba(escopo.tipo);
    if (escopo.tipo === "periodo") { setDe(escopo.de); setAte(escopo.ate); }
  }, [aberto, escopo]);

  const escolher = (e: EscopoDoDashboard) => { onEscopo(e); setAberto(false); };

  const aplicarFaixa = () => {
    const limpo = escopoValido({ tipo: "periodo", de, ate });
    if (limpo) escolher(limpo);
  };

  return (
    <>
      {/* `titulo` e nao `label` no rotulo acessivel: a chave `label` do grupo antigo diz
          "Analisando", e um leitor de tela anunciaria o botao de filtro com o nome errado. */}
      <button type="button" onClick={() => setAberto(true)} data-testid="abrir-filtro-escopo"
              title={t("volumeFilter.titulo")} aria-label={t("volumeFilter.titulo")}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-background/50 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary">
        <SlidersHorizontal className="size-3.5" aria-hidden />
        <span className="hidden sm:inline">{t("volumeFilter.ajustar")}</span>
      </button>

      {aberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4"
             data-testid="filtro-escopo">
          <div className="w-full max-w-md rounded-lg border border-border bg-hud-surface p-4 shadow-xl">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-widest-2 text-primary">
                  {t("volumeFilter.titulo")}
                </div>
                <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                  {t("volumeFilter.ajuda")}
                </p>
              </div>
              <button onClick={() => setAberto(false)} data-testid="fechar-filtro-escopo"
                      aria-label={t("volumeFilter.fechar")}
                      className="shrink-0 text-muted-foreground transition-colors hover:text-foreground">
                <X className="size-4" />
              </button>
            </div>

            {/* as tres dimensoes como abas: elas sao EXCLUSIVAS, e o jogador escolhe UMA */}
            <div role="tablist" className="mb-3 flex gap-px overflow-hidden rounded-md bg-background/50 ring-1 ring-border">
              {(["torneios", "maos", "periodo"] as Aba[]).map((k) => (
                <button key={k} role="tab" type="button" onClick={() => setAba(k)}
                        data-testid={`aba-${k}`} aria-selected={aba === k}
                        className={cn("flex-1 px-2 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
                                      aba === k ? "bg-primary font-bold text-primary-foreground"
                                                : "text-muted-foreground hover:text-foreground")}>
                  {t(`volumeFilter.aba.${k}`)}
                </button>
              ))}
            </div>

            {aba === "torneios" && (
              <div className="grid grid-cols-4 gap-1.5" data-testid="opcoes-torneios">
                {TORNEIOS.map((n) => (
                  <Opcao key={n} testid={`escopo-torneios-${n}`}
                         ativo={escopo.tipo === "torneios" && escopo.n === n}
                         onClick={() => escolher({ tipo: "torneios", n })}>
                    {n === 0 ? t("volumeFilter.all") : n}
                  </Opcao>
                ))}
              </div>
            )}

            {aba === "maos" && (
              <div className="grid grid-cols-4 gap-1.5" data-testid="opcoes-maos">
                {MAOS.map((n) => (
                  <Opcao key={n} testid={`escopo-maos-${n}`}
                         ativo={escopo.tipo === "maos" && escopo.n === n}
                         onClick={() => escolher({ tipo: "maos", n })}>
                    {n.toLocaleString()}
                  </Opcao>
                ))}
              </div>
            )}

            {aba === "periodo" && (
              <div className="space-y-2" data-testid="opcoes-periodo">
                {/* ── Os limites são ACOPLADOS, e por isso não saem de um laço (18/09) ─────
                    O dono: "as datas do filtro 'de' e 'até' estão invertidas....o 'de' tem que
                    permitir selecionar o passado....o até, no máximo o dia de hoje".

                    A causa era o meu atalho: eu gerava os dois campos num `map`, e o laço os
                    fazia IDÊNTICOS (`min` do piso e `max` de hoje nos dois). As duas pontas de
                    uma faixa não são simétricas -- o começo é limitado pelo FIM, e o fim pelo
                    hoje. Com limites iguais dava para escolher `de` depois do `ate`, e a faixa
                    invertida só era corrigida DEPOIS, no validador, calada.

                    Agora o seletor não oferece a inversão, em vez de aceitar e consertar. */}
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="mb-1 block font-mono text-[9.5px] uppercase tracking-widest-2 text-muted-foreground">
                      {t("volumeFilter.de")}
                    </span>
                    <input type="date" value={de} min={pisoDaFaixa()} max={ate || hoje}
                           data-testid="escopo-data-de"
                           onChange={(ev) => setDe(ev.target.value)}
                           className={CAMPO_DE_DATA} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block font-mono text-[9.5px] uppercase tracking-widest-2 text-muted-foreground">
                      {t("volumeFilter.ate")}
                    </span>
                    <input type="date" value={ate} min={de || pisoDaFaixa()} max={hoje}
                           data-testid="escopo-data-ate"
                           onChange={(ev) => setAte(ev.target.value)}
                           className={CAMPO_DE_DATA} />
                  </label>
                </div>
                <button type="button" onClick={aplicarFaixa} data-testid="escopo-aplicar-periodo"
                        className="w-full rounded bg-primary px-2 py-2 font-mono text-[10.5px] font-bold uppercase tracking-widest-2 text-background transition-colors hover:bg-primary-glow">
                  {t("volumeFilter.aplicar")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
