/**
 * Paleta canônica de cores por ação. Use ACTION_COLORS (ou ACTION_TW, para classes) em qualquer
 * widget que represente ação visualmente: barras de frequência, range grid, badges, balões da
 * mesa.
 *
 * ── A convenção é a do mercado, e isso é deliberado (15/09) ───────────────────────────────────
 *
 * Azul folda, verde paga, vermelho agride, vinho vai com tudo. É o padrão do GTO Wizard e do
 * PioSOLVER, e o jogador chega aqui já sabendo ler isso. Pedido do Rullian, com a captura do
 * GTO Wizard como referência: "como muitos jogadores já utilizam outras plataformas de estudo,
 * o ideal é que a gente siga o mesmo padrão de cores pra evitar confusões".
 *
 * A paleta anterior tinha call em AZUL e raise em VERDE, ou seja as duas invertidas em relação
 * ao que o jogador já sabe. Pior: o `SidePanels` do replayer já pintava fold azul, call verde e
 * raise vermelho por conta própria, então a mesma cor significava coisas diferentes em duas
 * telas NOSSAS. A varredura de 15/09 achou CINCO mapas de ação conflitantes no front, e o
 * all-in aparecia em cinco cores: vermelho, vermelho escuro, vermelho vivo, rosa e violeta.
 *
 * ── Por que check é verde e bet é vermelho ────────────────────────────────────────────────────
 *
 * Cada família tem dois tons porque as ações de uma nunca coexistem com as da outra no mesmo
 * menu: se existe aposta para pagar há fold, call e raise, e não há check; se não existe, há
 * check e bet, e não há fold nem call. Então check acompanha o call (passivo) e bet acompanha o
 * raise (agressivo), sem nunca competir na mesma tela.
 *
 * Dentro da família agressiva o tom FECHA conforme a agressão sobe: bet, raise, all-in. É a
 * mesma lógica que o GTO Wizard usa para separar sizings.
 *
 * ── O que mudou antes, e por que o guarda existe ──────────────────────────────────────────────
 *
 * Em 27/08 esta constante dizia `fold: #fde047` (amarelo) e a grade pintava fold com um rgba
 * CRAVADO. As duas superfícies aparecem na mesma tela do replayer. E `COLORS.fold` era
 * atribuído no `RangeGrid` e nunca lido: a constante canônica estava ali, morta, ao lado do
 * literal que mandava de verdade. `actionColors.test.ts` varre o front para isso não voltar, e
 * agora varre a paleta INTEIRA, não só a cor do fold.
 *
 * Fold deixou de ser neutro nesta mudança. O motivo antigo era legítimo (fold ocupa 60% ou mais
 * das células num spot de abertura, e cor forte compete com quem põe fichas), e por isso o azul
 * é médio em vez de vibrante. Mas ler a grade sem reaprender vale mais que a economia visual,
 * e é o que o mercado inteiro faz.
 */
export const ACTION_COLORS = {
  fold:  "#3E7DC8",  // azul: não põe fichas
  check: "#5FBA68",  // verde claro: passivo sem aposta na mesa
  call:  "#4CA455",  // verde: passivo, mas comprometeu fichas
  bet:   "#E5434A",  // vermelho: agressão inicial
  raise: "#D2333A",  // vermelho fechado: agressão sobre aposta
  allin: "#8C2028",  // vinho: agressão levada ao limite
} as const;

export type ActionKey = keyof typeof ACTION_COLORS;

/**
 * Versão em classes Tailwind, para quando o widget usa `className` em vez de `style`.
 *
 * Os hex estão ESCRITOS, não interpolados de ACTION_COLORS, porque o JIT do Tailwind só enxerga
 * classe que existe como string estática no fonte: `bg-[${cor}]` compila e não gera CSS nenhum,
 * e a barra sai transparente sem erro. O teste confere valor por valor que as duas tabelas
 * dizem a mesma cor, que é justamente a divergência de 27/08.
 */
export const ACTION_TW = {
  fold:  { bg: "bg-[#3E7DC8]", text: "text-[#7EA9DC]", ring: "ring-[#3E7DC8]/30" },
  check: { bg: "bg-[#5FBA68]", text: "text-[#8FCF95]", ring: "ring-[#5FBA68]/30" },
  call:  { bg: "bg-[#4CA455]", text: "text-[#7FC486]", ring: "ring-[#4CA455]/30" },
  bet:   { bg: "bg-[#E5434A]", text: "text-[#F08C90]", ring: "ring-[#E5434A]/30" },
  raise: { bg: "bg-[#D2333A]", text: "text-[#E88287]", ring: "ring-[#D2333A]/30" },
  allin: { bg: "bg-[#8C2028]", text: "text-[#C9737A]", ring: "ring-[#8C2028]/30" },
} as const;

/** Normaliza string de ação para a chave canônica. */
export function actionKey(raw: string | null | undefined): ActionKey {
  const s = (raw ?? "").toLowerCase().replace(/[-_ ]/g, "");
  if (s === "fold" || s === "folds" || s === "muck" || s === "mucks") return "fold";
  if (s === "check" || s === "checks") return "check";
  if (s === "call" || s === "calls" || s === "limp") return "call";
  if (s.startsWith("bet")) return "bet";
  if (s.startsWith("raise")) return "raise";
  if (s === "jam" || s === "shove" || s === "allin" || s === "alli") return "allin";
  return "fold"; // fallback seguro
}

export function colorFor(action: string | null | undefined): string {
  return ACTION_COLORS[actionKey(action)];
}

/** Classes Tailwind da ação, pela mesma normalização de `colorFor`. */
export function twFor(action: string | null | undefined) {
  return ACTION_TW[actionKey(action)];
}
