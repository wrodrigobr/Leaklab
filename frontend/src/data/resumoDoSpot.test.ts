import { describe, it, expect } from 'vitest';
import { resumoDoSpot, ROTULO_ACAO, type RangeSet } from './ranges';

/**
 * `resumoDoSpot` — a mistura vira categoria com nome e contagem.
 *
 * Nasceu do benchmark de 27/08: o visor do concorrente não deixa a estratégia mista como uma cor
 * intermediária para o olho decifrar, ele nomeia ("Raise ou Call: 62 combos · 4,7%"). O ganho é
 * didático e não custa dado novo.
 *
 * O teste que importa é o do DENOMINADOR: se a soma não fecha 1.326, alguma célula ficou fora e o
 * resumo estaria mentindo com cara de precisão.
 */

const vazia: RangeSet = { label: 'vazia', raise: new Set() };

describe('resumoDoSpot', () => {
  it('soma sempre os 1.326 combos do baralho', () => {
    const casos: RangeSet[] = [
      vazia,
      { label: 'so AA', raise: new Set(['AA']) },
      { label: 'com call', raise: new Set(['AA']), call: new Set(['KK', 'AKs']) },
      {
        label: 'com mistas',
        raise: new Set(['AA', '87s']),
        frequencies: { '87s': { raise: 0.15, fold: 0.85 }, AA: { raise: 1 } },
      },
    ];
    for (const r of casos) {
      const soma = resumoDoSpot(r).reduce((a, c) => a + c.combos, 0);
      expect(soma, `range "${r.label}" não fechou 1326`).toBe(1326);
    }
  });

  it('nomeia a mistura em português, com os termos de poker em inglês', () => {
    const r: RangeSet = {
      label: 'mista',
      raise: new Set(['87s']),
      frequencies: { '87s': { raise: 0.15, fold: 0.85 } },
    };
    const cat = resumoDoSpot(r).find((c) => c.chave === 'raise+fold');
    expect(cat, 'a categoria mista raise+fold não apareceu').toBeDefined();
    // A tela compõe assim: termos de poker em inglês, conector traduzido. O conector NÃO mora
    // na camada de dados — a 1ª versão juntava lá e o guarda de i18n pegou.
    expect(cat!.acoes.map((x) => ROTULO_ACAO[x]).join(' ou ')).toBe('Raise ou Fold');
    // 87s é suited: 4 combos
    expect(cat!.combos).toBe(4);
  });

  it('separa pura de mista em vez de somar as duas', () => {
    // CONTRAPROVA: uma versão que só olhasse "tem raise?" juntaria AA e 87s na mesma linha e o
    // resumo perderia justamente a informação que ele existe para dar.
    const r: RangeSet = {
      label: 'pura e mista',
      raise: new Set(['AA', '87s']),
      frequencies: { AA: { raise: 1 }, '87s': { raise: 0.15, fold: 0.85 } },
    };
    const chaves = resumoDoSpot(r).map((c) => c.chave);
    expect(chaves).toContain('raise');
    expect(chaves).toContain('raise+fold');
  });

  it('range vazia é 100% fold, e não uma lista vazia', () => {
    // Devolver [] aqui faria o painel sumir sem dizer nada — o mesmo "silêncio" que a gente
    // combateu no backend com o motivo declarado da ausência.
    const cats = resumoDoSpot(vazia);
    expect(cats).toHaveLength(1);
    expect(cats[0].chave).toBe('fold');
    expect(cats[0].combos).toBe(1326);
    expect(cats[0].pct).toBe('100.0');
  });

  it('ordena agressão antes de fold, e pura antes de mista', () => {
    const r: RangeSet = {
      label: 'ordem',
      raise: new Set(['AA', '87s']),
      call: new Set(['KK']),
      frequencies: { AA: { raise: 1 }, KK: { call: 1 }, '87s': { raise: 0.15, fold: 0.85 } },
    };
    const chaves = resumoDoSpot(r).map((c) => c.chave);
    expect(chaves.indexOf('raise')).toBeLessThan(chaves.indexOf('raise+fold'));
    expect(chaves.indexOf('raise')).toBeLessThan(chaves.indexOf('fold'));
    expect(chaves.indexOf('call')).toBeLessThan(chaves.indexOf('fold'));
  });

  it('trata fold como o RESTO, mesmo quando a frequência não declara fold', () => {
    // O caso que a 1ª versão deste arquivo não cobria, e por isso passou verde com a mutação que
    // trocava `1 - ativo` por `f.fold`. Aqui `87s` sobe 15% e o resto é fold, mas o mapa de
    // frequência NÃO tem a chave `fold` — que é como a célula é pintada (`buildGradient` também
    // calcula o resto). Ler `f.fold` daria "só raise" e o resumo diria 100% de agressão numa mão
    // que folda 85% das vezes.
    const r: RangeSet = {
      label: 'sem fold explicito',
      raise: new Set(['87s']),
      frequencies: { '87s': { raise: 0.15 } },
    };
    const cats = resumoDoSpot(r);
    const mista = cats.find((c) => c.chave === 'raise+fold');
    expect(mista, 'sem a chave `fold` no mapa, a mistura deixou de ser reconhecida').toBeDefined();
    expect(mista!.combos).toBe(4);
    expect(cats.find((c) => c.chave === 'raise')).toBeUndefined();
  });

  it('conta o peso certo por tipo de mão (par 6, suited 4, offsuit 12)', () => {
    // Sem isto o resumo pareceria certo e estaria errado: 169 células não são 1326 combos.
    const par: RangeSet     = { label: 'p', raise: new Set(['AA']) };
    const suited: RangeSet  = { label: 's', raise: new Set(['AKs']) };
    const offsuit: RangeSet = { label: 'o', raise: new Set(['AKo']) };
    expect(resumoDoSpot(par).find((c) => c.chave === 'raise')!.combos).toBe(6);
    expect(resumoDoSpot(suited).find((c) => c.chave === 'raise')!.combos).toBe(4);
    expect(resumoDoSpot(offsuit).find((c) => c.chave === 'raise')!.combos).toBe(12);
  });
});
