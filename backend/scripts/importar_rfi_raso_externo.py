# -*- coding: utf-8 -*-
"""Importa a faixa RASA (3-7bb) da carta RFI externa para a nossa base.

    python scripts/importar_rfi_raso_externo.py <arquivo.tsv> --dry-run
    python scripts/importar_rfi_raso_externo.py <arquivo.tsv> --apply

── Por que SO 3-7bb ────────────────────────────────────────────────────────────────────────

A conferencia de 26/08 (`comparar_rfi_com_carta_externa.py`) mediu 94,0% de concordancia entre a
nossa carta e a dele nas 64 celulas sobrepostas. Isso e credencial para a carta inteira, mas nao
para qualquer faixa dela: a mesma conferencia achou **AA e KK limpando no BTN entre 8 e 14bb** e
QQ/JJ limpando no SB a 2bb -- saida que nenhum solve MTT padrao produz. Ja **3-7bb vem push/fold
puro, zero limps**, que e exatamente o regime esperado nessa profundidade.

Entao entra 3-7bb, e so.

── O que muda de comportamento ─────────────────────────────────────────────────────────────

Hoje `_stack_bucket` satura na ponta rasa: o balde `10bb` cobre `[0, 12)`, e o caminho principal
do motor (`preflop_gto_ranges.py`, o `_stack_bucket` de dentro de `analyze_preflop`) le esse balde
SEM passar por `_balde_da_carta`. Resultado medido no acervo: 117 das 128 decisoes de RFI entre
2,5 e 7,5bb sao julgadas hoje pela carta de **10bb** -- 2 a 4 vezes mais funda que o stack real.
E a saturacao que `_profundidade_compativel` existe para impedir, e que ja produziu duas acusacoes
falsas medidas (3,9bb e 5,2bb) no caminho da range de jam.

Os baldes novos entram ANTES do `10bb` na lista, cobrindo `[2.5, 7.5)`. As duas pontas que hoje
caem no `10bb` -- `[0, 2.5)` e `[7.5, 12)` -- **continuam caindo nele**, entao nada que ja
funciona muda de endereco.

── O que os baldes novos NAO tem ───────────────────────────────────────────────────────────

So capturamos RFI. Os baldes 3-7bb tem `RFI` e mais nada: nao ha `vs_RFI`, `vs_3bet` nem
`faces_squeeze`. Nao copiei as secoes do balde de 10bb para dentro deles -- dado de 10bb gravado
num balde de 4bb e mentira escrita no arquivo, e comentario nao desfaz dado
([[reference_env_flags_lost_in_migration]] e a regra 8 do CLAUDE.md). O efeito disso no acervo e
medido por `medir_efeito_rfi_raso.py` e esta declarado no CHANGELOG.

── Contrato da celula (v3) ─────────────────────────────────────────────────────────────────

Copiado do formato que o motor ja consome (`is_v3 = 'open_pct' in rfi or 'raise_hands' in rfi`):
`open_pct` / `raise_pct` / `allin_pct` / `call_pct` / `fold_pct` sao **combos x frequencia / 1326**
(convencao conferida contra `BTN@100bb`: 0,5484 gravado = 0,5483 recalculado). As listas
`*_hands` sao pertencimento por frequencia > 0. `hand_freqs` so lista mao com alguma acao
diferente de fold -- mao ausente o motor ja trata como fold 100%.

O codigo de raise sai **sem tamanho** (`'R'`, nao `'R2'`): a carta de origem rotula so "RAISE",
sem sizing. `raise_to_bb_from_node` devolve None para codigo sem numero, entao o produto nao
ensina um tamanho que ninguem mediu.
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from comparar_rfi_com_carta_externa import le_externa                  # noqa: E402
from leaklab.preflop_gto_ranges import _RANGES_FILE                    # noqa: E402

_PROFUNDIDADES = (3, 4, 5, 6, 7)
_ORDEM = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')
_FONTE = {
    'origem': 'carta RFI de natecnica.com.br',
    'capturado_em': '2026-08-25',
    'autorizacao': 'do autor, declarada pelo dono do produto',
    'conferencia': '94,0% de concordancia com a nossa carta nas 64 celulas sobrepostas '
                   '(comparar_rfi_com_carta_externa.py, 26/08)',
    'faixa_aceita': '3-7bb: push/fold puro, zero limps. 2bb e 8-14bb foram RECUSADOS -- a carta '
                    'de origem limpa AA/KK no BTN nessas profundidades.',
    'secoes': 'somente RFI. vs_RFI/vs_3bet nao foram capturados e NAO foram herdados de outro '
              'balde.',
    'utg_e_utg1_sao_A_MESMA_CARTA': 'a origem serve a MESMA grade para UTG e UTG+1 em 20 das 21 '
                                    'profundidades. Confirmado no proprio site com controle: '
                                    'trocar para UTG+2 muda a grade (51 -> 54 all-ins a 5bb) e '
                                    'trocar para UTG+1 nao muda nada. E o produto dele, nao um '
                                    'defeito da captura. A nossa carta GW distingue as duas '
                                    '(UTG abre 14,7% e UTG+1 16,85% a 100bb).',
}


def _combos(mao):
    if len(mao) == 2:
        return 6
    return 4 if mao.endswith('s') else 12


def _freqs_da_acao(bruto):
    """{codigo_nosso: frequencia} a partir do rotulo do site.

    `ALL_IN` -> `RAI`; `RAISE` -> `R` (sem tamanho, porque a origem nao declara sizing);
    `FOLD` -> `F`; `CALL` -> `C`. Mix vira varias entradas somando 1,0.
    """
    mapa = {'ALL_IN': 'RAI', 'ALLIN': 'RAI', 'JAM': 'RAI', 'RAISE': 'R', 'FOLD': 'F', 'CALL': 'C'}
    txt = (bruto or '').strip()
    if not txt.upper().startswith('MIXED'):
        cod = mapa.get(txt.upper())
        return {cod: 1.0} if cod else {'F': 1.0}
    out = {}
    for parte in txt.split('|'):
        parte = parte.replace('Mixed:', '').strip()
        if '%' not in parte:
            continue
        nome = parte.split()[0].upper()
        try:
            f = float(parte.split()[-1].rstrip('%')) / 100.0
        except ValueError:
            continue
        cod = mapa.get(nome)
        if cod:
            out[cod] = round(out.get(cod, 0.0) + f, 4)
    return out or {'F': 1.0}


def _celula(maos_ext, profundidade, pos):
    """Uma celula RFI no formato v3 que o motor ja consome."""
    freqs = {}
    for mao, bruto in maos_ext.items():
        f = _freqs_da_acao(bruto)
        if set(f) != {'F'}:                       # mao 100% fold nao entra em hand_freqs
            freqs[mao] = f

    def _massa(pred):
        t = 0.0
        for mao, bruto in maos_ext.items():
            for cod, v in _freqs_da_acao(bruto).items():
                if pred(cod):
                    t += _combos(mao) * v
        return round(t / 1326.0, 4)

    def _lista(pred):
        return ','.join(sorted(m for m, b in maos_ext.items()
                               if any(pred(c) and v > 0 for c, v in _freqs_da_acao(b).items())))

    e_raise = lambda c: c.startswith('R') and c != 'RAI'      # noqa: E731
    raise_pct, allin_pct = _massa(e_raise), _massa(lambda c: c == 'RAI')
    call_pct, fold_pct = _massa(lambda c: c == 'C'), _massa(lambda c: c == 'F')
    raise_hs, allin_hs = _lista(e_raise), _lista(lambda c: c == 'RAI')
    call_hs, fold_hs = _lista(lambda c: c == 'C'), _lista(lambda c: c == 'F')

    def _acao(tipo, cod, betsize, allin, freq, hands):
        return {'type': tipo, 'code': cod, 'betsize': betsize, 'allin': allin,
                'frequency': freq, 'hand_count': len([h for h in hands.split(',') if h]),
                'hands': hands}

    idx = _ORDEM.index(pos) if pos in _ORDEM else 0
    return {
        'open_pct': round(raise_pct + allin_pct + call_pct, 4),
        'raise_pct': raise_pct, 'allin_pct': allin_pct,
        'call_pct': call_pct, 'check_pct': 0.0, 'fold_pct': fold_pct,
        'raise_hands': raise_hs, 'allin_hands': allin_hs,
        'call_hands': call_hs, 'check_hands': '', 'fold_hands': fold_hs,
        'hand_freqs': freqs,
        'actions': [a for a in (
            _acao('FOLD', 'F', '0', False, fold_pct, fold_hs),
            _acao('RAISE', 'R', '', False, raise_pct, raise_hs),
            _acao('RAISE', 'RAI', '%.3f' % profundidade, True, allin_pct, allin_hs),
            _acao('CALL', 'C', '1.000', False, call_pct, call_hs),
        ) if a['hands']],
        'preflop_actions': '-'.join(['F'] * idx),
        '_fonte': 'externa/natecnica 25-08-2026',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tsv')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    ext = le_externa(args.tsv)
    with open(_RANGES_FILE, encoding='utf-8') as fh:
        base = json.load(fh)

    novos = {}
    for d in _PROFUNDIDADES:
        rfi = {}
        for pos in _ORDEM:
            maos = ext.get((pos, d))
            if not maos:
                continue
            if len(maos) != 169:
                sys.exit('celula %s@%dbb tem %d maos, nao 169 -- captura incompleta, nao importo'
                         % (pos, d, len(maos)))
            rfi[pos] = _celula(maos, d, pos)
        if not rfi:
            sys.exit('profundidade %dbb sem nenhuma celula na carta externa' % d)
        novos['%dbb' % d] = {'_fonte': _FONTE, 'RFI': rfi}

    print('baldes a criar: %s' % ', '.join(sorted(novos, key=lambda b: int(b[:-2]))))
    print('\n%-7s %-6s %8s %8s %8s %8s' % ('balde', 'pos', 'open%', 'jam%', 'raise%', 'fold%'))
    for b in sorted(novos, key=lambda x: int(x[:-2])):
        for pos in _ORDEM:
            c = novos[b]['RFI'].get(pos)
            if not c:
                continue
            print('%-7s %-6s %7.1f%% %7.1f%% %7.1f%% %7.1f%%'
                  % (b, pos, c['open_pct'] * 100, c['allin_pct'] * 100,
                     c['raise_pct'] * 100, c['fold_pct'] * 100))

    ja = [b for b in novos if b in (base.get('ranges') or {})]
    if ja:
        sys.exit('balde(s) ja existem no arquivo, nao sobrescrevo: %s' % ', '.join(ja))

    if not args.apply:
        print('\n[DRY-RUN] nada foi escrito em %s' % _RANGES_FILE)
        return

    shutil.copy2(_RANGES_FILE, _RANGES_FILE + '.bak')
    base.setdefault('ranges', {}).update(novos)
    meta = base.setdefault('_metadata', {})
    meta['baldes_de_fonte_externa'] = {b: _FONTE for b in novos}
    with open(_RANGES_FILE, 'w', encoding='utf-8') as fh:
        # `indent=2` porque o arquivo JA era indentado: escrever tudo numa linha so
        # trocaria 316 mil linhas por uma e tornaria o diff impossivel de revisar.
        json.dump(base, fh, ensure_ascii=False, indent=2)
    print('\nescrito em %s (backup em .bak)' % _RANGES_FILE)


if __name__ == '__main__':
    main()
