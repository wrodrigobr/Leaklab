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
  /** street do spot postflop: a copy não pode presumir "flop" */
  street?: string | null;
  /** há aposta na mesa? sem isso o rótulo anuncia "vs c-bet" num spot de check/bet */
  facing?: boolean | null;
  /** categoria de INICIATIVA (`pf:street:pos:ini`): c-bet e barrel, o hero agride */
  iniciativa?: boolean | null;
}

/** Quebra a `category_key` (`scenario:pos:vs:stack`) — a ÚNICA taxonomia persistida. */
export function parseCategoryKey(key: string): SpotLabelInput {
  if (!key) return {};
  // `pf:` já foi UMA categoria só (BB vs BTN no flop). Hoje o backend produz `pf:<street>:<pos>`
  // e agrupa domínio em `pf:flop` / `pf:turn` / `pf:river`. Devolver BB vs BTN fixo fazia as três
  // habilidades postflop aparecerem com o MESMO nome na lista de domínio, e a de river anunciar
  // "(flop)". Sem posição conhecida, é melhor não inventar uma.
  if (key.startsWith("pf:")) {
    const [, a, b, c] = key.split(":");
    const streets = ["flop", "turn", "river"];
    // `pf:<street>:<pos>:ini` (12/08): categoria de INICIATIVA — c-bet e barrel. A chave da
    // defesa segue sem sufixo de propósito, porque `progression_attempts` é chaveado por ela e
    // o histórico agregado de antes era majoritariamente defesa.
    if (a && streets.includes(a))
      return { kind: "postflop", street: a, position: b || "", vs_position: "",
               iniciativa: c === "ini" };
    return { kind: "postflop", position: "BB", vs_position: "BTN", street: "flop" };  // `pf:bb_defense` legado
  }
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
      // A street e a existência de aposta vinham HARDCODED na copy ("... vs c-bet de X (flop)"),
      // herança de quando havia uma categoria postflop só. O acervo serve flop, turn e river, e
      // serve spots SEM aposta na mesa — o rótulo anunciava "vs c-bet (flop)" com 5 cartas no
      // board e nenhuma ficha do vilão.
      s.kind === "postflop"
        ? (vs
            ? t(s.facing ? "leakTrainer.cat.postflopBb" : "leakTrainer.cat.postflopNoBet",
                { pos, vs, street: t(`leakTrainer.cat.street.${s.street || "flop"}`, s.street || "flop") })
            // Sem vs_position, o rótulo era SÓ a street — três categorias da mesma street liam
            // idênticas. Com a posição e a iniciativa a categoria diz o que o jogador treina:
            // "C-bet e barrel: SB com a iniciativa (turn)" vs "SB defende no turn".
            : t(s.iniciativa ? "leakTrainer.cat.pfIniciativa" : "leakTrainer.cat.pfDefesa",
                { pos, street: t(`leakTrainer.cat.street.${s.street || "flop"}`, s.street || "flop") }))
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
