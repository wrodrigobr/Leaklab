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
from database.repositories import _adapt
from leaklab.invariantes_acervo import (INVARIANTES, LINHA_SA, LINHA_SA_POSTFLOP,
                                        _forjar_linha, melhorias, regressoes, varrer)

_FALHAS = []

#: ids altos e proprios: sob Postgres o banco e COMPARTILHADO com as outras suites, e `1` ja
#: pertence a alguem.
_UID, _TID = 9802, 9802


def _banco(com_linhas_sas=True):
    """Conexao numa TRANSACAO ABERTA, com (ou sem) as duas decisoes sas. Nada e commitado.

    Antes isto trocava `sch.SQLITE_PATH` por um arquivo novo para ganhar um banco limpo. Sob
    `DATABASE_URL` a troca e ignorada, o banco e o mesmo de todo mundo, e a suite passava a
    medir o acervo alheio E a deixar as forjas gravadas (`hand_id='FORJA'`,
    `gto_nodes.spot_hash='forja-no-vazio'`). A transacao com rollback e o mesmo desenho do
    `DIA_6.py` e funciona nas duas gramaticas. Auditoria DIA-10 (15/09).

    Quem chama FECHA com `_desfazer(c)`, nunca com `c.commit()`.

    Em SQLITE o arquivo novo FICA: e hermetico, e barato, e sem ele a suite passaria a medir o
    banco de desenvolvimento do dono (medido: a sonda BOARD ja vinha em 1 e a forja nao movia
    nada). No Postgres a troca de caminho e ignorada, e quem isola e a transacao.
    """
    if not sch.USE_POSTGRES:
        sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    c = sch.get_conn()
    if not c.execute(_adapt("SELECT id FROM users WHERE id=?"), (_UID,)).fetchone():
        c.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                         "VALUES (?,?,?,?)"), (_UID, 'inv%d' % _UID, 'inv@t.st', 'x'))
    if not c.execute(_adapt("SELECT id FROM tournaments WHERE id=?"), (_TID,)).fetchone():
        c.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, hero) "
                         "VALUES (?,?,?,?)"), (_TID, _UID, 'T-INV', 'Hero'))
    if com_linhas_sas:
        for linha in (LINHA_SA, LINHA_SA_POSTFLOP):
            d = dict(linha, tournament_id=_TID)
            cols = ', '.join(d)
            c.execute(_adapt(f"INSERT INTO decisions ({cols}) "
                             f"VALUES ({', '.join('?' for _ in d)})"), tuple(d.values()))
    return c


def _desfazer(c):
    """Desfaz TUDO, inclusive o usuario e o torneio de esqueleto."""
    try:
        c.rollback()
    finally:
        c.close()


def _contagens(conn):
    return {r['id']: r['medido'] for r in varrer(conn)}


def test_linha_sa_nao_dispara_nenhuma_sonda():
    """CONTROLE DE BASE. Se o esqueleto já violasse algo, todo passo 2 abaixo seria vácuo."""
    c = _banco(com_linhas_sas=False)
    try:
        antes = _contagens(c)
        for linha in (LINHA_SA, LINHA_SA_POSTFLOP):
            d = dict(linha, tournament_id=_TID)
            c.execute(_adapt("INSERT INTO decisions (%s) VALUES (%s)"
                             % (', '.join(d), ', '.join('?' for _ in d))), tuple(d.values()))
        depois = _contagens(c)
    finally:
        _desfazer(c)
    # DELTA e nao absoluto: sob Postgres o banco e compartilhado e a baseline nao e zero. A
    # afirmacao e a mesma ("a linha sa nao dispara nada"), medida como movimento.
    ruidosas = {k: (antes[k], depois[k]) for k in depois if depois[k] != antes[k]}
    assert not ruidosas, f'a linha sã já dispara: {ruidosas}'
    print('OK  test_linha_sa_nao_dispara_nenhuma_sonda')


def test_cada_sonda_enxerga_a_propria_forja():
    """Uma forja por invariante, e a sonda certa — só ela — tem de reagir."""
    for inv in INVARIANTES:
        if inv.banco_isolado:
            continue
        c = _banco()
        try:
            antes = _contagens(c)
            inv.forjar(c)
            depois = _contagens(c)
        finally:
            _desfazer(c)     # a forja NAO fica gravada: era o que sujava o banco compartilhado

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
        try:
            # `decisions` vazia DENTRO da transacao (o DIA_6.py faz o mesmo): sonda de coluna
            # olha a coluna inteira, e uma linha viva de outra suite a calaria.
            c.execute("DELETE FROM decisions")
            if _contagens(c)[inv.id] != 0:
                falhas.append(f'{inv.id}: acusou com a tabela VAZIA — não há coluna morta sem linha')
            inv.forjar(c)
            if _contagens(c)[inv.id] != 1:
                falhas.append(f'{inv.id}: não acusou com a coluna morta')
            inv.curar(c)
            if _contagens(c)[inv.id] != 0:
                falhas.append(f'{inv.id}: continuou acusando depois de uma linha viva')
        finally:
            _desfazer(c)
    assert not falhas, '\n  ' + '\n  '.join(falhas)
    print('OK  test_sondas_de_coluna_medem_nos_dois_sentidos')


def test_toda_invariante_declara_forja_e_porta():
    """Sonda sem forja não prova que enxerga; sem porta, não prova que importa."""
    faltando = [inv.id for inv in INVARIANTES if not inv.forjar or not inv.porta]
    assert not faltando, f'invariantes incompletas: {faltando}'
    ids = [inv.id for inv in INVARIANTES]
    assert len(ids) == len(set(ids)), f'id repetido em {ids}'
    print(f'OK  test_toda_invariante_declara_forja_e_porta ({len(ids)} invariantes)')


class _ResultadoComoNoPostgres:
    """A superfície EXATA de `_PgResult`: `fetchall()` devolvendo dicts e nada mais.

    Sem `description`, sem `keys()`, sem indexação por posição. Se a varredura tocar em qualquer
    coisa fora daqui, este dublê estoura.
    """

    def __init__(self, cur):
        self._linhas = [dict(r) for r in cur.fetchall()]

    def fetchall(self):
        return list(self._linhas)

    def fetchone(self):
        return self._linhas[0] if self._linhas else None

    def __iter__(self):
        return iter(self._linhas)


class _ConexaoComoNoPostgres:
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=()):
        return _ResultadoComoNoPostgres(self._c.execute(sql, params) if params
                                        else self._c.execute(sql))


def test_a_varredura_roda_na_superficie_do_POSTGRES():
    """A suíte roda em SQLite; produção é Postgres, e as duas interfaces não são a mesma.

    A primeira versão de `_linhas` usava `cursor.description` e passou em TODOS os testes daqui
    para estourar `AttributeError: '_PgResult' object has no attribute 'description'` na
    primeira execução contra produção — depois do deploy, que é o pior momento para descobrir.

    LIMITE CONHECIDO: dublê prova LÓGICA, só o driver prova CONTRATO. Este teste garante que a
    varredura não usa nada além de `fetchall()`; não garante que o SQL é aceito pelo Postgres.
    """
    c = _banco()
    try:
        real = _contagens(c)
        disfarcada = {r['id']: r['medido'] for r in varrer(_ConexaoComoNoPostgres(c))}
    finally:
        _desfazer(c)
    assert disfarcada == real, f'a varredura muda de resultado conforme o driver: {disfarcada}'
    print('OK  test_a_varredura_roda_na_superficie_do_POSTGRES')


def test_ev_teto_preflop_enxerga_o_dinheiro_morto_dos_blinds():
    """A régua por COLUNAS é cega ao pote preflop: `pot_size` é NULL nessa street e `stack_bb`
    é o que sobra ATRÁS do blind postado. Caso real (14/08, id 317491 em produção): SB com
    0,2bb atrás folda K2o, gw_har mede 0,669bb — legítimo, porque SB+BB (1,5bb) já estão no
    pote e a coluna não os vê; a sonda acusava falso. O conserto é o piso de 1,5bb no pote
    preflop, e este teste exige os DOIS sentidos: o caso real cala a sonda, e um EV acima até
    do teto com piso (1,5 + 2·stack) continua acusando. Nenhuma outra sonda pode se mover."""
    c = _banco()
    try:
        antes = _contagens(c)

        _forjar_linha(c, street='preflop', pot_size=None, stack_bb=0.2,
                      effective_stack_bb=0.2, ev_loss_bb=0.669, ev_loss_source='gw_har')
        depois = _contagens(c)
        assert depois == antes, \
            f'EV preflop legítimo (dinheiro morto dos blinds) moveu sonda: ' \
            f'{ {k: (antes[k], depois[k]) for k in depois if depois[k] != antes[k]} }'

        _forjar_linha(c, street='preflop', pot_size=None, stack_bb=0.2,
                      effective_stack_bb=0.2, ev_loss_bb=2.0, ev_loss_source='gw_har')
        depois2 = _contagens(c)
    finally:
        _desfazer(c)
    esperado = dict(depois, **{'EV-TETO': depois['EV-TETO'] + 1})
    assert depois2 == esperado, \
        f'EV 2,0bb com teto-piso 1,9 devia acusar SÓ a EV-TETO: ' \
        f'{ {k: (depois[k], depois2[k]) for k in depois2 if depois2[k] != depois[k]} }'
    print('OK  test_ev_teto_preflop_enxerga_o_dinheiro_morto_dos_blinds')


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
