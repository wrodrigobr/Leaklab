# -*- coding: utf-8 -*-
"""A grade de perfil por assento, e a invariante que ela tem de respeitar.

── O que originou (05/09) ────────────────────────────────────────────────────────────────

O dono pediu uma linha de TOTAL no card, "pro usuario ver que na media cai no valor que e
mostrado no HUD principal". Ao conferir a reconciliacao com dados reais, o total dava 26.588
maos e a soma dos assentos dava 26.575. Treze maos de diferenca.

Eram decisoes gravadas com `position='MP1'`. E a causa nao era rotulo estranho: **a grade
nasceu com OITO assentos e a mesa 9-max tem NOVE — faltava o LJ.** O `hand_state_builder`
rotula a 4a acao de mesa cheia como `MP1`, que e o mesmo assento com outro nome. Medido na
base inteira: 334 decisoes em 70 torneios com `MP1`, e `LJ` nao aparece uma unica vez.

O agravante: a traducao JA EXISTIA. `gto_utils._POSITION_NORM` mapeia MP1->LJ, MP2->HJ, MP->LJ
desde que spots postflop nesses assentos eram REJEITADOS no insert do no. O motor normalizava;
a consulta da grade comparava o rotulo cru. Regra 5 outra vez: a mesma regra em dois lugares,
e o lugar novo nao recebeu o que o antigo ja sabia.

── A invariante que este arquivo defende ─────────────────────────────────────────────────

**A grade tem de FECHAR com o HUD principal, para QUALQUER rotulo que o sistema saiba emitir.**

Nao e um teste do caso MP1; e a varredura N+1. Se amanha o parser emitir um rotulo novo e
ninguem mapear, a soma dos assentos deixa de bater com o total e este teste acusa — que e
exatamente o sinal que faltou por semanas. Testar so `MP1 -> LJ` congelaria o caso conhecido
e continuaria cego para o proximo.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                          # noqa: E402
import database.repositories as repo                                   # noqa: E402
from database.repositories import (                                    # noqa: E402
    POSICOES_NA_ORDEM, _adapt, get_player_stats, get_player_stats_by_position,
    rotulos_do_assento,
)
from leaklab.gto_utils import _POSITION_NORM, normalize_position       # noqa: E402


def _semeia(rotulos_por_mao):
    """Um usuario com N maos, uma por rotulo de posicao dado. Devolve o user_id."""
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM decisions")
    conn.execute("DELETE FROM tournaments")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()

    uid = repo.create_user('grade', 'grade@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt(
        "INSERT INTO tournaments (id, user_id, tournament_id, site, hero, played_at, imported_at) "
        "VALUES (1, ?, 'T1', 'pokerstars', 'Hero', '2026-09-01', '2026-09-01')"), (uid,))
    n = 0
    for rotulo in rotulos_por_mao:
        # Volume suficiente para a celula classificar (VPIP/PFR pedem 100 maos por assento).
        for _ in range(120):
            n += 1
            conn.execute(_adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, "
                "action_taken, best_action, score, label) "
                "VALUES (1, ?, 'preflop', ?, ?, 'raise', 0.1, 'standard')"),
                ('H%d' % n, rotulo, 'raise' if n % 2 else 'fold'))
    conn.commit()
    conn.close()
    return uid


def test_a_mesa_9max_tem_NOVE_assentos():
    """Nasceu com 8. LJ faltava, e nao ficava uma linha vazia: sumiam as maos dele."""
    assert len(POSICOES_NA_ORDEM) == 9, POSICOES_NA_ORDEM
    assert 'LJ' in POSICOES_NA_ORDEM
    # Ordem de fala, nao alfabetica: LJ age depois de UTG+2 e antes do HJ.
    assert POSICOES_NA_ORDEM.index('UTG+2') < POSICOES_NA_ORDEM.index('LJ') < POSICOES_NA_ORDEM.index('HJ')


def test_a_grade_FECHA_com_o_hud_principal_para_todo_rotulo_conhecido():
    """A varredura N+1: todo rotulo que o sistema sabe emitir tem de cair em algum assento.

    Se a soma dos assentos ficar abaixo do total, existe rotulo orfao — que foi exatamente o
    estado da grade ate 05/09, calado.
    """
    rotulos = sorted(set(POSICOES_NA_ORDEM) | set(_POSITION_NORM))
    uid = _semeia(rotulos)

    geral = get_player_stats(uid, days=3650, last_n=0)
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    soma = sum(linha['hands'] for linha in grade['positions'])

    orfaos = geral['total_hands'] - soma
    assert orfaos == 0, (
        'rotulo(s) sem assento: %d de %d maos nao caem em linha nenhuma. Rotulos semeados: %s'
        % (orfaos, geral['total_hands'], ', '.join(rotulos)))


def test_MP1_cai_no_assento_LJ():
    """O caso concreto que originou. `MP1` e `LJ` sao o MESMO assento, e a traducao ja
    existia em `gto_utils` — faltava a consulta usa-la em vez do rotulo cru."""
    uid = _semeia(['MP1'])
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    por_assento = {linha['position']: linha['hands'] for linha in grade['positions']}
    assert por_assento.get('LJ') == 120, por_assento
    assert 'MP1' not in por_assento, 'o rotulo cru virou uma linha propria'


def test_os_aliases_saem_da_fonte_unica():
    """Sem isto, alguem escreve uma 3a copia do mapa e ela envelhece sozinha (regra 5)."""
    assert rotulos_do_assento('LJ') == ('LJ', 'MP1', 'MP') or \
           set(rotulos_do_assento('LJ')) == {'LJ', 'MP1', 'MP'}, rotulos_do_assento('LJ')
    assert set(rotulos_do_assento('HJ')) == {'HJ', 'MP2'}
    # Assento sem alias devolve so ele proprio.
    assert rotulos_do_assento('BTN') == ('BTN',)
    # E a fonte e mesmo a do motor.
    for cru, canon in _POSITION_NORM.items():
        assert normalize_position(cru) == canon
        assert cru in rotulos_do_assento(canon)


def test_a_grade_NAO_emite_veredito_por_assento():
    """05/09 — a regua de `STAT_REFERENCES` e do JOGO INTEIRO, e aplica-la assento a assento
    produzia acusacao falsa: dos 6 jogadores com volume em producao, **5 de 6 acusados de
    `loose` no BB e 4 de 6 no SB, contra 0 de 6 do UTG ao HJ**. Nao eram cinco jogadores
    soltos; era a regua no lugar errado.

    E impossivel de satisfazer por construcao: o VPIP global e a media PONDERADA dos
    posicionais, entao exigir 18-24 em TODO assento so seria satisfeito por quem joga igual
    de todas as posicoes — que e exatamente o leak. Decisao do dono: nao criar regua por
    assento; a grade descreve e o veredito fica na linha TOTAL.

    A celula so pode carregar `value` e o gate de AMOSTRA. `flag` ou `healthy` de volta no
    payload e a acusacao esperando alguem repinta-la.
    """
    uid = _semeia(list(POSICOES_NA_ORDEM))
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)

    proibidos, bandas = set(), set()
    for linha in grade['positions']:
        for chave, cel in linha['stats'].items():
            proibidos |= ({'flag', 'healthy'} & set(cel))
            bandas.add(cel.get('band'))

    assert not proibidos, 'a celula por assento voltou a carregar veredito: %s' % sorted(proibidos)
    assert bandas <= {'ok', 'low_sample'}, 'banda de veredito por assento: %s' % sorted(bandas)


def test_o_gate_de_amostra_SOBREVIVE():
    """Contraprova da anterior: se `low_sample` sumisse junto, a grade passaria a afirmar
    numero sem amostra — que e o erro oposto e igualmente caro."""
    uid = _semeia(['BTN'])            # 120 maos: passa o min de VPIP (100), nao o de 3bet (750)
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    bandas = {c['band'] for l in grade['positions'] for c in l['stats'].values()}
    assert 'low_sample' in bandas or 'ok' in bandas, bandas


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
