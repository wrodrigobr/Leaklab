import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { ACTION_COLORS, ACTION_TW, colorFor, actionKey, twFor } from './actionColors';

/**
 * Uma cor por ação, e UMA fonte para cada cor.
 *
 * ── Os dois defeitos que originaram ───────────────────────────────────────────────────────────
 *
 * 27/08: a paleta dizia `fold: #fde047` (amarelo) e a grade pintava fold com
 * `rgba(113,113,122,0.35)` HARDCODED. As duas superfícies aparecem na MESMA tela do replayer.
 * Pior: `COLORS.fold = ACTION_COLORS.fold` era atribuído em `RangeGrid.tsx:18` e **nunca lido**
 * — a constante canônica estava lá, morta, ao lado do literal que mandava de verdade.
 *
 * 15/09: a varredura achou CINCO mapas de ação completos e conflitantes (`actionColors`,
 * `SidePanels`, `PokerTableV3`, `GtoPanel`, e o trio LeakTrainer/AcademyGtoPreflop/
 * RangeClassesCard). All-in saía em vermelho, vermelho escuro, vermelho vivo, rosa e violeta,
 * dependendo da tela; call saía azul aqui e verde no replayer. O guarda de 27/08 não pegou
 * porque olhava UMA cor (o rgba do fold), e a divergência estava em todas as outras.
 *
 * Por isso os dois testes de varredura abaixo: um pega o literal de qualquer cor da paleta fora
 * daqui, o outro pega o ARQUIVO que monta mapa de ação próprio sem ler a fonte.
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

const ARQUIVO_DA_PALETA = join('lib', 'actionColors.ts');

/**
 * Arquivos que nomeiam ação perto de cor por um motivo que NÃO é paleta de ação. Declarado, não
 * omitido: a lista é curta de propósito, e cada entrada carrega o motivo. Sem o motivo escrito,
 * ninguém distingue decisão de esquecimento.
 */
const FORA_DA_PALETA: Record<string, string> = {
  'components/hud/GtoPanel.tsx':
    'as barras codificam VEREDITO (jogou o topo, jogou outra coisa), não ação; a cor de ação ' +
    'entra junto com o destaque da jogada do jogador, em mudança própria',
};

describe('paleta canônica de ações', () => {
  it('toda ação tem cor, e as ações que põem fichas têm cores distintas', () => {
    const chaves = ['fold', 'check', 'call', 'bet', 'raise', 'allin'] as const;
    for (const k of chaves) expect(ACTION_COLORS[k], `sem cor para ${k}`).toBeTruthy();
    // CONTRAPROVA de uma paleta que "existe" mas repete: as quatro que investem precisam ser
    // distinguíveis entre si.
    const investem = [ACTION_COLORS.call, ACTION_COLORS.bet, ACTION_COLORS.raise, ACTION_COLORS.allin];
    expect(new Set(investem).size).toBe(investem.length);
  });

  it('segue a convenção do mercado: azul folda, verde paga, vermelho agride', () => {
    // O que impede a volta da paleta invertida (call azul, raise verde), que era a nossa até
    // 15/09 e contradizia todo solver que o jogador usa fora daqui. Não fixa o hex exato (tom
    // pode ser calibrado); fixa a FAMÍLIA, que é o que o jogador lê.
    const canal = (hex: string) => ({
      r: parseInt(hex.slice(1, 3), 16),
      g: parseInt(hex.slice(3, 5), 16),
      b: parseInt(hex.slice(5, 7), 16),
    });
    const fold = canal(ACTION_COLORS.fold);
    expect(fold.b, 'fold tem de ser AZUL: o canal azul manda').toBeGreaterThan(fold.r);
    expect(fold.b).toBeGreaterThan(fold.g);

    for (const passiva of ['call', 'check'] as const) {
      const c = canal(ACTION_COLORS[passiva]);
      expect(c.g, `${passiva} tem de ser VERDE`).toBeGreaterThan(c.r);
      expect(c.g).toBeGreaterThan(c.b);
    }

    for (const agressiva of ['bet', 'raise', 'allin'] as const) {
      const c = canal(ACTION_COLORS[agressiva]);
      expect(c.r, `${agressiva} tem de ser VERMELHO`).toBeGreaterThan(c.g);
      expect(c.r).toBeGreaterThan(c.b);
    }

    // O tom FECHA conforme a agressão sobe: é o que separa all-in de raise na mesma família.
    const lum = (hex: string) => { const c = canal(hex); return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b; };
    expect(lum(ACTION_COLORS.allin), 'all-in é mais fechado que raise').toBeLessThan(lum(ACTION_COLORS.raise));
    expect(lum(ACTION_COLORS.raise), 'raise é mais fechado que bet').toBeLessThan(lum(ACTION_COLORS.bet));
  });

  it('ACTION_TW diz a MESMA cor que ACTION_COLORS', () => {
    // Os hex do ACTION_TW são escritos à mão porque o JIT do Tailwind não enxerga classe
    // interpolada. Escrito à mão é escrito duas vezes, e duas fontes divergem: foi exatamente o
    // defeito de 27/08. Este teste é o que torna a duplicação segura.
    for (const k of Object.keys(ACTION_COLORS) as Array<keyof typeof ACTION_COLORS>) {
      const hex = ACTION_COLORS[k].toLowerCase();
      expect(ACTION_TW[k].bg.toLowerCase(), `ACTION_TW.${k}.bg fora de ${hex}`).toContain(hex);
      expect(ACTION_TW[k].ring.toLowerCase(), `ACTION_TW.${k}.ring fora de ${hex}`).toContain(hex);
    }
  });

  it('nenhum arquivo crava um literal da paleta fora de actionColors.ts', () => {
    // A varredura N+1 do LITERAL. O guarda velho olhava só o rgba do fold; este olha as seis
    // cores, porque a divergência de 15/09 estava nas outras cinco.
    const hexes = Object.values(ACTION_COLORS).map(c => c.toLowerCase());
    const suspeitos: string[] = [];
    for (const f of arquivosDeCodigo(SRC)) {
      if (f.endsWith(ARQUIVO_DA_PALETA)) continue;   // a definição mora aqui
      const codigo = readFileSync(f, 'utf-8').toLowerCase();
      for (const hex of hexes) {
        if (codigo.includes(hex)) { suspeitos.push(`${f.slice(SRC.length + 1)} (${hex})`); break; }
      }
    }
    expect(suspeitos, 'cor da paleta cravada fora de actionColors.ts').toEqual([]);
  });

  it('nenhum arquivo monta um MAPA de ação próprio sem ler a fonte', () => {
    // O guarda que faltava. Cor cravada é fácil de ver; o que escapou foram arquivos inteiros
    // com a sua própria tabela ação -> cor, em classes Tailwind, sem nunca tocar a paleta.
    const ACAO = String.raw`(fold|check|call|bet|raise|allin|jam|shove)`;
    // A ação tem de aparecer como CHAVE de objeto ou dentro de comparação: assim `CheckCircle2`
    // e `className="...justify-between..."` não entram.
    //
    // `g` + matchAll, e não `match`: a primeira versão deste guarda usava `match` sem flag
    // global, que devolve UM casamento por linha. LeakTrainer e AcademyGtoPreflop declaram o
    // mapa inteiro numa linha só (`raise: "...", call: "...", allin: "...", fold: "..."`),
    // contavam uma ação e passavam VERDES. Dois arquivos com mapa próprio invisíveis para o
    // guarda que existia para achá-los.
    const COMO_CHAVE = new RegExp(
      String.raw`(?:^|[^A-Za-z])["']?${ACAO}s?["']?\s*:` + '|' +
      String.raw`(?:===|==|includes\(|startsWith\()\s*["']${ACAO}`, 'gi');
    const COR = /#[0-9a-fA-F]{3,8}|bg-\[#|(?:bg|text|from|via|to)-(?:blue|sky|cyan|indigo|violet|purple|emerald|green|lime|teal|red|rose|orange|amber|yellow|zinc|slate|gray|stone)-\d{2,3}/;

    const comMapaProprio: string[] = [];
    for (const f of arquivosDeCodigo(SRC)) {
      if (f.endsWith(ARQUIVO_DA_PALETA)) continue;
      const rel = f.slice(SRC.length + 1).split('\\').join('/');
      if (rel in FORA_DA_PALETA) continue;
      const codigo = readFileSync(f, 'utf-8');
      const acoesPintadas = new Set<string>();
      for (const linha of codigo.split('\n')) {
        if (!COR.test(linha)) continue;
        for (const m of linha.matchAll(COMO_CHAVE)) {
          const acao = (m[1] ?? m[2] ?? '').toLowerCase();   // o grupo que casou, não o texto todo
          if (acao) acoesPintadas.add(acao);
        }
      }
      // Uma ação só pode ser coincidência de nome; duas ou mais é tabela.
      if (acoesPintadas.size >= 2) comMapaProprio.push(`${rel} (${[...acoesPintadas].join(', ')})`);
    }
    expect(comMapaProprio, 'mapa de ação paralelo: use ACTION_COLORS/ACTION_TW').toEqual([]);
  });

  it('a declaração de FORA_DA_PALETA não guarda arquivo que não existe mais', () => {
    // Declaração que apodrece vira permissão esquecida.
    const existentes = new Set(arquivosDeCodigo(SRC).map(f => f.slice(SRC.length + 1).split('\\').join('/')));
    for (const rel of Object.keys(FORA_DA_PALETA)) {
      expect(existentes.has(rel), `FORA_DA_PALETA aponta para ${rel}, que não existe`).toBe(true);
      expect(FORA_DA_PALETA[rel].length, `motivo vazio para ${rel}`).toBeGreaterThan(30);
    }
  });

  it('a varredura está de fato varrendo o repositório', () => {
    // CONTROLE. Sem isto, um bug no caminho faria as varreduras acima lerem zero arquivo e
    // passarem verdes — o zero tranquilizador.
    expect(arquivosDeCodigo(SRC).length).toBeGreaterThan(100);
  });

  it('normaliza o vocabulário real de ações', () => {
    expect(actionKey('folds')).toBe('fold');
    expect(actionKey('CALLS')).toBe('call');
    expect(actionKey('limp')).toBe('call');
    expect(actionKey('jam')).toBe('allin');
    expect(actionKey('shove')).toBe('allin');
    expect(actionKey('all-in')).toBe('allin');
    expect(actionKey('mucks')).toBe('fold');
    expect(colorFor('raise')).toBe(ACTION_COLORS.raise);
    expect(twFor('jam')).toBe(ACTION_TW.allin);
    // desconhecido cai em fold, que é o fallback seguro (não pinta agressão sem saber)
    expect(actionKey('coisa-que-nao-existe')).toBe('fold');
  });
});
