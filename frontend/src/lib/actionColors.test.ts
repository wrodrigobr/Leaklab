import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { ACTION_COLORS, colorFor, actionKey } from './actionColors';

/**
 * Uma cor por ação, e UMA fonte para cada cor.
 *
 * ── O defeito que originou (27/08) ─────────────────────────────────────────────────────────
 *
 * A paleta canônica dizia `fold: #fde047` (amarelo) e a grade pintava fold com
 * `rgba(113,113,122,0.35)` HARDCODED. As duas superfícies aparecem na MESMA tela do replayer: a
 * barra de frequência amarela ao lado da grade cinza, para a mesma ação.
 *
 * Pior que a divergência: `COLORS.fold = ACTION_COLORS.fold` era atribuído em `RangeGrid.tsx:18`
 * e **nunca lido**. A constante canônica estava lá, morta, ao lado do literal que mandava de
 * verdade. Contando os literais espalhados, a cor do fold tinha cinco fontes.
 *
 * A resolução foi tornar o fold neutro nos DOIS lugares, e não amarelo nos dois: fold é a
 * ausência de ação e ocupa ~65% das células num spot de abertura; cor forte é para quem põe
 * fichas.
 */

const SRC = join(import.meta.dirname, '..');

function arquivosDeCodigo(dir: string, acc: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      if (nome === 'node_modules' || nome === '__tests__') continue;
      arquivosDeCodigo(caminho, acc);
    } else if (/\.(ts|tsx)$/.test(nome) && !/\.test\.tsx?$/.test(nome)) {
      acc.push(caminho);
    }
  }
  return acc;
}

describe('paleta canônica de ações', () => {
  it('toda ação tem cor, e as ações que põem fichas têm cores distintas', () => {
    const chaves = ['fold', 'check', 'call', 'bet', 'raise', 'allin'] as const;
    for (const k of chaves) expect(ACTION_COLORS[k], `sem cor para ${k}`).toBeTruthy();
    // CONTRAPROVA de uma paleta que "existe" mas repete: raise e call precisam ser distinguíveis
    const investem = [ACTION_COLORS.call, ACTION_COLORS.bet, ACTION_COLORS.raise, ACTION_COLORS.allin];
    expect(new Set(investem).size).toBe(investem.length);
  });

  it('fold é neutro, não uma cor de ação', () => {
    // O que impede a volta do amarelo. Fold ocupa ~65% de um spot de abertura: se ele saturar,
    // compete visualmente com as mãos que de fato entram no pote.
    expect(ACTION_COLORS.fold).toMatch(/113,\s*113,\s*122/);
    expect(ACTION_COLORS.fold).not.toMatch(/fde047|yellow/i);
  });

  it('nenhum arquivo pinta ação com a cor do fold CRAVADA', () => {
    // A varredura N+1: o contador de consumidores pega quem parou de chamar; esta pega quem
    // reintroduz o literal. Eram QUATRO literais espalhados antes do conserto.
    const suspeitos: string[] = [];
    for (const f of arquivosDeCodigo(SRC)) {
      if (f.endsWith(join('lib', 'actionColors.ts'))) continue;   // a definição mora aqui
      const codigo = readFileSync(f, 'utf-8');
      if (/rgba\(\s*113\s*,\s*113\s*,\s*122/.test(codigo)) {
        suspeitos.push(f.slice(SRC.length + 1));
      }
    }
    expect(suspeitos, 'cor do fold cravada fora de actionColors.ts').toEqual([]);
  });

  it('a varredura está de fato varrendo o repositório', () => {
    // CONTROLE. Sem isto, um bug no caminho faria a varredura acima ler zero arquivo e passar
    // verde — o zero tranquilizador que já cegou um guarda meu nesta mesma semana.
    expect(arquivosDeCodigo(SRC).length).toBeGreaterThan(100);
  });

  it('normaliza o vocabulário real de ações', () => {
    expect(actionKey('folds')).toBe('fold');
    expect(actionKey('CALLS')).toBe('call');
    expect(actionKey('limp')).toBe('call');
    expect(actionKey('jam')).toBe('allin');
    expect(actionKey('shove')).toBe('allin');
    expect(actionKey('all-in')).toBe('allin');
    expect(colorFor('raise')).toBe(ACTION_COLORS.raise);
    // desconhecido cai em fold, que é o fallback seguro (não pinta agressão sem saber)
    expect(actionKey('coisa-que-nao-existe')).toBe('fold');
  });
});
