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

/** Critérios ok / total do gate — para a barrinha do painel de contexto. */
export function criteriosDoNo(item: ProgressionStatusItem): { ok: number; total: number } {
  const c = item.mastery?.criterios ?? [];
  return { ok: c.filter((x) => x.ok).length, total: c.length };
}
