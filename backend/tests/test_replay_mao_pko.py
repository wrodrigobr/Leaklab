# -*- coding: utf-8 -*-
"""O replayer estava MORTO para as maos PKO — e ninguem reportou, porque erro parece dado faltando.

── A cadeia que achou isto ────────────────────────────────────────────────────────────────────

A sonda ODDS media "fold acusado com equity abaixo do pot odds" em 25 linhas. Ao verificar o que
o CARD mostra (nao o que o banco diz), 16 de 16 mensuraveis eram FANTASMA: a sonda calculava o
preco com `pot_size` (o pote ANTES da aposta do vilao) e o card vivo usa o pote com a aposta —
o preco fecha e o veredito e coerente. As 9 restantes nao rendiam card NENHUM: o
`_build_replay_data` tinha o QUARTO regex de assento do projeto, inline (`_re.match`, invisivel
a varredura de `re.compile`), exigindo o `)` logo apos o numero:

    Seat 1: emmawoodford (12255 in chips, $15 bounty)     <- nao casava

Sem assento, o replay INTEIRO devolvia `{'error': 'Seats nao encontrados'}` para toda mao dos
11 torneios PKO. Hoje a leitura vem de `mesa_final.assentos_numerados`, a fonte unica.

── Por que a mao de fixture e a REAL ──────────────────────────────────────────────────────────

O cabecalho, o formato do assento e o trailing space sao copiados do raw_text de producao
(t51, mao 261295408695). Fixture inventada ja passou pelo motivo errado nesta sessao.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

MAO_PKO = """PokerStars Hand #261295408695: Tournament #4010771541, $7.20+$7.50+$1.80 USD Hold'em No Limit - Level X (300/600)
Table '4010771541 2' 8-max Seat #4 is the button
Seat 1: emmawoodford (12255 in chips, $15 bounty)
Seat 2: Th3GodFath3r77 (17289 in chips, $21.56 bounty)
Seat 4: Arxaiospower (41158 in chips, $32.57 bounty)
Seat 5: phpro (9500 in chips, $15 bounty)
emmawoodford: posts small blind 300
Th3GodFath3r77: posts big blind 600
*** HOLE CARDS ***
Dealt to phpro [Ah Kd]
phpro: raises 1200 to 1800
Arxaiospower: folds
emmawoodford: folds
Th3GodFath3r77: folds
Uncalled bet (1200) returned to phpro
phpro collected 1500 from pot
*** SUMMARY ***
Total pot 1500 | Rake 0
Seat 5: phpro collected (1500)
"""


def test_o_replay_de_mao_PKO_monta_a_mesa():
    from leaklab.parser import parse_hand_history
    from api.app import _build_replay_data
    hands = parse_hand_history(MAO_PKO)
    assert len(hands) == 1, len(hands)
    data = _build_replay_data(hands[0], [])
    assert 'error' not in data, f"replay PKO segue quebrado: {data.get('error')}"
    assert len(data.get('seats') or {}) == 4, data.get('seats')
    assert (data.get('timeline') or []), 'timeline vazia'
    print('OK  test_o_replay_de_mao_PKO_monta_a_mesa')


def test_CONTROLE_mao_sem_bounty_continua_montando():
    """Sem esta ancora, quebrar o formato classico passaria batido no teste de cima."""
    from leaklab.parser import parse_hand_history
    from api.app import _build_replay_data
    mao = MAO_PKO.replace(', $15 bounty', '').replace(', $21.56 bounty', '') \
                 .replace(', $32.57 bounty', '')
    data = _build_replay_data(parse_hand_history(mao)[0], [])
    assert 'error' not in data and len(data.get('seats') or {}) == 4, data.get('seats')
    print('OK  test_CONTROLE_mao_sem_bounty_continua_montando')


def test_assento_out_of_hand_segue_FORA_do_replay():
    """O filtro que pertence ao replay (nao a leitura) sobreviveu a unificacao: o assento
    'out of hand' e lido pela fonte unica mas excluido aqui — inclui-lo deslocava posicoes."""
    from leaklab.parser import parse_hand_history
    from api.app import _build_replay_data
    mao = MAO_PKO.replace(
        'Seat 4: Arxaiospower (41158 in chips, $32.57 bounty)',
        'Seat 4: Arxaiospower (41158 in chips, $32.57 bounty) out of hand '
        '(moved from another table into small blind)')
    assert 'out of hand' in mao, 'o replace nao casou — o teste estaria medindo a mao original'
    data = _build_replay_data(parse_hand_history(mao)[0], [])
    assert 'error' not in data, data.get('error')
    jogadores = {v['player'] for v in (data.get('seats') or {}).values()}
    assert 'Arxaiospower' not in jogadores, jogadores
    assert len(jogadores) == 3, jogadores
    print('OK  test_assento_out_of_hand_segue_FORA_do_replay')


def test_nenhum_regex_de_ROSTER_inline_fora_das_fontes():
    """Extensao da varredura dos N+1: a versao anterior so olhava `re.compile`, e o quarto
    consumidor usava `_re.match` inline. Agora qualquer literal `Seat (\\d+): (.+?) \\(` que
    capture nome+stack do roster conta, compile ou nao.

    LIMITE: linhas de SUMMARY (showed/collected/mucked) leem outra coisa e sao legitimas; a
    assinatura do roster e capturar o nome seguido de parentese de stack.
    """
    import re
    assinatura = re.compile(r"Seat \(\\d\+\): \(\.\+\?\) \\\(\(?\[0-9")
    permitidos = ('leaklab/mesa_final.py', 'leaklab/parser.py')
    raiz = os.path.join(os.path.dirname(__file__), '..')
    fora = []
    for pasta in ('leaklab', 'database', 'api'):
        for dirpath, _, arquivos in os.walk(os.path.join(raiz, pasta)):
            for nome in arquivos:
                if not nome.endswith('.py'):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, nome), raiz).replace(os.sep, '/')
                if rel in permitidos:
                    continue
                for i, linha in enumerate(open(os.path.join(dirpath, nome),
                                               encoding='utf-8').read().splitlines(), 1):
                    if assinatura.search(linha.split('#')[0]):
                        fora.append(f'{rel}:{i}: {linha.strip()[:80]}')
    assert not fora, ('leitura de roster fora da fonte unica — use '
                      'mesa_final.assentos_numerados:\n  ' + '\n  '.join(fora))
    print('OK  test_nenhum_regex_de_ROSTER_inline_fora_das_fontes')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
