# -*- coding: utf-8 -*-
"""A referencia do solver no HUD so sai com amostra; abaixo do piso o card cai no "Ref MTT".

-- O defeito (auditoria TEL-4, 15/09) ------------------------------------------------------

`referencia_rfi_media` mede a MEDIA do que o solver abriria nas oportunidades do jogador e
acompanha o numero de uma folga binomial (2 desvios, piso `FOLGA_MINIMA_PP`). Sem piso de
AMOSTRA, com 4 oportunidades a folga da 54pp e a faixa vira "Solver 0-87%": o HUD imprime isso
como referencia e qualquer valor cai dentro dela. Referencia que nao exclui nada nao e
referencia.

O piso e o mesmo da matriz de abertura (`MINIMO_MAOS_DO_RESUMO`, 30) e vem DE LA, nao de um 30
escrito outra vez. Sem referencia do solver, `PlayerStatsCard` ja cai sozinho na faixa fixa de
MTT ("Ref MTT") — o front nao precisou mudar.

-- O que este arquivo defende --------------------------------------------------------------

1. Abaixo do piso nao ha referencia; no piso exato ela sai.
2. O piso e o MESMO numero da matriz (pega o fallback do import tardio derivando).
3. O que ja funcionava nao mudou: cobertura baixa continua None, mais amostra continua
   estreitando a faixa.
4. Varredura (regra 5): as funcoes de referencia do modulo estao DECLARADAS aqui; uma nova
   aparece como falha, para que a decisao sobre o piso dela seja consciente.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RAIZ = os.path.join(os.path.dirname(__file__), '..')

# Assentos que o chart RFI cobre: aqui o `n` do resultado e o numero de oportunidades.
COBERTOS = [('UTG', 22.0), ('CO', 18.0), ('BTN', 31.0)]


def _amostra(n):
    return [COBERTOS[i % len(COBERTOS)] for i in range(n)]


def test_o_piso_e_o_mesmo_da_matriz_de_abertura():
    from leaklab.preflop_gto_ranges import minimo_de_amostra
    from database.repositories import MINIMO_MAOS_DO_RESUMO
    assert minimo_de_amostra() == MINIMO_MAOS_DO_RESUMO == 30


def test_abaixo_do_piso_nao_ha_referencia_do_solver():
    from leaklab.preflop_gto_ranges import referencia_rfi_media, minimo_de_amostra
    piso = minimo_de_amostra()
    for n in (1, 4, 10, piso - 1):
        assert referencia_rfi_media(_amostra(n)) is None, 'n=%d ainda devolveu faixa' % n


def test_no_piso_exato_a_referencia_sai():
    from leaklab.preflop_gto_ranges import referencia_rfi_media, minimo_de_amostra
    piso = minimo_de_amostra()
    ref = referencia_rfi_media(_amostra(piso))
    assert ref is not None and ref['n'] == piso, ref
    assert 0 <= ref['lo'] < ref['hi'] <= 100, ref


def test_mais_amostra_continua_estreitando_a_faixa():
    """Regra 7: o piso corta o ruido, nao a informacao. A folga binomial segue viva."""
    from leaklab.preflop_gto_ranges import referencia_rfi_media, minimo_de_amostra
    piso = minimo_de_amostra()
    no_piso = referencia_rfi_media(_amostra(piso))
    farto = referencia_rfi_media(_amostra(300))
    assert farto['folga'] < no_piso['folga'], (no_piso['folga'], farto['folga'])


def test_cobertura_baixa_continua_sem_referencia_mesmo_com_amostra():
    """O guarda antigo nao foi trocado pelo novo: os dois valem."""
    from leaklab.preflop_gto_ranges import referencia_rfi_media
    # 100 oportunidades, so 10 em assento que o chart cobre.
    mistura = _amostra(10) + [('BB', 12.0)] * 90
    assert referencia_rfi_media(mistura) is None


# -- Varredura das funcoes de referencia (regra 5) -------------------------------------------

# Cada referencia do modulo e o piso que ela aplica hoje. `False` NAO e aprovacao: e o registro
# de que o piso ali ainda nao foi decidido. Quem acrescentar uma referencia nova tem de
# aparecer aqui, e ai a decisao sobre o piso e consciente.
REFERENCIAS = {
    'referencia_rfi_por_assento':        False,
    'referencia_3bet_por_assento':       False,
    'referencia_fold3bet_por_assento':   False,
    'referencia_cbet':                   False,
    'referencia_rfi_media':              True,
    'referencia_vpip_pfr_por_assento':   False,
}


def referencias_do_modulo(fonte):
    return {n.name for n in ast.walk(ast.parse(fonte))
            if isinstance(n, ast.FunctionDef) and n.name.startswith('referencia_')}


def aplica_o_piso(fonte, nome):
    for n in ast.walk(ast.parse(fonte)):
        if isinstance(n, ast.FunctionDef) and n.name == nome:
            return 'minimo_de_amostra' in ast.dump(n)
    return None


def test_varredura_as_referencias_declaradas_sao_as_que_existem():
    with open(os.path.join(RAIZ, 'leaklab', 'preflop_gto_ranges.py'), encoding='utf-8') as f:
        fonte = f.read()
    achadas = referencias_do_modulo(fonte)
    novas = achadas - set(REFERENCIAS)
    sumidas = set(REFERENCIAS) - achadas
    assert not novas, 'referencia nova sem decisao sobre o piso de amostra: %s' % sorted(novas)
    assert not sumidas, 'referencia declarada que nao existe mais: %s' % sorted(sumidas)
    for nome, esperado in REFERENCIAS.items():
        assert aplica_o_piso(fonte, nome) is esperado, \
            '%s: piso aplicado=%s, declarado=%s' % (nome, aplica_o_piso(fonte, nome), esperado)


def test_varredura_acha_o_caso_forjado():
    """Regra 1: o medidor tem de se mexer."""
    forjado = (
        "def referencia_nova(x):\n"
        "    return {'lo': 0, 'hi': 100}\n"
        "def referencia_rfi_media(x):\n"
        "    if n < minimo_de_amostra():\n"
        "        return None\n"
    )
    assert referencias_do_modulo(forjado) == {'referencia_nova', 'referencia_rfi_media'}
    assert aplica_o_piso(forjado, 'referencia_nova') is False
    assert aplica_o_piso(forjado, 'referencia_rfi_media') is True
    sem_piso = "def referencia_rfi_media(x):\n    return {'lo': 0, 'hi': 89}\n"
    assert aplica_o_piso(sem_piso, 'referencia_rfi_media') is False


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
