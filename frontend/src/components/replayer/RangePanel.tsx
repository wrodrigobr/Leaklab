import { useState, useEffect } from "react";
import { LayoutGrid, X, Loader2, CheckCircle2, XCircle, AlertTriangle, Info } from "lucide-react";
import { GtoMixedBadge } from "./GtoMixedBadge";
import { RangeGrid } from "./RangeGrid";
import {
  heroHand, RANGES, normalizePosition, PUSH_FOLD, getPushFoldBucket,
  Position, RangeType, POSITIONS, CORE_TAB_POSITIONS, RANGE_TYPES, RangeSet,
} from "@/data/ranges";
import { ACTION_COLORS } from "@/lib/actionColors";
import { mostraQualidadeEstatica } from "@/lib/cardLogic";
import { ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Trans, useTranslation } from "react-i18next";
import { computeEffectiveGtoLabel } from "@/lib/gtoUtils";

function authFetch(path: string): Promise<Response> {
  const t = sessionStorage.getItem("ll_token");
  const base = import.meta.env.VITE_API_URL ?? "";
  return fetch(`${base}${path}`, {
    headers: t ? { Authorization: `Bearer ${t}` } : {},
  });
}

interface Props {
  step: ReplayStep;
  hero: string;
  heroCards: string[];
  onClose: () => void;
  onHeaderMouseDown?: (e: React.MouseEvent<HTMLDivElement>) => void;
  /* Condições que a matriz deve MOSTRAR, quando quem abre o painel não quer as da mão.
     Nasceu de um relato: a pergunta do treino falava da range do BTN e a tabela abria no SB — a
     posição do spot. O jogador conferiu a mão citada, viu comportamento diferente e concluiu que
     o produto tinha errado. A pergunta estava certa; a referência é que não respondia a pergunta
     feita. Ausente = comporta-se como sempre (as condições da mão). */
  posicaoInicial?: string | null;
  stackInicial?: number | null;
}

// Frequência por ação (estilo solver — soma 1.0)
interface HandFreqApi {
  raise?: number; call?: number; allin?: number; fold?: number;
}

// Grade de ação por mão (mesma estrutura p/ vs_rfi, vs_3bet e squeeze).
interface ActionGrid {
  hands: string[];
  raise3bet: string[];
  call: string[];
  allin?: string[];
  pct_play: number;
  call_pct?: number;
  raise_pct?: number;
  allin_pct?: number;
  acoes?: string[];
  frequencies?: Record<string, HandFreqApi>;
}
export interface PreflopRangesResp {
  position: string;
  stack_bb: number;
  stack_bucket: string;
  rfi: { hands: string[]; pct: number; raise_pct?: number; allin_pct?: number; frequencies?: Record<string, HandFreqApi> } | null;
  vs_rfi: Record<string, ActionGrid>;
  vs_3bet: Record<string, ActionGrid> | null;     // keyed por 3bettor
  squeeze: Record<string, ActionGrid> | null;     // keyed por opener
}

function fmtAction(a: string): string {
  const s = (a ?? "").toLowerCase();
  if (s === "jam" || s === "allin" || s === "all-in") return "Shove";
  if (s === "fold") return "Fold";
  if (s === "call") return "Call";
  if (s === "raise") return "Raise";
  if (s === "bet")  return "Bet";
  if (s === "check") return "Check";
  return a;
}

const SCENARIO_TO_TYPE: Record<string, RangeType> = {
  rfi: 'open',
  vs_rfi: 'call',
  vs_3bet: '3bet',
  faces_squeeze: 'call',   // cold/blind defende vs squeeze → range de defesa
  squeeze: '3bet',         // hero é o squeezador (3bet sobre open+caller)
};

// Rótulos de cenário/qualidade: a CHAVE i18n mora aqui, a tradução no locale (os termos de
// poker — RFI, Open, 3-Bet, Squeeze — atravessam os 3 idiomas por regra do projeto).
const SCENARIO_KEY: Record<string, string> = {
  rfi: 'cenario.rfi',
  vs_rfi: 'cenario.vsRfi',
  vs_3bet: 'cenario.vs3bet',
  vs_shove_fallback: 'cenario.vsShove',
  faces_squeeze: 'cenario.facesSqueeze',
  squeeze: 'cenario.squeeze',
};

const QUALITY_META: Record<string, { key: string; color: string; icon: typeof CheckCircle2 }> = {
  correct:    { key: 'qualidade.correto',   color: 'text-emerald-400', icon: CheckCircle2 },
  acceptable: { key: 'qualidade.aceitavel', color: 'text-sky-400',     icon: Info          },
  leak:       { key: 'qualidade.leak',      color: 'text-amber-400',   icon: AlertTriangle },
  major_leak: { key: 'qualidade.leakGrave', color: 'text-red-400',     icon: XCircle       },
  unknown:    { key: 'qualidade.semDados',  color: 'text-muted-foreground', icon: Info     },
};

// Exportada em 27/08 para a pagina /ranges reusar a MESMA construcao. Duplicar aqui seria a
// segunda fonte para o mesmo fato -- o defeito que este projeto passa a semana consertando.
export function buildRangeFromApi(resp: PreflopRangesResp, type: RangeType, openerPos?: string, scenario?: string): RangeSet | null {
  if (type === 'open') {
    if (!resp.rfi) return null;
    return {
      label: `Open ${resp.position} (${resp.stack_bucket})`,
      raise: new Set(resp.rfi.hands),
      frequencies: resp.rfi.frequencies,
    };
  }
  if (type === '3bet') {
    // squeeze (hero squeeza) usa resp.squeeze[opener]; vs_3bet usa resp.vs_3bet[3bettor].
    // O vilão (openerPos = gto.vs_position) é a chave em ambos.
    const isSqueeze = scenario === 'squeeze';
    const src = isSqueeze ? resp.squeeze : resp.vs_3bet;
    if (!src) return null;
    const villains = Object.keys(src);
    if (!villains.length) return null;
    const key = (openerPos && src[openerPos]) ? openerPos : villains[0];
    const g = src[key];
    return {
      label: `${isSqueeze ? 'Squeeze vs' : 'vs'} ${key} ${isSqueeze ? 'open' : '3-bet'} · ${resp.position} (${resp.stack_bucket})`,
      raise: new Set(g.raise3bet),
      call:  new Set(g.call),
      allin: new Set(g.allin ?? []),
      frequencies: g.frequencies,
    };
  }
  if (type === 'call') {
    const openers = Object.keys(resp.vs_rfi);
    if (!openers.length) return null;
    const resolvedKey = openerPos
      ? (resp.vs_rfi[openerPos] ? openerPos
        : resp.vs_rfi[openerPos + '_open'] ? openerPos + '_open'
        : null)
      : null;
    const key = resolvedKey ?? openers[0];
    const def = resp.vs_rfi[key];
    return {
      label: `vs ${key.replace('_open', '')} open · ${resp.position} (${resp.stack_bucket})`,
      raise: new Set(def.raise3bet ?? []),
      call:  new Set(def.call ?? []),
      allin: new Set(def.allin ?? []),
      frequencies: def.frequencies,
    };
  }
  return null;
}

export function RangePanel({ step, hero, heroCards, onClose, onHeaderMouseDown,
                             posicaoInicial, stackInicial }: Props) {
  const { t } = useTranslation("replayer");
  const heroSeat    = Object.entries(step.seats ?? {}).find(([, s]) => s.player === hero);
  const detectedPos = heroSeat ? normalizePosition(heroSeat[1].pos) : null;
  const gto         = step.preflop_gto;
  const posPedida   = posicaoInicial ? normalizePosition(posicaoInicial) : null;
  /* A posição em que o veredito FOI calculado — fonte única. O nome do assento é outro dialeto:
     numa mesa curta o backend gradeia por jogadores atrás (assento "UTG+1" de 7-max vira LJ), e
     re-derivar esse mapa aqui seria mais uma cópia da regra. Caso real (19/08): o assento UTG+2
     era achatado para LJ e a grade contradizia o veredito na mesma tela (K6s). */
  const gtoPos      = gto?.position ? normalizePosition(gto.position) : null;

  const [pos,  setPos]  = useState<Position>(posPedida ?? gtoPos ?? detectedPos ?? 'BTN');

  const [apiData, setApiData] = useState<PreflopRangesResp | null>(null);
  const [loading, setLoading] = useState(false);

  // hero_stack_bb só existe em steps de decisão do hero; fallback via seats + bb
  const heroSeatStack = heroSeat ? heroSeat[1].stack : null;
  const stackBb = stackInicial
    ?? step.hero_stack_bb
    ?? (heroSeatStack && step.bb ? Math.round(heroSeatStack / step.bb) : null)
    ?? 30;
  const openerPos  = gto?.vs_position ?? undefined;
  const pushBucket = getPushFoldBucket(stackBb);
  const isPushZone = pushBucket !== null;

  // Default: segue o cenário (open pra RFI, call pra vs_RFI, 3bet pra vs 3-bet).
  // Aba 'shove' (Nash simplificado) só é default quando NÃO temos GW v3 — caso contrário
  // o range de open/call já mostra raise+allin com freqs reais (mais informativo).
  const defaultType: RangeType =
    (gto?.scenario ? (SCENARIO_TO_TYPE[gto.scenario] ?? 'open')
      : (Object.entries(step.bets ?? {}).some(([seat, bet]) =>
          step.seats?.[seat]?.player !== hero && bet > (step.bb ?? 0))
        ? 'call' : 'open'));

  const [type, setType] = useState<RangeType>(posPedida ? 'open' : defaultType);

  /* A matriz TROCA quando as condições pedidas mudam — é o pedido explícito: enquanto a pergunta
     está em cena o painel mostra a range DELA; ao revelar as cartas do herói ele volta para a da
     mão. Sem este efeito o `useState` congelaria o valor da primeira montagem, e um painel deixado
     aberto seguiria mostrando a range da pergunta depois que ela saiu da tela — que é a mesma
     confusão que o conserto existe para acabar, só que ao contrário.
     Trocar de aba à mão continua valendo: as dependências só mudam quando a FONTE muda. */
  useEffect(() => {
    setPos(posPedida ?? gtoPos ?? detectedPos ?? 'BTN');
    // Toda pergunta de range do treino é sobre a range de ABERTURA ("abre", "range de abertura",
    // "às vezes entrando"). Abrir na aba de call mostraria outra coisa com o rótulo certo.
    setType(posPedida ? 'open' : defaultType);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [posPedida, gtoPos, detectedPos]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setApiData(null);
    // encodeURIComponent: o '+' de UTG+1/UTG+2 cru na query decodifica como ESPAÇO no backend.
    authFetch(`/preflop-ranges?position=${encodeURIComponent(pos)}&stack_bb=${stackBb}`)
      .then(r => r.json())
      .then((d: PreflopRangesResp) => { if (!cancelled) setApiData(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pos, stackBb]);

  const staticRange    = RANGES[pos];
  const nashRange      = pushBucket ? PUSH_FOLD[pushBucket]?.[pos] : null;

  // UTG+1/UTG+2 só viram aba quando são a posição da mão/veredito/pergunta — mas aí PRECISAM
  // existir, senão a grade responde outra pergunta. Âncoras (e não só `pos`): a aba não pode
  // sumir da régua quando o usuário navega para outra e quer voltar.
  const tabPositions = POSITIONS.filter(p =>
    CORE_TAB_POSITIONS.includes(p) || p === pos || p === gtoPos || p === posPedida || p === detectedPos);

  const availableTypes = RANGE_TYPES.filter(t => {
    // Aba shove (Nash simplificado) só faz sentido sem GW v3 — o range de open já tem
    // raise+allin com freqs precisas. Esconde quando apiData.rfi existe.
    if (t.id === 'shove') return isPushZone && !!nashRange && !apiData?.rfi;
    if (apiData) {
      if (t.id === 'open')  return !!apiData.rfi;
      if (t.id === '3bet') {
        // aba '3bet' serve vs_3bet E squeeze — fonte depende do cenário da decisão
        const src = gto?.scenario === 'squeeze' ? apiData.squeeze : apiData.vs_3bet;
        return !!(src && Object.keys(src).length);
      }
      if (t.id === 'call')  return Object.keys(apiData.vs_rfi).length > 0;
    }
    return staticRange?.[t.id] !== undefined;
  });

  const effectiveType: RangeType = availableTypes.some(t => t.id === type)
    ? type : (availableTypes[0]?.id ?? 'open');

  const displayRange: RangeSet | null | undefined = effectiveType === 'shove'
    ? nashRange
    : (apiData ? buildRangeFromApi(apiData, effectiveType, openerPos, gto?.scenario) : staticRange?.[effectiveType]);

  const hand = heroHand(heroCards);

  // ── MESA CURTA: a grade é de MESA CHEIA e não sabe quantos jogadores há na mão ──────────
  //
  // Varredura de contradição (20/08, scripts/varredura_contradicao_grade.py): das 3.149
  // combinações (posição, stack, mão) do acervo, 235 divergem entre o VEREDITO e a GRADE —
  // e a ablação por tamanho de mesa explica: **51,5% em heads-up** contra 4-6% em mesa
  // cheia. Não é bug de lookup: as ranges do GW são 9-max, e numa mesa de 3 o "UTG" é outra
  // posição efetiva. O veredito conhece a mesa real; a grade, não.
  //
  // Então a grade DECLARA a premissa em vez de fingir que responde — a mesma regra que já
  // vale no resto do produto: fonte que não sabe, diz que não sabe. Não escondemos a grade
  // (ela segue útil como referência de mesa cheia), mas o aviso tira a contradição.
  const vivosNaMao = (() => {
    const total = Object.keys(step.seats ?? {}).length;
    if (!total) return null;
    const foldados = new Set(step.folded ?? []);
    const vivos = Object.values(step.seats ?? {})
      .filter((s) => s?.player && !foldados.has(s.player)).length;
    // No preflop ninguém foldou ainda no início: o que vale é quem foi DISTRIBUÍDO.
    return Math.max(vivos, 2) <= total ? Math.max(vivos, 2) : total;
  })();
  const mesaCurta = vivosNaMao != null && vivosNaMao < 6;

  // Show GTO context when data is available — detectedPos may be null for positions
  // not yet in the static list (e.g. LJ before the fix), so we show it regardless
  const showGtoCtx = gto?.available ?? false;

  // Solver overrides static ranges when available — same logic as effectiveGtoLabel in Replayer.tsx
  const solverStratSorted = step.gto_strategy
    ? [...step.gto_strategy].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0))
    : [];
  const effectiveGtoLabel = computeEffectiveGtoLabel(solverStratSorted, step.gto_label, step.action);
  // `mostraQualidadeEstatica` decide: a qualidade crua da carta não pode dizer "major leak" ao
  // lado de um veredito que diz que não é erro. O guarda antigo ancorava só no rótulo do solver
  // e não cobria `gto_critical` — que era 25 de 25 dos casos medidos.
  const mostraQualidade = mostraQualidadeEstatica({
    actionQuality: gto?.action_quality, gtoLabel: effectiveGtoLabel, isError: step.is_error,
    podeFalarComoGto: step.pode_falar_como_gto,
  });

  const quality = showGtoCtx && mostraQualidade
    ? QUALITY_META[gto!.action_quality ?? 'unknown'] : null;
  const QIcon   = quality?.icon ?? Info;

  return (
    <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      {/* Header */}
      <div
        className={cn("flex items-center justify-between", onHeaderMouseDown && "cursor-grab active:cursor-grabbing select-none")}
        onMouseDown={onHeaderMouseDown}
      >
        <div className="flex items-center gap-2">
          <LayoutGrid className="size-3.5 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-foreground">
            Range Reference
          </span>
          {hand && <span className="font-mono text-[10px] text-primary font-bold">· {hand}</span>}
          {/* O bucket sozinho ("20bb") ao lado de uma análise que fala 24bb parecia contradição —
              o arredondamento existe, então ele é ROTULADO em vez de escondido. */}
          {apiData && (
            <span className="font-mono text-[8px] text-emerald-400/60">
              {`${stackBb.toFixed(0)}bb` === apiData.stack_bucket
                ? apiData.stack_bucket
                : `${stackBb.toFixed(0)}bb (bucket ${apiData.stack_bucket})`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="size-3 text-muted-foreground animate-spin" />}
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors" aria-label={t("rangePanel.fechar")}>
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {/* MESA CURTA: a premissa da grade, declarada. Medido: em heads-up 51,5% das mãos do
          acervo divergem entre veredito e grade — não porque o lookup erra, mas porque a
          tabela é de mesa cheia. Aqui ela avisa em vez de contradizer o card ao lado. */}
      {mesaCurta && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/[0.07] px-3 py-2">
          <Info className="mt-0.5 size-3.5 shrink-0 text-amber-400" aria-hidden />
          <p className="text-[11px] leading-snug text-amber-200/90">
            <span className="font-bold">
              {vivosNaMao === 2 ? t("rangePanel.mesa.hu") : t("rangePanel.mesa.curta", { n: vivosNaMao })}
            </span>{" "}
            {t("rangePanel.mesa.aviso")}
            {vivosNaMao === 2 ? ` ${t("rangePanel.mesa.avisoHu")}` : ""}
          </p>
        </div>
      )}

      {/* GTO context banner */}
      {showGtoCtx && gto && (
        <div className={cn(
          "rounded-lg border px-3 py-2 space-y-1.5",
          !mostraQualidade
            ? "border-border/40 bg-muted/10"
            : gto.in_range ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
        )}>
          {/* Scenario — em PF zone renomear "Raise First In" para "Push/Fold" */}
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide">
            {t("rangePanel.cenarioLabel")}: {
              isPushZone && gto.scenario === 'rfi'
                ? `Push/Fold (RFI · ${stackBb.toFixed(0)}bb)`
                : isPushZone && gto.scenario === 'vs_rfi'
                ? `Push/Fold (Reshove vs Open · ${stackBb.toFixed(0)}bb)`
                : (SCENARIO_KEY[gto.scenario] ? t(`rangePanel.${SCENARIO_KEY[gto.scenario]}`) : gto.scenario)
            }
          </p>

          {/* Solver override notice */}
          {!mostraQualidade ? (
            <div className="flex items-center flex-wrap gap-2">
              <p className="font-mono text-[9px] text-muted-foreground/60 italic">
                {t("rangePanel.solverSubstitui")}
              </p>
              {(effectiveGtoLabel === 'gto_mixed' || effectiveGtoLabel === 'gto_minor_deviation') && (
                <GtoMixedBadge label={effectiveGtoLabel} size="xs" />
              )}
            </div>
          ) : (
            <>
              {/* In-range status */}
              <div className="flex items-center gap-1.5">
                {gto.in_range
                  ? <CheckCircle2 className="size-3 text-emerald-400 shrink-0" />
                  : <XCircle     className="size-3 text-amber-400 shrink-0" />}
                <span className={cn("font-mono text-[10px] font-bold", gto.in_range ? "text-emerald-400" : "text-amber-400")}>
                  {hand} {gto.in_range ? t("rangePanel.noRange") : t("rangePanel.foraRange")}
                </span>
              </div>

              {/* Quality + recommended */}
              <div className="flex items-center gap-2 flex-wrap">
                {quality && (
                  <div className={cn("flex items-center gap-1", quality.color)}>
                    <QIcon className="size-3 shrink-0" />
                    <span className="font-mono text-[9px]">{t(`rangePanel.${quality.key}`)}</span>
                  </div>
                )}
                {gto.recommended_actions.length > 0 && (
                  <span className="font-mono text-[9px] text-muted-foreground">
                    GTO: <span className="text-primary font-bold">{gto.recommended_actions.map(fmtAction).join(' / ')}</span>
                  </span>
                )}
                {gto.range_pct > 0 && (
                  <span className="font-mono text-[9px] text-muted-foreground">
                    {t("rangePanel.rangeTop")} <span className="text-foreground">{(gto.range_pct * 100).toFixed(0)}%</span>
                  </span>
                )}
              </div>

              {/* % de ação DA MÃO DO JOGADOR (não do range agregado). O jogador
                  tem cartas específicas: a análise é sobre a mão dele. Fonte:
                  gto.hand_freq (None = fold puro 100%). */}
              {(() => {
                const hf = gto.hand_freq;
                // Sem carta GTO para o spot, a barra NAO e desenhada. Antes, `hand_freq`
                // ausente caia no ramo "fold puro 100%" — a tela afirmava "Fold 100%" onde o
                // produto nao tem resposta, e em 4 de 12 casos auditados isso contradizia o
                // veredito exibido ao lado. Nao ter carta e um ESTADO, nao uma estrategia.
                const semCarta = gto.available === false
                  || !hf || Object.keys(hf).length === 0;
                if (semCarta) {
                  return (
                    <div className="rounded-md border border-dashed border-border/60 bg-background/30 px-2.5 py-1.5">
                      <div className="font-mono text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
                        {t("rangePanel.semCarta")}
                      </div>
                    </div>
                  );
                }
                const raise = hf?.raise ?? 0, call = hf?.call ?? 0, allin = hf?.allin ?? 0;
                const fold = hf.fold ?? Math.max(0, 1 - raise - call - allin);
                const segs = [
                  { k: "Raise",  v: raise, c: ACTION_COLORS.raise },
                  { k: "Call",   v: call,  c: ACTION_COLORS.call },
                  { k: "All-in", v: allin, c: ACTION_COLORS.allin },
                  { k: "Fold",   v: fold,  c: ACTION_COLORS.fold },
                ].filter(s => s.v > 0.001);
                const total = segs.reduce((a, s) => a + s.v, 0) || 1;
                return (
                  <div className="space-y-1 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5">
                    <div className="font-mono text-[9px] font-semibold uppercase tracking-wide text-foreground/70">
                      {t("rangePanel.estrategiaDaMao")} · {hand}
                    </div>
                    <div className="flex h-3 w-full overflow-hidden rounded-sm ring-1 ring-border/40">
                      {segs.map(s => (
                        <div key={s.k} style={{ width: `${(s.v / total) * 100}%`, background: s.c }}
                             title={`${s.k} ${(s.v * 100).toFixed(0)}%`} />
                      ))}
                    </div>
                    <div className="flex gap-2.5 flex-wrap font-mono text-[9px] text-muted-foreground">
                      {segs.map(s => (
                        <span key={s.k} className="flex items-center gap-1">
                          <span className="inline-block size-2 rounded-[1px]" style={{ background: s.c }} />
                          {s.k} <span className="text-foreground font-bold">{(s.v * 100).toFixed(0)}%</span>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}
              {gto.reasoning && (
                <p className="font-mono text-[9px] text-muted-foreground/70 leading-relaxed">
                  {gto.reasoning}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* Push/Fold zone banner — só mostra quando NÃO há dados GW v3 disponíveis
          (Nash simplificado faz sentido em 4-6bb fallback). GW v3 cobre 10bb+ com
          freqs reais incluindo raise sized, banner ficaria contraditório. */}
      {isPushZone && effectiveType === 'shove' && !apiData?.rfi && (
        <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 px-3 py-2 space-y-1">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[9px] font-bold uppercase tracking-wide text-violet-400">
              Push/Fold Zone · {stackBb.toFixed(0)}bb (Nash simplificado)
            </span>
          </div>
          <p className="font-mono text-[9px] text-muted-foreground leading-relaxed">
            {t("rangePanel.semSolverBucket")}
          </p>
          {hand && nashRange && (
            <p className={cn(
              "font-mono text-[10px] font-bold",
              (nashRange.raise.has(hand) || nashRange.call?.has(hand)) ? "text-emerald-400" : "text-amber-400"
            )}>
              {hand}: {(nashRange.raise.has(hand) || nashRange.call?.has(hand)) ? `✓ ${t("rangePanel.noRangeCurto")}` : `✗ ${t("rangePanel.foraRangeCurto")}`}
            </p>
          )}
        </div>
      )}

      {/* Position selector */}
      <div className="grid gap-px rounded-md overflow-hidden ring-1 ring-border"
        style={{ gridTemplateColumns: `repeat(${tabPositions.length}, minmax(0, 1fr))` }}>
        {tabPositions.map(p => (
          <button key={p} onClick={() => setPos(p)}
            className={cn(
              'py-1 font-mono text-[9px] font-bold uppercase transition-colors',
              pos === p ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/30',
            )}>
            {p}
          </button>
        ))}
      </div>

      {/* Range type selector */}
      <div className="grid gap-px rounded-md overflow-hidden ring-1 ring-border"
        style={{ gridTemplateColumns: `repeat(${availableTypes.length}, minmax(0, 1fr))` }}>
        {availableTypes.map(t => (
          <button key={t.id} onClick={() => setType(t.id)}
            className={cn(
              'py-1 font-mono text-[9px] font-bold uppercase transition-colors',
              effectiveType === t.id ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/30',
            )}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Aviso quando a aba ativa mostra OUTRA POSIÇÃO que não a do veredito — navegar pelas
          abas é legítimo, mas a grade e o banner na mesma tela não podem parecer se contradizer
          sem rótulo (caso K6s: veredito UTG+2, grade LJ). */}
      {showGtoCtx && gtoPos && pos !== gtoPos && (
        <div className="rounded-md border border-amber-500/25 bg-amber-500/5 px-3 py-1.5">
          <p className="font-mono text-[9px] text-amber-400/80 leading-snug">
            <Trans i18nKey="rangePanel.abaDivergente" ns="replayer"
              values={{ pos, gtoPos }}
              components={{ b: <strong className="text-amber-400" /> }} />
          </p>
        </div>
      )}

      {/* Aviso quando a aba ativa não corresponde ao cenário da decisão. Só aponta
          "está na aba X" quando essa aba REALMENTE existe, senão dizia pra clicar
          numa aba inexistente (a grade vs 3-bet ainda não é exposta como aba). */}
      {(() => {
        const targetType = gto?.scenario ? SCENARIO_TO_TYPE[gto.scenario] : undefined;
        if (!showGtoCtx || !targetType || effectiveType === targetType) return null;
        const refLabel = t(`rangePanel.ref.${effectiveType === 'open' ? 'open' : effectiveType === '3bet' ? 'tresBet' : 'defesa'}`);
        const decLabel = t(`rangePanel.dec.${targetType === 'call' ? 'defesa' : targetType === '3bet' ? 'respTresBet' : 'abertura'}`);
        const targetTab = availableTypes.find(t => t.id === targetType);
        return (
          <div className="rounded-md border border-amber-500/25 bg-amber-500/5 px-3 py-1.5">
            <p className="font-mono text-[9px] text-amber-400/80 leading-snug">
              {targetTab ? (
                <Trans i18nKey="rangePanel.cenarioOutraAba" ns="replayer"
                  values={{ refLabel, decLabel, aba: targetTab.label }}
                  components={{ b: <strong className="text-amber-400" /> }} />
              ) : (
                <>{t("rangePanel.cenarioSemAba", { refLabel, decLabel })}</>
              )}
            </p>
          </div>
        );
      })()}

      {/* Range grid — sempre interativo (tooltips por célula). */}
      {displayRange ? (
        <RangeGrid range={displayRange} heroHand={hand} />
      ) : loading ? (
        <p className="text-xs text-muted-foreground text-center py-4 animate-pulse">{t("rangePanel.carregando")}</p>
      ) : (
        <p className="text-xs text-muted-foreground text-center py-4">{t("rangePanel.semRange")}</p>
      )}

      {/* Pro notes — suprimidas quando solver contradiz ranges estaticos */}
      {showGtoCtx && mostraQualidade && gto?.pro_notes && gto.pro_notes.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 px-3 py-2 space-y-1">
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide mb-1.5">{t("rangePanel.analiseGto")}</p>
          {gto.pro_notes.map((note, i) => (
            <p key={i} className="font-mono text-[9px] text-foreground/80 leading-relaxed">
              · {note}
            </p>
          ))}
        </div>
      )}

      {/* Footer — data source + context */}
      <p className="font-mono text-[8px] text-muted-foreground/40 text-center leading-relaxed">
        {detectedPos ? `${t("rangePanel.posicao")}: ${detectedPos} · ` : ''}{stackBb.toFixed(0)}bb
        {openerPos ? ` · opener: ${openerPos}` : ''}
        {' · '}{t("rangePanel.fonte")}: {apiData ? 'Nash MTT (local)' : t("rangePanel.fonteEstatica")}
        {!showGtoCtx && gto && !gto.available && ` · ${t("rangePanel.gtoIndisponivel")}`}
      </p>
    </section>
  );
}
