import { RangeGrid } from "@/components/replayer/RangeGrid";
import type { RangeSet } from "@/data/ranges";
import { cn } from "@/lib/utils";

/**
 * O conteúdo da janela flutuante: a grade e o mínimo para trocar de spot sem sair da mesa.
 *
 * ── O que ela é, e o que deliberadamente não é ────────────────────────────────────────────
 *
 * É consulta DURANTE a mão. O jogador tem alguns segundos, e o que ele precisa é a grade e três
 * escolhas: cenário, profundidade, posição. Tudo o mais que a `/ranges` tem — resumo por
 * categoria, contagem de combos, aviso de substituição — fica fora: numa janela de 380px sobre a
 * mesa, cada linha a mais é uma linha entre ele e a resposta.
 *
 * Ela é um PORTAL na mesma árvore React da página, então o estado é o mesmo objeto: mudar o
 * seletor aqui muda lá, e vice-versa, sem sincronização nenhuma. Duas cópias do estado
 * divergiriam, e o jogador estaria olhando um spot enquanto a página mostrava outro.
 */

export interface Cenario {
  id: string;
  rotulo: string;
  posicoes: string[];
  /** o cenário existe na faixa rasa (3 a 7bb)? Medido: lá só há RFI. */
  raso: boolean;
}

interface Props {
  range: RangeSet | null;
  carregando: boolean;
  cenarios: Cenario[];
  stacks: number[];
  stackRasoMax: number;
  cenarioId: string; setCenarioId: (v: string) => void;
  stack: number; setStack: (v: number) => void;
  posicao: string; setPosicao: (v: string) => void;
}

const CAIXA = "h-7 rounded-md border border-border bg-background/60 px-1.5 text-[11px] " +
  "text-foreground focus:outline-none focus:ring-1 focus:ring-primary";

export function ConsultaCompacta({
  range, carregando, cenarios, stacks, stackRasoMax,
  cenarioId, setCenarioId, stack, setStack, posicao, setPosicao,
}: Props) {
  const cenario = cenarios.find((c) => c.id === cenarioId) ?? cenarios[0];

  return (
    <div className="flex h-full flex-col gap-2 bg-background p-2 text-foreground">
      <div className="grid grid-cols-3 gap-1.5">
        <select value={cenarioId} onChange={(e) => setCenarioId(e.target.value)} className={CAIXA}>
          {cenarios.map((c) => <option key={c.id} value={c.id}>{c.rotulo}</option>)}
        </select>

        {/* A faixa rasa só tem RFI: oferecer 5bb num cenário que não existe lá manda o jogador
            para uma grade vazia bem no momento em que ele não pode investigar. */}
        <select value={stack} onChange={(e) => setStack(Number(e.target.value))} className={CAIXA}>
          {stacks
            .filter((s) => cenario.raso || s > stackRasoMax)
            .map((s) => <option key={s} value={s}>{s}bb</option>)}
        </select>

        <select value={posicao} onChange={(e) => setPosicao(e.target.value)} className={CAIXA}>
          {cenario.posicoes.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      <div className={cn("min-h-0 flex-1", carregando && "opacity-40")}>
        {range
          ? <RangeGrid range={range} />
          : (
            /* Sem carta para o spot, a janela DIZ isso. Grade vazia sem explicação, na mesa,
               leria como produto quebrado — e o jogador não vai investigar no meio de uma mão. */
            <div className="flex h-full items-center justify-center px-3 text-center">
              <span className="text-[11px] leading-snug text-muted-foreground">
                {carregando ? "…" : "Sem range para este spot"}
              </span>
            </div>
          )}
      </div>
    </div>
  );
}
