import { useTranslation } from "react-i18next";

/**
 * Nome humano de um spot — FONTE ÚNICA, localizada.
 *
 * Existiam QUATRO produtores de rótulo para a mesma coisa, e eles discordavam no texto:
 *   · `mission_title` (backend) → "Abertura de SB · 50bb"  — e só em português
 *   · `labelFor` e `leakOptLabel` (Leak Trainer) → "Abertura (RFI) de SB"
 *   · `skillLabel` (Treinos), a partir da `category_key` → "Abertura (RFI) de SB"
 *
 * Duas consequências. A primeira é de idioma: o título vinha pronto do servidor, em PT, e
 * aparecia no Dashboard, nos Treinos, no Plano de Estudo e no Leak Trainer — um usuário em
 * EN/ES via a interface traduzida e o nome do leak em português. A segunda é de reconhecimento:
 * o MESMO leak tinha dois nomes conforme a tela, e o jogador não tem como saber que são o mesmo.
 *
 * Aqui o rótulo é derivado dos campos ESTRUTURADOS (cenário, posição, vs, profundidade), que já
 * viajam em toda missão e em toda `category_key`. O `titulo` do backend fica só como último
 * recurso, para dados que não tragam os campos.
 */
export interface SpotLabelInput {
  scenario?: string | null;
  position?: string | null;
  vs_position?: string | null;
  stack_bb?: number | null;
  /** `postflop` tem rótulo próprio (o cenário preflop não descreve a situação) */
  kind?: string | null;
}

/** Quebra a `category_key` (`scenario:pos:vs:stack`) — a ÚNICA taxonomia persistida. */
export function parseCategoryKey(key: string): SpotLabelInput {
  if (!key) return {};
  if (key.startsWith("pf:")) return { kind: "postflop", position: "BB", vs_position: "BTN" };
  const [scenario, position, vs_position, stack] = key.split(":");
  const n = Number(stack);
  return { scenario, position, vs_position, stack_bb: Number.isFinite(n) && n > 0 ? n : null };
}

/**
 * Devolve o rótulo localizado. `stack: false` omite a profundidade (listas curtas, chips).
 * `fallback` é o `titulo` do servidor, usado só quando não há campos estruturados.
 */
export function useSpotLabel() {
  const { t } = useTranslation("academy");
  return (input: SpotLabelInput | string | null | undefined,
          opts: { stack?: boolean; fallback?: string } = {}): string => {
    const { stack = true, fallback = "" } = opts;
    const s: SpotLabelInput = typeof input === "string" ? parseCategoryKey(input) : (input ?? {});
    const pos = s.position ?? "";
    const vs  = s.vs_position ?? "";
    if (!pos) return fallback;

    const base =
      s.kind === "postflop" ? t("leakTrainer.cat.postflopBb", { pos, vs })
      : s.scenario === "rfi"     ? t("leakTrainer.cat.rfi", { pos })
      : s.scenario === "vs_rfi"  ? t("leakTrainer.cat.vsRfi", { pos, vs })
      : s.scenario === "vs_3bet" ? t("leakTrainer.cat.vs3bet", { pos, vs })
      : fallback || pos;

    // A profundidade é parte da identidade do spot: a mesma mão é shove a 12bb e call a 30bb.
    // Sem ela, duas famílias diferentes leem como o mesmo leak.
    if (!stack || s.stack_bb == null) return base;
    return t("leakTrainer.cat.withStack", { base, stack: s.stack_bb, defaultValue: `${base} · ${s.stack_bb}bb` });
  };
}
