"""
test_enqueue_pot_unit.py — o pote que vai para o solver está em BB, não em fichas.

**A terceira cópia da mesma montagem foi extraída para `montar_payload_postflop` justamente para
acabar com as divergências, e o chamador que sobrou ficou com o bug.** `_enfileirar_spot_da_decisao`
passava `spot['potSize']` (FICHAS) como `pot_bb`, enquanto os outros dois pontos do mesmo arquivo
dividiam pelo `level_bb` e explicavam por quê no comentário.

Consequência: pote ~100x inflado → SPR colapsa → o solver força all-in e devolve estratégia
degenerada com exploitability 0.0% FALSA. Medido em produção antes do conserto: **135 nós (2,6%)
com pote maior que 2,5x o stack**, 9 deles all-in a 100% e 11 com exploitability ≤ 0,05%.

O treino peneira esses nós desde 2026-08-02 (`trainer_pool._POTE_MAX_EM_STACKS`), mas o `/replay`
não peneira: eles continuavam virando veredito para o jogador.

Dois invariantes travados aqui:

1. **O pote enfileirado sai de `potBb`, nunca de `potSize`.** São campos vizinhos no mesmo dicionário
   e a troca é invisível na leitura.
2. **Pote implausível NÃO entra na fila.** Nó degenerado é pior que nó ausente: o ausente vira
   "sem cobertura" na tela, e o degenerado vira veredito confiante e errado. Isto é a regra 7 do
   CLAUDE.md aplicada — o conserto não pode causar dano que o bug não causava, e deixar entrar
   causaria.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import api.app as A


def _di(pot_chips, pot_bb, stack_bb=40.0):
    """Decisão como o pipeline a entrega: `potSize` em FICHAS, `potBb` já convertido."""
    return {
        'street': 'flop',
        'board': ['Ks', '6c', '7d'],
        'hero_cards': ['Ah', 'Kd'],
        'spot': {
            'position': 'BB', 'villainPosition': 'BTN',
            'effectiveStackBb': stack_bb,
            'potSize': pot_chips,          # FICHAS
            'potBb': pot_bb,               # BB
            'potType': 'srp',
        },
        'context': {},
    }


class _Espiao:
    """Captura o que chega em `montar_payload_postflop` sem montar nada."""
    def __init__(self):
        self.visto = None

    def __call__(self, **kw):
        self.visto = kw
        return None          # `montado` falsy → a função retorna False sem tocar no banco


def _com_espiao():
    import leaklab.gto_solver as gs
    original = gs.montar_payload_postflop
    espiao = _Espiao()
    gs.montar_payload_postflop = espiao
    return original, espiao


def test_o_pote_enfileirado_vem_em_BB_e_nao_em_fichas():
    """`potSize` e `potBb` são vizinhos no mesmo dicionário; trocar um pelo outro não aparece na
    leitura, e o solver não reclama — ele só devolve estratégia degenerada."""
    original, espiao = _com_espiao()
    try:
        A._enfileirar_spot_da_decisao(_di(pot_chips=3500, pot_bb=5.0, stack_bb=40), facing=1.65)
        assert espiao.visto is not None, 'nem chegou a montar o payload'
        assert espiao.visto['pot_bb'] == 5.0, f"passou {espiao.visto['pot_bb']} (fichas?)"
        assert espiao.visto['pot_bb'] != 3500, 'passou o valor em FICHAS'
    finally:
        import leaklab.gto_solver as gs
        gs.montar_payload_postflop = original
    print('OK  test_o_pote_enfileirado_vem_em_BB_e_nao_em_fichas')


def test_pote_implausivel_nao_entra_na_fila():
    """Quando o parser não extrai a BB, o próprio `potBb` sai igual ao valor em fichas. A peneira
    é a última linha de defesa, e ela NÃO enfileira: nó degenerado vira veredito confiante e
    errado, enquanto nó ausente vira apenas "sem cobertura"."""
    original, espiao = _com_espiao()
    try:
        # pote de 3500bb com stack de 40bb: é o valor em fichas escapando pelo `or 1`
        ok = A._enfileirar_spot_da_decisao(_di(pot_chips=3500, pot_bb=3500.0, stack_bb=40), facing=1.65)
        assert ok is False, 'enfileirou pote implausivel'
        assert espiao.visto is None, 'chegou a montar payload com pote implausivel'
    finally:
        import leaklab.gto_solver as gs
        gs.montar_payload_postflop = original
    print('OK  test_pote_implausivel_nao_entra_na_fila')


def test_pote_zero_ou_negativo_tambem_nao_entra():
    """Postflop sem pote não existe. Zero passaria pelo teto e viraria SPR infinito."""
    for pot in (0.0, -3.0):
        original, espiao = _com_espiao()
        try:
            ok = A._enfileirar_spot_da_decisao(_di(pot_chips=0, pot_bb=pot), facing=1.0)
            assert ok is False, f'enfileirou pote {pot}'
            assert espiao.visto is None
        finally:
            import leaklab.gto_solver as gs
            gs.montar_payload_postflop = original
    print('OK  test_pote_zero_ou_negativo_tambem_nao_entra')


def test_pote_plausivel_no_limite_ainda_passa():
    """A peneira não pode ser tão apertada que descarte spot legítimo: dois stacks no meio é o
    máximo que existe em heads-up, e um pote grande de river é normal."""
    original, espiao = _com_espiao()
    try:
        A._enfileirar_spot_da_decisao(_di(pot_chips=8000, pot_bb=80.0, stack_bb=40), facing=20.0)
        assert espiao.visto is not None, 'descartou pote legitimo de 2x o stack'
        assert espiao.visto['pot_bb'] == 80.0
    finally:
        import leaklab.gto_solver as gs
        gs.montar_payload_postflop = original
    print('OK  test_pote_plausivel_no_limite_ainda_passa')


def test_pote_ausente_nao_derruba_o_enfileiramento():
    """Sem `potBb` o payload segue com `None` e quem monta decide — o que não pode é levantar
    exceção no caminho do `/analyze`."""
    original, espiao = _com_espiao()
    try:
        di = _di(pot_chips=500, pot_bb=None)
        del di['spot']['potBb']
        A._enfileirar_spot_da_decisao(di, facing=1.65)
        assert espiao.visto is not None, 'não montou o payload sem potBb'
        assert espiao.visto['pot_bb'] is None
    finally:
        import leaklab.gto_solver as gs
        gs.montar_payload_postflop = original
    print('OK  test_pote_ausente_nao_derruba_o_enfileiramento')


def test_os_tres_pontos_do_arquivo_convertem_fichas_para_bb():
    """Varre o arquivo: nenhum ponto pode mandar `potSize` cru para `pot_bb`.

    A montagem já foi TRÊS cópias divergentes e foi extraída para uma função só justamente por
    isso — e mesmo assim o chamador que sobrou ficou com a versão errada. É a regra 5 do
    CLAUDE.md: regra que vale em N lugares vira função, com teste que varre os N+1.
    """
    import re
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as f:
        linhas = [l for l in f if not l.lstrip().startswith('#')]
    src = ''.join(linhas)
    # Duas armadilhas que a primeira versão deste teste caiu, as duas acusando código CERTO:
    #   1. cortar na vírgula escondia a divisão (`... / _lvl_bb, 2)` tem vírgula no meio);
    #   2. `potSize` aparece em COMENTÁRIO de fim de linha na chamada que usa `potBb` corretamente.
    # A regra que ficou é a mais simples possível: `potSize` só pode virar `pot_bb` se houver uma
    # DIVISÃO na mesma linha. Sem divisão, são fichas indo cruas.
    ruins = []
    for linha in src.split('\n'):
        codigo = linha.split('#', 1)[0]              # fora o comentário de fim de linha
        if 'potSize' not in codigo or 'pot_bb' not in codigo:
            continue
        if '/' in codigo:
            continue                                # converte
        ruins.append(codigo.strip())
    assert not ruins, f'potSize (fichas) indo cru para pot_bb: {ruins}'
    assert 'potSize' in src, 'a varredura nao encontrou potSize — passaria sem ler nada'
    # e a peneira de sanidade tem que existir no enfileiramento
    i = src.index('def _enfileirar_spot_da_decisao')
    trecho = src[i:i + 3000]
    assert '_stack * 2.5' in trecho, 'sumiu a peneira de pote implausivel do enfileiramento'
    print('OK  test_os_tres_pontos_do_arquivo_convertem_fichas_para_bb')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
    raise SystemExit(1 if fail else 0)
