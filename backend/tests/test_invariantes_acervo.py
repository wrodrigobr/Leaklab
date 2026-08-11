# -*- coding: utf-8 -*-
"""Prova que a varredura de invariantes ENXERGA — cada sonda, uma por uma.

── Por que este teste é o mais importante do arquivo vizinho ──────────────────────────────────

`invariantes_acervo.py` é uma ferramenta de MEDIÇÃO, e neste projeto medidor quebrado já custou
mais caro que bug. Em 28/07 quatro diagnósticos imprimiram números confiantes e falsos, e um
deles reportou "zero perdidas" porque um `split()` num campo gravado colado fazia todo hash sair
errado. Zero tranquilizador encerra a investigação — é o pior resultado possível numa medição.

Então aqui não se testa o conserto: testa-se o detector. Para CADA invariante:

  1. banco limpo com duas decisões SÃS (uma preflop, uma postflop) → a sonda tem de dar 0;
  2. insere-se a violação forjada → a sonda tem de dar exatamente 1;
  3. NENHUMA outra sonda pode reagir à mesma forja.

O passo 3 é o que impede uma sonda de virar rede de arrasto. Sem ele, uma sonda larga demais
passaria nos passos 1 e 2 acusando meio acervo.

As sondas de coluna morta não cabem nesse molde: elas olham a coluna inteira, e uma forja não
mata uma coluna que já tem linha sã. Essas rodam num banco só delas, e em troca precisam provar
o caminho de VOLTA — com uma linha viva, a sonda cala. Uma sonda que só sabe acusar não mede.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as sch
from leaklab.invariantes_acervo import (INVARIANTES, LINHA_SA, LINHA_SA_POSTFLOP,
                                        melhorias, regressoes, varrer)

_FALHAS = []


def _banco(com_linhas_sas=True):
    """Banco novo, schema real, com (ou sem) as duas decisões sãs."""
    sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    c = sch.get_conn()
    c.execute("INSERT OR IGNORE INTO users (id, username, email, password_hash) "
              "VALUES (1, 'u', 'u@t.st', 'x')")
    c.execute("INSERT OR IGNORE INTO tournaments (id, user_id, tournament_id, hero) "
              "VALUES (1, 1, 'T-INV', 'Hero')")
    if com_linhas_sas:
        for linha in (LINHA_SA, LINHA_SA_POSTFLOP):
            d = dict(linha, tournament_id=1)
            cols = ', '.join(d)
            c.execute(f"INSERT INTO decisions ({cols}) VALUES ({', '.join('?' for _ in d)})",
                      tuple(d.values()))
    c.commit()
    return c


def _contagens(conn):
    return {r['id']: r['medido'] for r in varrer(conn)}


def test_linha_sa_nao_dispara_nenhuma_sonda():
    """CONTROLE DE BASE. Se o esqueleto já violasse algo, todo passo 2 abaixo seria vácuo."""
    c = _banco()
    ruidosas = {k: v for k, v in _contagens(c).items() if v}
    c.close()
    assert not ruidosas, f'a linha sã já dispara: {ruidosas}'
    print('OK  test_linha_sa_nao_dispara_nenhuma_sonda')


def test_cada_sonda_enxerga_a_propria_forja():
    """Uma forja por invariante, e a sonda certa — só ela — tem de reagir."""
    for inv in INVARIANTES:
        if inv.banco_isolado:
            continue
        c = _banco()
        antes = _contagens(c)
        inv.forjar(c)
        c.commit()
        depois = _contagens(c)
        c.close()

        subiu = {k: (antes[k], depois[k]) for k in depois if depois[k] != antes[k]}
        if depois[inv.id] - antes[inv.id] != 1:
            _FALHAS.append(f'{inv.id}: a forja não moveu a sonda '
                           f'({antes[inv.id]} → {depois[inv.id]})')
        outras = {k: v for k, v in subiu.items() if k != inv.id and k not in inv.sobrepoe}
        if outras:
            _FALHAS.append(f'{inv.id}: a forja também moveu {outras} — a sonda vizinha é larga '
                           f'demais, ou a forja quebra mais de uma coisa')
    assert not _FALHAS, '\n  ' + '\n  '.join(_FALHAS)
    print(f'OK  test_cada_sonda_enxerga_a_propria_forja ({len(INVARIANTES)} sondas)')


def test_sondas_de_coluna_medem_nos_dois_sentidos():
    """Coluna morta acusa; uma linha viva cala. Sonda que só acusa não é medida."""
    falhas = []
    for inv in INVARIANTES:
        if not inv.banco_isolado:
            continue
        assert inv.curar is not None, f'{inv.id} precisa de `curar` para provar o caminho de volta'

        c = _banco(com_linhas_sas=False)
        if _contagens(c)[inv.id] != 0:
            falhas.append(f'{inv.id}: acusou com a tabela VAZIA — não há coluna morta sem linha')

        inv.forjar(c)
        c.commit()
        if _contagens(c)[inv.id] != 1:
            falhas.append(f'{inv.id}: não acusou com a coluna morta')

        inv.curar(c)
        c.commit()
        if _contagens(c)[inv.id] != 0:
            falhas.append(f'{inv.id}: continuou acusando depois de uma linha viva')
        c.close()
    assert not falhas, '\n  ' + '\n  '.join(falhas)
    print('OK  test_sondas_de_coluna_medem_nos_dois_sentidos')


def test_toda_invariante_declara_forja_e_porta():
    """Sonda sem forja não prova que enxerga; sem porta, não prova que importa."""
    faltando = [inv.id for inv in INVARIANTES if not inv.forjar or not inv.porta]
    assert not faltando, f'invariantes incompletas: {faltando}'
    ids = [inv.id for inv in INVARIANTES]
    assert len(ids) == len(set(ids)), f'id repetido em {ids}'
    print(f'OK  test_toda_invariante_declara_forja_e_porta ({len(ids)} invariantes)')


def test_regressao_e_melhoria_sao_lidas_com_o_sinal_certo():
    """O veredito da varredura: só o que PIORA derruba; o que melhora pede baseline novo.

    Testado com números forjados, não com o acervo — o acervo muda a cada reprocesso e um teste
    que dependesse dele contaria como cobertura sem dar cobertura.
    """
    amostra = [{'id': 'A', 'baseline': 10, 'medido': 11, 'delta': 1},
               {'id': 'B', 'baseline': 10, 'medido': 10, 'delta': 0},
               {'id': 'C', 'baseline': 10, 'medido': 3, 'delta': -7}]
    assert [r['id'] for r in regressoes(amostra)] == ['A']
    assert [r['id'] for r in melhorias(amostra)] == ['C']
    print('OK  test_regressao_e_melhoria_sao_lidas_com_o_sinal_certo')

if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print(f'FAIL    {_t.__name__}: {type(_e).__name__}: {_e}')
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
