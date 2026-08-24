import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { clampVerdict } from "./cardLogic";

/**
 * O clamp RC-D existe para garantir que o card nunca diga "Correto" enquanto o painel diz
 * "Fold 100%". Ele aceita `foldPct` como 5º parâmetro — e, até 24/08, NENHUM dos cinco
 * chamadores passava esse argumento. A garantia estava escrita no comentário e não existia no
 * produto: mesma forma da flag que ficou sete semanas desligada porque o comentário explicava
 * um estado que já tinha outra causa.
 *
 * `cardLogic.test.ts` cobria a função chamando-a DIRETAMENTE com foldPct, então passava verde
 * enquanto a rede estava desligada — cobertura sem cobrir. Estes testes olham a fiação.
 */

const lerFonte = (rel: string) => readFileSync(join(__dirname, "..", rel), "utf-8");

/** Chamadas de clampVerdict com os parênteses BALANCEADOS. Uma regex não-gulosa para no `)` de
 *  `verdictLevel(...)` e devolve a chamada cortada — foi assim que a mutação "passa fold_pct da
 *  grade" passou verde na primeira tentativa. */
function chamadasDeClamp(fonte: string): Array<{ texto: string; linha: number }> {
  const out: Array<{ texto: string; linha: number }> = [];
  const re = /clampVerdict\(/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(fonte)) !== null) {
    let i = m.index + m[0].length;
    let nivel = 1;
    while (i < fonte.length && nivel > 0) {
      if (fonte[i] === "(") nivel++;
      else if (fonte[i] === ")") nivel--;
      i++;
    }
    const linha = fonte.slice(0, m.index).split(String.fromCharCode(10)).length;
    out.push({ texto: fonte.slice(m.index, i), linha });
  }
  return out;
}

describe("clamp RC-D recebe mesmo o foldPct", () => {
  it("a função continua marcando erro quando o painel diz fold ~100%", () => {
    // controle: sem este, o teste de fiação abaixo poderia proteger um clamp quebrado
    expect(clampVerdict("correct", "raise", "raise", null, 1.0)).toBe("error");
    expect(clampVerdict("correct", "raise", "raise", null, 0.2)).toBe("correct");
    // mix legítimo não é rebaixado nem com fold alto
    expect(clampVerdict("correct", "raise", "raise", "gto_mixed", 1.0)).toBe("correct");
  });

  it("todos os chamadores passam o argumento — senão a rede está desligada", () => {
    const arquivos = ["components/replayer/SidePanels.tsx", "pages/Replayer.tsx"];
    const semArgumento: string[] = [];
    let total = 0;
    for (const rel of arquivos) {
      for (const c of chamadasDeClamp(lerFonte(rel))) {
        total++;
        if (!c.texto.includes("hand_freq?.fold") && !c.texto.includes("hand_freq.fold")) {
          semArgumento.push(`${rel}:${c.linha}`);
        }
      }
    }
    expect(total, "a varredura não achou chamada nenhuma — o padrão mudou").toBeGreaterThanOrEqual(5);
    expect(
      semArgumento,
      "clampVerdict sem `hand_freq.fold`: o card pode voltar a dizer Correto enquanto o painel diz Fold 100%",
    ).toEqual([]);
  });

  it("ninguém passa fold_pct (da GRADE) no lugar de hand_freq.fold (da MÃO)", () => {
    // `fold_pct` é a proporção de MÃOS que a posição descarta: UTG folda ~90% delas. Passá-lo
    // aqui marcaria erro em toda agressão de posição inicial, inclusive com AA — um conserto
    // que causaria dano que o bug não causava.
    for (const rel of ["components/replayer/SidePanels.tsx", "pages/Replayer.tsx"]) {
      for (const c of chamadasDeClamp(lerFonte(rel))) {
        // Comentários fora: um deles EXPLICA por que não se usa fold_pct, e a primeira versão
        // deste teste leu essa explicação como se fosse código. Comentário não é evidência —
        // nem a favor nem contra.
        const semComentario = c.texto
          .replace(/\/\*[\s\S]*?\*\//g, "")
          .split(String.fromCharCode(10))
          .map((l) => l.split("//")[0])
          .join(String.fromCharCode(10));
        const semOCerto = semComentario.replace(/hand_freq\??\.fold/g, "");
        expect(
          /fold_pct|foldPct/.test(semOCerto),
          `chamada usa fold_pct (da grade) em ${rel}:${c.linha}`,
        ).toBe(false);
      }
    }
  });
});
