import type { MedalEmblem } from "@/components/hud/AchievementMedal";
import type { MedalTier } from "@/lib/medalTiers";

/**
 * achievementMedals — que medalha cada conquista de treino ganha. FONTE ÚNICA.
 *
 * ── A regra do tier, declarada ────────────────────────────────────────────────────────────────
 *
 * O tier é o PESO DO MARCO na trilha de esforço, e não raridade. Raridade exigiria saber quantos
 * alunos desbloquearam cada uma, dado que não temos e que mudaria o tier de uma conquista já
 * ganha (ninguém des-ganha um marco). Peso é estável e derivável do próprio critério.
 *
 * Isso mantém UMA escala na tela: a mesma que as barras de "domínio por habilidade" usam, com as
 * mesmas cores (`lib/medalTiers`). Duas escalas homônimas na mesma página seria o erro.
 *
 * As três conquistas cujo critério É atingir um tier de domínio (`silver`, `gold`, `diamond`)
 * recebem exatamente o tier correspondente. Sem isso, a conquista "Ouro" poderia sair com medalha
 * de prata e a tela se contradiria sozinha.
 *
 * ── Cobertura ────────────────────────────────────────────────────────────────────────────────
 *
 * As 12 chaves vêm de `_TRAINING_ACHIEVEMENT_DEFS` no backend. `tests/achievementMedals.test.ts`
 * exige que o mapa cubra todas — conquista sem medalha cairia num fallback silencioso e apareceria
 * como bronze genérico, indistinguível de uma conquista que É bronze.
 */
export const ACHIEVEMENT_MEDALS: Record<string, { tier: MedalTier; emblem: MedalEmblem }> = {
  // Primeiros passos
  "train:first":     { tier: "bronze",  emblem: "spade" },
  "train:reps50":    { tier: "bronze",  emblem: "chip" },
  "train:explorer":  { tier: "bronze",  emblem: "range" },
  "train:streak3":   { tier: "bronze",  emblem: "streak" },
  // Consistência
  "train:reps200":   { tier: "silver",  emblem: "bankroll" },
  "train:streak7":   { tier: "silver",  emblem: "clock" },
  "train:silver":    { tier: "silver",  emblem: "shield" },
  // Domínio
  "train:gold":      { tier: "gold",    emblem: "club" },
  "train:gold3":     { tier: "gold",    emblem: "bluff" },
  "train:streak30":  { tier: "gold",    emblem: "heart" },
  // Topo
  "train:reps1000":  { tier: "diamond", emblem: "crown" },
  "train:diamond":   { tier: "diamond", emblem: "diamond" },
};

/** Chave de conquista → chave de i18n (`trainAch.<key>.*`). O backend usa `:`, o i18n usa `_`. */
export const achievementI18nKey = (key: string) => (key || "").replace(/:/g, "_");
