import { MINIATURAS_DE_TREINO } from "@/data/miniaturasDeTreino";
import { ACTION_COLORS } from "@/lib/actionColors";
import { cn } from "@/lib/utils";

/**
 * A miniatura da range que ILUSTRA um card de treino.
 *
 * ── Por que ela existe (28/08) ─────────────────────────────────────────────────────────────
 *
 * O dono leu a primeira proposta da tela de treino e disse que a gente tende a encher a tela de
 * texto. Estava certo, e dava para medir: o mockup tinha 127 palavras e UM elemento visual.
 *
 * A regra que sobrou disso: **a imagem tem que carregar a informação que a frase carregava, para
 * a frase poder sair**. Se a imagem entra e o texto fica, virou enfeite.
 *
 * "Abrir o pote" não precisa da frase "com que mãos abrir de cada posição, por profundidade"
 * quando mostra o formato real da range de abertura. O desenho é o mesmo que o jogador vai
 * encontrar treinando, então a miniatura também ensina onde ele está indo.
 *
 * ── O que ela NÃO é ────────────────────────────────────────────────────────────────────────
 *
 * Ferramenta de consulta. Sem rótulo de mão, sem frequência, sem hover: um caractere por célula,
 * só a forma. Quem quer consultar vai em `/ranges`, que tem seletor, frequência e combos. Manter
 * a miniatura burra é o que impede ela de virar uma segunda fonte de verdade sobre a range.
 */

/** Um caractere por célula, na ordem de leitura da grade. Ver `gerar_miniaturas_de_treino.py`. */
const COR: Record<string, string> = {
  r: ACTION_COLORS.raise,
  c: ACTION_COLORS.call,
  a: ACTION_COLORS.allin,
  m: "hsl(215 16% 47%)",     // mista: cinza médio, porque a proporção não cabe em 4px
  f: ACTION_COLORS.fold,
};

export function MiniRange({ id, className }: { id: string; className?: string }) {
  const tira = MINIATURAS_DE_TREINO[id];
  // Sem miniatura o card fica sem ilustração, e isso é melhor que uma grade cinza inventada:
  // grade toda apagada leria como "sem dado", que é uma afirmação que não temos base para fazer.
  if (!tira) return null;

  // A grade e QUADRADA e dimensionada pela ALTURA do card, nao pela largura. A 1a versao usava
  // `w-full`: 13 colunas esticadas na largura do card viravam celulas de 30px e as ultimas linhas
  // eram cortadas -- no mockup parecia certo, e so a captura da tela real mostrou.
  return (
    <div
      aria-hidden
      className={cn("grid aspect-square h-full gap-px", className)}
      style={{ gridTemplateColumns: "repeat(13, minmax(0, 1fr))" }}
    >
      {Array.from(tira).map((ch, i) => (
        <span
          key={i}
          className="block aspect-square rounded-[0.5px]"
          style={{ background: COR[ch] ?? COR.f }}
        />
      ))}
    </div>
  );
}
