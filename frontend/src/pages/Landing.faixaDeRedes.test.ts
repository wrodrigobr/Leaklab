import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { LANDING_NETWORKS } from './Landing';

/**
 * A faixa de redes compatíveis não deixa célula vazia, com qualquer número de salas.
 *
 * ── O defeito (15/09) ─────────────────────────────────────────────────────────────────────────
 *
 * A faixa era `grid-cols-2 md:grid-cols-4` e as salas passaram a ser CINCO quando o PartyPoker
 * entrou. Em desktop a segunda linha ficava com o PartyPoker sozinho e três buracos ao lado, e
 * como a faixa é desenhada em fio de cabelo (`gap-px` sobre `bg-border`), o fio contornava o
 * vazio e o buraco ficava ainda mais visível. Reportado pelo dono olhando a tela.
 *
 * Trocar 4 por 5 consertaria hoje e quebraria de novo na sexta sala, que é exatamente o que
 * aconteceu da quarta para a quinta. Então o layout passou a ser `flex-wrap` com `flex-1`: os
 * itens da última linha crescem e fecham a largura sozinhos.
 *
 * Este guarda existe para a grade de N colunas fixas não voltar sem que alguém faça a conta.
 * Ele não mede pixel (jsdom não faz layout): ele lê a classe e a quantidade de salas, que é o
 * par que produziu o defeito.
 */

/**
 * A faixa fecha as linhas? Ou o layout é elástico, ou o número de colunas divide a quantidade
 * de itens em TODA variante declarada (`grid-cols-2 md:grid-cols-4` são duas variantes).
 */
export function faixaFechaAsLinhas(classes: string, itens: number): { ok: boolean; motivo: string } {
  const colunas = [...classes.matchAll(/(?:^|[\s:])grid-cols-(\d+)/g)].map((m) => Number(m[1]));
  if (!colunas.length) {
    // Sem contagem fixa: flex-wrap com item elástico fecha a linha por construção.
    const elastico = /flex-wrap/.test(classes);
    return elastico
      ? { ok: true, motivo: 'flex-wrap: a última linha cresce e fecha' }
      : { ok: false, motivo: 'nem grade de colunas nem flex-wrap: o layout não está declarado' };
  }
  const quebram = colunas.filter((n) => itens % n !== 0);
  return quebram.length === 0
    ? { ok: true, motivo: `grade fixa que divide ${itens} itens` }
    : { ok: false, motivo: `${quebram.map((n) => `grid-cols-${n}`).join(' e ')} deixa item sozinho com ${itens} salas` };
}

const FONTE = readFileSync(join(import.meta.dirname, 'Landing.tsx'), 'utf-8');

describe('faixa de redes compatíveis', () => {
  it('o container da faixa não deixa célula vazia com as salas de hoje', () => {
    // O container é o que envolve o `LANDING_NETWORKS.map`: pega a `div` imediatamente anterior.
    const antes = FONTE.slice(0, FONTE.indexOf('LANDING_NETWORKS.map'));
    const abre = antes.lastIndexOf('<div className="');
    expect(abre, 'não achei o container da faixa no Landing.tsx').toBeGreaterThan(0);
    const classes = antes.slice(abre).replace(/^<div className="/, '').split('"')[0];

    const veredito = faixaFechaAsLinhas(classes, LANDING_NETWORKS.length);
    expect(veredito.ok, `${veredito.motivo} — classes: ${classes}`).toBe(true);
  });

  it('o guarda ACUSA a grade que produziu o defeito', () => {
    // CONTROLE. Sem ele, um erro na extração das classes faria o teste acima passar verde lendo
    // string vazia — o zero tranquilizador.
    const defeito = faixaFechaAsLinhas('grid grid-cols-2 gap-px md:grid-cols-4', 5);
    expect(defeito.ok).toBe(false);
    expect(defeito.motivo).toContain('grid-cols-4');

    // `grid-cols-2 md:grid-cols-5` com 5 salas parece resolver e NÃO resolve: no telefone são
    // 2+2+1 e o último fica sozinho com um buraco do lado. Escrevi esta asserção esperando
    // `true` e a função me corrigiu, o que é o guarda funcionando contra quem o escreveu.
    expect(faixaFechaAsLinhas('grid grid-cols-2 md:grid-cols-5', 5).ok).toBe(false);

    // o que de fato fecha
    expect(faixaFechaAsLinhas('grid grid-cols-1 md:grid-cols-5', 5).ok).toBe(true);
    expect(faixaFechaAsLinhas('flex flex-wrap gap-px', 5).ok).toBe(true);
    expect(faixaFechaAsLinhas('flex gap-px', 7).ok).toBe(false);   // sem wrap, não é elástico
  });

  it('as salas da faixa são as mesmas do texto de apoio', () => {
    // A faixa e a frase logo abaixo dela ("Suporte a hand histories de ...") saíram de listas
    // diferentes até 15/09, e a frase negava o PartyPoker. O teste de backend
    // `test_copy_cita_as_salas_suportadas` cobre a copy contra o parser; este cobre a FAIXA
    // contra a copy, que é o par que o jogador vê junto na mesma tela.
    const pt = JSON.parse(readFileSync(
      join(import.meta.dirname, '..', 'i18n', 'locales', 'pt-BR', 'landing.json'), 'utf-8'));
    const frase: string = pt.networks.subtitle;
    for (const rede of LANDING_NETWORKS) {
      const nome = rede.name.replace(/\s*\(.*\)$/, '');   // "ACR (WPN)" → "ACR"
      expect(frase, `a frase de apoio não cita ${nome}, que está na faixa`).toContain(nome);
    }
  });
});
