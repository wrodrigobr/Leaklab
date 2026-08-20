import type { ProgressionStatus, ProgressionStatusItem } from "@/lib/api";
import type { MedalEmblem } from "@/components/hud/AchievementMedal";

/**
 * trilhaTreino — a montagem da TRILHA (Training v2) a partir do estado do Protocolo.
 *
 * Lógica pura e separada da página de propósito: a ordem dos nós, o estado de cada um e o
 * emblema por cenário são regras testáveis sem montar React. A página só desenha.
 *
 * A fonte é UMA: `progression.status` — o mesmo endpoint que a tela clássica e o Leak
 * Trainer leem. A trilha não inventa progresso; ela dá corpo espacial ao que o gate de
 * domínio já decide (proposta: memória project_redesign_trilha_training).
 */

export type EstadoNo = "comprovado" | "dominado" | "ativo" | "bloqueado";

export interface NoDaTrilha {
  key: string;
  estado: EstadoNo;
  /** reabriu por regressão comprovada no jogo — o nó perde o selo e volta a pulsar */
  reaberto: boolean;
  item: ProgressionStatusItem;
}

/** Emblema gravado por cenário — o MESMO vocabulário das medalhas de conquista. */
export function emblemaDoCenario(scenario: string | undefined): MedalEmblem {
  switch ((scenario || "").toLowerCase()) {
    case "rfi": return "spade";
    case "vs_rfi": return "shield";     // defesa: o escudo
    case "vs_3bet": return "cards";     // duas cartas: o confronto re-raisado
    case "postflop": return "chip";
    default: return "target";
  }
}

/**
 * A trilha em ordem de CAMINHO: o que ficou para trás primeiro (dominadas na ordem do
 * backend, comprovadas incluídas), o nó ATIVO em seguida, e as próximas bloqueadas — a
 * ordem delas já é o EV do jogador, decidido pelo backend, e a trilha não a reordena.
 *
 * Leak REABERTO é a exceção deliberada: ele volta como ATIVO se for a missão ativa, e se
 * não for, continua entre as dominadas mas marcado `reaberto` — o desenho tira o selo e
 * pulsa em vermelho. Esconder a regressão seria mentir com a trilha.
 */
export function montarTrilha(status: ProgressionStatus | undefined | null): NoDaTrilha[] {
  if (!status) return [];
  const nos: NoDaTrilha[] = [];
  for (const d of status.dominadas ?? []) {
    nos.push({
      key: d.key,
      estado: d.estado === "comprovado_no_jogo" ? "comprovado" : "dominado",
      reaberto: !!d.reaberto,
      item: d,
    });
  }
  if (status.ativa) {
    nos.push({ key: status.ativa.key, estado: "ativo",
               reaberto: !!status.ativa.reaberto, item: status.ativa });
  }
  for (const p of status.proximas ?? []) {
    // a ativa às vezes também aparece em `proximas` em backends antigos — dedup por key
    if (nos.some((n) => n.key === p.key)) continue;
    nos.push({ key: p.key, estado: "bloqueado", reaberto: false, item: p });
  }
  return nos;
}

/**
 * Código curto do spot (enxerto 20/08): `BBvSB-20`, `RFI-BTN-30`. O grinder reconhece o
 * spot pelo código antes de ler a frase — e o código é derivado da CHAVE, então não inventa
 * informação nem depende de tradução.
 */
export function codigoDoNo(item: ProgressionStatusItem): string {
  const pos = (item.position || "").replace("+", "");
  const vs = (item.vs_position || "").replace("+", "");
  const bb = Math.round(Number(item.stack_bb) || 0);
  const cen = (item.scenario || "").toLowerCase();
  const base = cen === "rfi" ? `RFI-${pos}`
    : cen === "vs_rfi" ? `${pos}v${vs}`
    : cen === "vs_3bet" ? `${pos}v3B`
    : `${pos}${vs ? "v" + vs : ""}`;
  return bb > 0 ? `${base}-${bb}` : base;
}

/** Critérios ok / total do gate — para a barrinha do painel de contexto. */
export function criteriosDoNo(item: ProgressionStatusItem): { ok: number; total: number } {
  const c = item.mastery?.criterios ?? [];
  return { ok: c.filter((x) => x.ok).length, total: c.length };
}

/** Emblema do MOSTRADOR de critério do gate (cockpit v3) — vocabulário fixo por chave. */
export function emblemaDoCriterio(key: string): MedalEmblem {
  switch (key) {
    case "volume": return "chip";
    case "precisao": return "target";
    case "amplitude": return "range";
    case "fronteira": return "cards";
    case "transferencia": return "clock";
    default: return "target";
  }
}

/**
 * O placar da régua — HONESTO por construção (a crítica do painel de design derrubou a
 * proposta A exatamente por um eixo que mentia): `bbComprovados` soma o EV medido APENAS
 * dos leaks com estado comprovado_no_jogo — melhora validada por torneio real importado.
 * Dominado-no-treino conta em `dominados`, nunca em bb: treino fechado não é bb recuperado
 * até o jogo real confirmar.
 */
export function placarDaTrilha(nos: NoDaTrilha[]): {
  dominados: number; total: number; bbComprovados: number; bbNaMesa: number;
} {
  const fechados = nos.filter((n) => n.estado === "dominado" || n.estado === "comprovado");
  const bb = nos
    .filter((n) => n.estado === "comprovado" && !n.reaberto)
    .reduce((s, n) => s + Math.abs(n.item.ev_loss_bb ?? 0), 0);
  // "Ainda na mesa": o EV que os leaks NÃO fechados seguem custando — o goal-gradient que
  // faltava (enxerto 20/08). Reaberto conta como aberto: o custo voltou de verdade.
  const naMesa = nos
    .filter((n) => n.estado === "ativo" || n.estado === "bloqueado" || n.reaberto)
    .reduce((s, n) => s + Math.abs(n.item.ev_loss_bb ?? 0), 0);
  return { dominados: fechados.length, total: nos.length,
           bbComprovados: Math.round(bb * 10) / 10,
           bbNaMesa: Math.round(naMesa * 10) / 10 };
}
