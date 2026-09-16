import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseLeakSpot, hrefDaMao, fonteDaNavegacao, rotuloDoLeak } from "./playlistDoLeak";

/**
 * A playlist do leak: as setas percorrem as mãos do LEAK, mesmo entre torneios.
 *
 * O caso real que originou, do banco do dono: o leak "pagou onde o ideal era foldar, preflop"
 * tem 12 mãos espalhadas em OITO torneios. Com o `t=` da URL fixo em todo link, a segunda mão
 * da playlist era buscada no torneio da primeira, que não a tem.
 */

const TORNEIOS: Record<string, number> = {
  // as quatro primeiras mãos do leak medido, com o torneio de cada uma
  H_QhJd: 18, H_AdKd: 2, H_Kh7h: 30, H_3h3c: 19,
};

describe("playlist do leak", () => {
  it("lê o spot da URL e recusa o que não é spot", () => {
    expect(parseLeakSpot("preflop:call:fold")).toEqual({
      street: "preflop", actionTaken: "call", bestAction: "fold",
    });
    // URL malformada não pode quebrar o replayer: cai na navegação do torneio
    for (const ruim of [null, undefined, "", "preflop", "preflop:call", "a:b:c:d", "::", "preflop::fold"]) {
      expect(parseLeakSpot(ruim as string | null), JSON.stringify(ruim)).toBeNull();
    }
  });

  it("o link leva o torneio DA MÃO, não o da URL", () => {
    // O defeito, escrito como teste: sem o mapa, a mão H_Kh7h (torneio 30) seria buscada no 19.
    const href = hrefDaMao({
      mao: "H_Kh7h", tournamentId: "19", torneioDaMao: TORNEIOS,
      leakParam: "preflop:call:fold", leakLastN: 50,
    });
    expect(href).toContain("t=30");
    expect(href).not.toContain("t=19");
  });

  it("o leak viaja com o link, senão a playlist morre na segunda mão", () => {
    const href = hrefDaMao({
      mao: "H_AdKd", tournamentId: "18", torneioDaMao: TORNEIOS,
      leakParam: "preflop:call:fold", leakLastN: 50,
    });
    expect(href).toBe("/replayer?t=2&h=H_AdKd&leak=preflop%3Acall%3Afold&ln=50");
  });

  it("fora da playlist, o link é o de sempre", () => {
    // CONTRAPROVA: uma implementação que sempre anexasse `leak=` levaria playlist para dentro da
    // navegação normal do torneio, e o contador passaria a falar de uma lista que não existe.
    expect(hrefDaMao({ mao: "H9", tournamentId: "19" })).toBe("/replayer?t=19&h=H9");
    expect(hrefDaMao({ mao: "H9", tournamentId: "19", leakParam: "quebrado" }))
      .toBe("/replayer?t=19&h=H9");
  });

  it("preserva modo coach, aluno e o filtro da lista", () => {
    // As três coisas que o link já carregava antes da playlist existir. Perder qualquer uma
    // delas é sair do contexto no meio do estudo.
    const href = hrefDaMao({
      mao: "H3", tournamentId: "19", studentId: 62, coachMode: true, resultFilter: "error",
      leakParam: "flop:fold:call", leakLastN: 0,
    });
    expect(href).toContain("student=62");
    expect(href).toContain("coach=1");
    expect(href).toContain("f=error");
    expect(href).toContain("leak=flop%3Afold%3Acall");
    expect(href).toContain("ln=0");   // 0 é recorte válido (histórico inteiro), não ausência
  });

  it("a fonte da navegação tem precedência declarada", () => {
    expect(fonteDaNavegacao({ temLeak: true,  coachMode: true  })).toBe("leak");
    expect(fonteDaNavegacao({ temLeak: true,  coachMode: false })).toBe("leak");
    expect(fonteDaNavegacao({ temLeak: false, coachMode: true  })).toBe("coach");
    expect(fonteDaNavegacao({ temLeak: false, coachMode: false })).toBe("torneio");
  });

  it("o rótulo do leak diz a jogada FEITA antes da indicada", () => {
    // A ordem carrega o sentido do leak. Invertida, o mesmo texto acusa o oposto: "Call → Fold"
    // leria como "pagou onde devia foldar" num leak que é justamente o contrário.
    expect(rotuloDoLeak({ street: "preflop", actionTaken: "fold", bestAction: "call" }))
      .toBe("Fold → Call · preflop");
    // e passa pelo formatAction da casa, que é quem traduz o vocabulário do banco para o da
    // tela: `allin` na coluna é "Shove" em toda superfície, nunca "Allin" só aqui.
    expect(rotuloDoLeak({ street: "flop", actionTaken: "check", bestAction: "allin" }))
      .toBe("Check → Shove · flop");
  });

  it("o cabeçalho do replayer NOMEIA o leak, e o contador não repete a palavra", () => {
    // O texto que o dono viu: "REVISANDO UM LEAK" em cima de "mão 1/46 do leak". A linha de cima
    // não dizia QUAL leak, e a de baixo repetia a palavra. O guarda trava as duas pontas.
    const fonte = readFileSync(join(import.meta.dirname, "..", "pages", "Replayer.tsx"), "utf-8");
    expect(fonte, "o cabeçalho tem de interpolar o rótulo do leak")
      .toMatch(/leakPlaylist", \{ spot: rotuloDoLeak\(leakSpot\) \}/);
    expect(fonte, 'o contador não repete "do leak" depois do total')
      .not.toMatch(/navigation\.doLeak/);
  });

  it("o Replayer não sobrescreve a playlist do leak com a lista do torneio", () => {
    // A cicatriz de 14/08, aplicada ao caso novo: a playlist do coach substituía o filtro
    // CALADA, e o jogador pousava numa mão que a lista não mostrava. Aqui o risco é o efeito
    // que restaura a lista do torneio rodar depois e apagar a do leak.
    //
    // Não dá para montar o Replayer em teste (1.100 linhas, dez dependências de rede), então o
    // guarda lê o fonte e exige o `return` que protege a playlist. É menos que um teste de
    // comportamento e mais que nada, e diz por que existe.
    const fonte = readFileSync(join(import.meta.dirname, "..", "pages", "Replayer.tsx"), "utf-8");
    const efeito = fonte.slice(fonte.indexOf("Modo coach DESLIGADO"));
    const corpo = efeito.slice(0, efeito.indexOf("}, ["));
    expect(corpo, "o efeito que restaura a lista do torneio precisa sair quando há leak")
      .toMatch(/if \(leakSpot\) return;/);
  });
});
