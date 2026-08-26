# -*- coding: utf-8 -*-
"""Compara a NOSSA carta RFI com uma carta EXTERNA, nas profundidades que as duas cobrem.

    python scripts/comparar_rfi_com_carta_externa.py <arquivo.tsv>

Nao e importacao: e VALIDACAO CRUZADA. Duas cartas construidas de forma independente que
concordam sao evidencia de que a nossa esta certa; onde discordam ha uma pergunta de poker a
responder -- e a resposta pode ser que a errada e a nossa.

CONTROLES (regra 1 do CLAUDE.md: sem eles a concordancia alta nao vale nada) --------------

  1. VOCABULARIO. As duas cartas precisam falar das MESMAS 169 maos. Se os rotulos nao baterem,
     tudo vira "divergencia" e o numero e lixo. Roda antes de qualquer comparacao.
  2. AUTO-COMPARACAO. A nossa carta contra ela mesma tem que dar 100%. Se nao der, o comparador
     esta quebrado.
  3. DISCRIMINACAO. A nossa de 100bb contra a nossa de 10bb tem que dar concordancia BAIXA. Se
     der alta, o comparador nao esta olhando o dado -- esta dizendo "igual" para tudo.

Vocabulario: as duas cartas tem TRES acoes (agride / limpa / folda). `CALL` como acao de
abertura e LIMP. A nossa so tem limp no SB; a dele tem limp em varias posicoes -- essa e uma
divergencia de ESTRATEGIA, nao de formato, e por isso aparece na tabela em vez de ser escondida.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import _load                        # noqa: E402

_POS_EXTERNA = {'UTG_1': 'UTG+1', 'UTG_2': 'UTG+2'}
_AGRIDE = ('ALL_IN', 'RAISE', 'ALLIN', 'JAM')
_ROTULO = {'agride': 'RAISE', 'limp': 'CALL', 'fold': 'FOLD'}


# -- leitura das duas cartas, cada uma no seu dialeto --------------------------------------

def le_externa(caminho):
    """{(posicao_nossa, stack_int): {mao: acao_bruta}}"""
    out = {}
    with open(caminho, encoding='utf-8') as fh:
        for linha in fh:
            if linha.startswith('#') or not linha.strip():
                continue
            partes = linha.rstrip('\n').split('\t')
            pos_ext, stack = partes[0].split('@')
            maos = {}
            for bloco in partes[1:]:
                if '=' not in bloco:
                    continue
                acao, lista = bloco.split('=', 1)
                for m in lista.split(','):
                    if m:
                        maos[m] = acao
            out[(_POS_EXTERNA.get(pos_ext, pos_ext), int(stack))] = maos
    return out


def classifica_externa(acao):
    """'agride' | 'limp' | 'fold' a partir do rotulo bruto do site."""
    a = (acao or '').upper()
    if a.startswith('MIXED'):
        melhor, freq = 'FOLD', -1.0
        for parte in acao.split('|'):
            parte = parte.replace('Mixed:', '').strip()
            if '%' not in parte:
                continue
            try:
                f = float(parte.split()[-1].rstrip('%'))
            except ValueError:
                continue
            if f > freq:
                melhor, freq = parte.split()[0].upper(), f
        a = melhor
    if a in _AGRIDE:
        return 'agride'
    if a == 'CALL':
        return 'limp'
    return 'fold'


def _split(s):
    return [x for x in (s or '').split(',') if x]


def le_nossa(bucket, pos):
    """{mao: 'agride'|'limp'|'fold'} da NOSSA carta, ou None se a celula nao existe.

    `hand_freqs` manda quando existe (e o dado com frequencia, e resolve as maos mistas que
    aparecem em DUAS listas ao mesmo tempo). As listas sao o fallback.
    """
    cel = ((((_load().get('ranges') or {}).get(bucket) or {}).get('RFI')) or {}).get(pos)
    if not cel:
        return None
    out = {}
    for chave, rotulo in (('raise_hands', 'agride'), ('allin_hands', 'agride'),
                          ('call_hands', 'limp'), ('fold_hands', 'fold'),
                          ('check_hands', 'fold')):
        for m in _split(cel.get(chave)):
            out.setdefault(m, rotulo)
    for mao, freqs in (cel.get('hand_freqs') or {}).items():
        if not isinstance(freqs, dict) or not freqs:
            continue
        cod = max(freqs.items(), key=lambda kv: kv[1])[0]
        out[mao] = 'fold' if cod == 'F' else ('limp' if cod == 'C' else 'agride')
    return out


# -- comparacao ----------------------------------------------------------------------------

def compara(nossa, externa):
    """(iguais, diferentes, detalhe) -- detalhe = {(nossa, dele): n}"""
    iguais = diferentes = 0
    detalhe = {}
    for mao, acao in externa.items():
        dele = classifica_externa(acao)
        minha = nossa.get(mao)
        if minha is None:
            continue
        if minha == dele:
            iguais += 1
        else:
            diferentes += 1
            detalhe[(minha, dele)] = detalhe.get((minha, dele), 0) + 1
    return iguais, diferentes, detalhe


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: comparar_rfi_com_carta_externa.py <arquivo.tsv>')
    ext = le_externa(sys.argv[1])
    nossos = sorted((_load().get('ranges') or {}).keys(),
                    key=lambda b: int(b.replace('bb', '')))
    print('celulas na carta externa: %d' % len(ext))
    print('profundidades nossas:     %s' % ', '.join(nossos))

    # -- CONTROLE 1: vocabulario -----------------------------------------------------------
    ref = le_nossa('100bb', 'BTN')
    amostra = ext[('BTN', 100)]
    so_nossa = set(ref) - set(amostra)
    so_dele = set(amostra) - set(ref)
    print('\n[CONTROLE 1 vocabulario] nossa %d maos, dele %d; so nossa=%d so dele=%d  %s'
          % (len(ref), len(amostra), len(so_nossa), len(so_dele),
             'OK' if not so_nossa and not so_dele
             else 'FALHOU -> ' + str(sorted(so_nossa | so_dele)[:8])))
    if so_nossa or so_dele:
        sys.exit('vocabulario incompativel: a comparacao seria ruido')

    # -- CONTROLE 2: auto-comparacao -------------------------------------------------------
    espelho = {m: _ROTULO[a] for m, a in ref.items()}
    i, d, _ = compara(ref, espelho)
    print('[CONTROLE 2 auto]        BTN@100bb contra ela mesma: %d iguais, %d diferentes  %s'
          % (i, d, 'OK' if d == 0 else 'FALHOU'))
    if d:
        sys.exit('comparador quebrado')

    # -- CONTROLE 3: discriminacao ---------------------------------------------------------
    rasa = le_nossa('10bb', 'BTN')
    espelho_rasa = {m: _ROTULO[a] for m, a in rasa.items()}
    i2, d2, _ = compara(ref, espelho_rasa)
    print('[CONTROLE 3 discrimina]  BTN@100bb contra BTN@10bb: %d iguais, %d diferentes '
          '(%.0f%% concord.)  %s'
          % (i2, d2, 100.0 * i2 / max(1, i2 + d2),
             'OK' if d2 >= 20 else 'FALHOU -- o comparador nao esta olhando o dado'))
    if d2 < 20:
        sys.exit('comparador cego')

    # -- COMPARACAO REAL -------------------------------------------------------------------
    print('\n%-6s %-7s %8s %8s %8s   %s'
          % ('POS', 'STACK', 'iguais', 'difer', 'concord', 'natureza das diferencas'))
    tot_i = tot_d = 0
    agreg = {}
    linhas = []
    for bucket in nossos:
        prof = int(bucket.replace('bb', ''))
        for pos in sorted((((_load()['ranges'][bucket]).get('RFI')) or {}).keys()):
            maos_ext = ext.get((pos, prof))
            if maos_ext is None:
                continue
            nossa = le_nossa(bucket, pos)
            if not nossa:
                continue
            i, d, det = compara(nossa, maos_ext)
            tot_i += i
            tot_d += d
            for k, v in det.items():
                agreg[k] = agreg.get(k, 0) + v
            linhas.append((100.0 * i / max(1, i + d), pos, prof, i, d, det))

    for pct, pos, prof, i, d, det in sorted(linhas):
        nat = ', '.join('%s->%s x%d' % (a, b, n) for (a, b), n in
                        sorted(det.items(), key=lambda kv: -kv[1])[:3])
        print('%-6s %-7s %8d %8d %7.1f%%   %s' % (pos, str(prof) + 'bb', i, d, pct, nat))

    n = tot_i + tot_d
    print('\nTOTAL: %d maos em %d celulas sobrepostas' % (n, len(linhas)))
    print('  concordam: %d (%.1f%%)' % (tot_i, 100.0 * tot_i / max(1, n)))
    print('  divergem:  %d (%.1f%%)' % (tot_d, 100.0 * tot_d / max(1, n)))
    print('\nnatureza de TODAS as divergencias (nossa -> dele):')
    for (a, b), v in sorted(agreg.items(), key=lambda kv: -kv[1]):
        print('  %-7s -> %-7s %6d  (%.1f%% do total)' % (a, b, v, 100.0 * v / max(1, n)))

    profs_dele = sorted({p for _, p in ext})
    print('\nprofundidades so DELE (gap potencial nosso): %s'
          % ', '.join(str(p) for p in profs_dele if str(p) + 'bb' not in nossos))
    print('profundidades so NOSSAS: %s'
          % ', '.join(b for b in nossos if int(b.replace('bb', '')) not in profs_dele))


if __name__ == '__main__':
    main()
