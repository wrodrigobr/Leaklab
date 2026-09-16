import { describe, it, expect } from 'vitest';
import { frequenciasDoSpot, rangeStats, resumoDoSpot, type RangeSet } from './ranges';

/**
 * `frequenciasDoSpot` — a frequência PONDERADA por ação, que é a conta do GTO Wizard.
 *
 * ── O defeito (15/09) ─────────────────────────────────────────────────────────────────────────
 *
 * O dono comparou o nosso BTN 10bb com o GTO Wizard. A carta é a MESMA (a API responde
 * `allin_pct: 0.3393` e `raise_pct: 0.055`; o GW mostra 33,5% e 5,6%), mas a tela mostrava
 * All-in 24,3%. A diferença não era de estratégia, era de conta: `resumoDoSpot` classifica a mão
 * inteira por COMPORTAMENTO, então uma mão que às vezes vai all-in e às vezes dá raise levava
 * todos os seus combos para a categoria "All-in ou Raise" e desaparecia das duas colunas puras.
 *
 * Quem estuda nas duas plataformas leria 24,3% contra 33,5% e concluiria que o nosso solver é
 * impreciso, o que é a pior leitura possível de um produto que vende precisão. Decisão do dono:
 * adotar o padrão de exibição do mercado.
 *
 * Havia TRÊS contas para a mesma tela, e duas discordavam: o rodapé da grade (`rangeStats`)
 * contava a célula inteira se ela tivesse qualquer ação (43,9% no BTN 10bb) enquanto a soma
 * ponderada dava 39,4%. Agora as duas saem daqui.
 */

/** Mão a mão, o BTN 10bb que o dono comparou (recorte com as mistas, que é onde a conta difere). */
const BTN_10BB: RangeSet = {
  label: 'BTN 10bb (recorte)',
  raise: new Set(['AA', '99', '77', 'A2o']),
  allin: new Set(['AA', '99', '77', 'A2o']),
  frequencies: {
    AA:    { allin: 1 },                          // pura: 6 combos inteiros no all-in
    '99':  { allin: 0.5425, raise: 0.4575 },      // a mais misturada da carta
    '77':  { allin: 0.937,  raise: 0.063 },
    A2o:   { allin: 0.8698, raise: 0.1302 },      // offsuit: 12 combos
  },
};

describe('frequenciasDoSpot', () => {
  it('distribui o combo pela frequência, como o GTO Wizard', () => {
    const f = frequenciasDoSpot(BTN_10BB);
    const combos = (acao: string) => f.acoes.find((a) => a.acao === acao)?.combos ?? 0;

    // `99` tem 6 combos e joga all-in 54,25% das vezes: 3,255 vão para o all-in.
    // AA (6) + 99 (3,255) + 77 (5,622) + A2o (10,4376) = 25,3146
    expect(combos('allin')).toBeCloseTo(6 + 6 * 0.5425 + 6 * 0.937 + 12 * 0.8698, 4);
    expect(combos('raise')).toBeCloseTo(6 * 0.4575 + 6 * 0.063 + 12 * 0.1302, 4);

    // COMBO FRACIONÁRIO é o esperado, não erro: é o que faz 443,61 aparecer no GW em vez de 444.
    expect(Number.isInteger(combos('allin'))).toBe(false);
  });

  it('a soma fecha os 1.326 combos do baralho, sempre', () => {
    // O teste do DENOMINADOR. Se não fecha, alguma célula ficou fora e a tela estaria mentindo
    // com cara de precisão.
    const casos: RangeSet[] = [
      { label: 'vazia', raise: new Set() },
      { label: 'só AA', raise: new Set(['AA']) },
      BTN_10BB,
      { label: 'com call', raise: new Set(['AA']), call: new Set(['KK', 'AKs']) },
      { label: 'soma passando de 1', raise: new Set(['AA']), frequencies: { AA: { allin: 0.8, raise: 0.8 } } },
    ];
    for (const r of casos) {
      const f = frequenciasDoSpot(r);
      const soma = f.acoes.reduce((a, x) => a + x.combos, 0);
      expect(soma, `soma de ${r.label}`).toBeCloseTo(1326, 6);
      expect(f.total).toBe(1326);
      expect(f.acoes.reduce((a, x) => a + x.pct, 0)).toBeCloseTo(100, 6);
    }
  });

  it('o rodapé da grade concorda com a soma das ações', () => {
    // A lição de 28/08 repetida em 15/09: duas contas para "quanto este spot joga", na mesma
    // tela. Antes o rodapé dizia 43,9% e as ações somavam 39,4% no BTN 10bb. Agora `rangeStats`
    // deriva daqui, então divergir exige alguém reescrever as duas.
    for (const r of [BTN_10BB, { label: 'só AA', raise: new Set(['AA']) } as RangeSet]) {
      const f = frequenciasDoSpot(r);
      const ativoPorAcao = f.acoes.filter((a) => a.acao !== 'fold').reduce((a, x) => a + x.combos, 0);
      expect(f.ativos).toBeCloseTo(ativoPorAcao, 6);
      expect(rangeStats(r).pct).toBe((f.ativos / f.total * 100).toFixed(1));
    }
  });

  it('a mão mista entra nas DUAS ações, e não numa categoria à parte', () => {
    // O defeito, escrito como teste. `99` é misto: na conta antiga ele não aparecia nem em
    // "All-in" nem em "Raise"; aqui ele aparece nos dois, com o peso de cada um.
    const so99: RangeSet = {
      label: 'só 99 misto', raise: new Set(['99']), allin: new Set(['99']),
      frequencies: { '99': { allin: 0.5425, raise: 0.4575 } },
    };
    const f = frequenciasDoSpot(so99);
    expect(f.acoes.find((a) => a.acao === 'allin')?.combos).toBeCloseTo(3.255, 4);
    expect(f.acoes.find((a) => a.acao === 'raise')?.combos).toBeCloseTo(2.745, 4);

    // e a categorização continua contando a mão como mista, que é o dado que o GW não tem
    expect(f.mistos).toBe(6);
    const cat = resumoDoSpot(so99);
    expect(cat.find((c) => c.acoes.length >= 2)?.combos).toBe(6);
  });

  it('não inventa ação que a carta não tem', () => {
    // CONTRAPROVA: uma lista que devolvesse sempre as quatro ações passaria nos testes de soma
    // acima e pintaria barra de `call` num spot de push/fold.
    const pushFold: RangeSet = {
      label: 'push/fold', raise: new Set(), allin: new Set(['AA']),
      frequencies: { AA: { allin: 1 } },
    };
    const acoes = frequenciasDoSpot(pushFold).acoes.map((a) => a.acao);
    expect(acoes).toEqual(['allin', 'fold']);
    expect(acoes).not.toContain('call');
    expect(acoes).not.toContain('raise');
  });
});
