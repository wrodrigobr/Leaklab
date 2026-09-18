# -*- coding: utf-8 -*-
"""test_escopo_do_dashboard.py - as TRES dimensoes do filtro do dashboard (17/09).

O dono pediu o filtro com tres dimensoes: ultimos N torneios, ultimas X maos (teto de 30 mil) e
faixa de data (com o seletor limitado a 12 meses).

-- O que este arquivo defende, e por que ele existe ----------------------------------------

Medido antes de escolher o desenho: `last_n` aparece 295 vezes no projeto (109 no repositorio, 54
na app, 132 em 13 arquivos de teste) e ainda e o nome do parametro HTTP. Das 29 linhas que mexem
com ele, 24 apenas o REPASSAM para `_build_tournament_filter` -- entao alargar o TIPO daquela
funcao alcanca os 38 chamadores sem tocar em nenhum, e um parametro novo custaria 63 lugares.

O preco e um nome que fica curto: `last_n` passa a carregar um escopo. A varredura da secao 4 e o
que paga esse preco: ela descobre por INTROSPECCAO toda funcao do repositorio que recebe `last_n`
e chama cada uma com um escopo de dict, exigindo que nenhuma quebre. Sem ela, isto seria um tipo
alargado pela metade -- e a casa tem a cicatriz exata disso (o sentinela `0` ensinado a uma das
duas implementacoes da janela, e o grafico de bankroll vindo VAZIO com "Historico" selecionado).

A varredura DECLARA o que nao conseguiu chamar. Varredura que pula em silencio e a que mente.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_escopo_dash_test.db'
if os.path.exists('_escopo_dash_test.db'):
    os.remove('_escopo_dash_test.db')

import database.schema as schema

schema.init_db()

from datetime import date, datetime, timedelta

import database.repositories as repo
from database.repositories import (MESES_MAXIMOS_DO_ESCOPO, TETO_DE_MAOS_DO_ESCOPO, _adapt,
                                   _build_tournament_filter, get_conn, get_ev_summary)

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("  FAIL: %s" % msg)


UID = 501
N_TORNEIOS = 10
MAOS_POR_TORNEIO = 100


def _semear():
    """10 torneios, 100 maos cada, um por dia a partir de 02/01. E10 e o mais RECENTE.

    `imported_at` sai em ordem INVERTIDA de proposito: se o codigo regredir para o eixo do
    upload, o resultado sai TROCADO e nao so impreciso. E a cicatriz do lote do Rullian, que
    subiu 280 torneios de 3 meses com `imported_at` espremido em 25 horas.
    """
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (?,?,?,?)"),
                 (UID, 'escopo', 'escopo@e.st', 'h'))
    base = date(2026, 1, 1)
    base_imp = datetime(2026, 9, 3, 12, 0, 0)
    for i in range(1, N_TORNEIOS + 1):
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, "
            "played_at, imported_at, hands_count) VALUES (?,?,?,?,?,?,?)"),
            (UID, 'E%02d' % i, 'Escopo %d' % i, 'Hero',
             (base + timedelta(days=i)).isoformat(),
             (base_imp - timedelta(seconds=i)).strftime('%Y-%m-%d %H:%M:%S'),
             MAOS_POR_TORNEIO))
        tid = conn.execute(_adapt("SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
                           (UID, 'E%02d' % i)).fetchone()['id']
        conn.execute(_adapt(
            "INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, label, score, position, vs_position, stack_bb, "
            "pot_size, facing_bet, estimated_equity, ev_loss_source, ev_loss_bb, num_players, "
            "gto_label) VALUES (?, 'H', 'preflop', 'AsKs', '[]', 'call', 'raise', "
            "'small_mistake', 0.3, 'BTN', 'CO', 50.0, 10.0, 2.0, 0.40, 'gw_har', ?, 9, "
            "'gto_correct')"), (tid, float(i)))
    conn.commit()
    conn.close()


_semear()


def _ids_do_escopo(escopo):
    """Os `tournament_id` que o escopo seleciona, pelo WHERE que o construtor devolve."""
    onde, params = _build_tournament_filter(UID, 90, escopo)
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(
            "SELECT tournament_id FROM tournaments t WHERE %s ORDER BY tournament_id" % onde),
            params).fetchall()
        return sorted(r['tournament_id'] for r in rows)
    finally:
        conn.close()


# -- 1. ULTIMAS X MAOS -----------------------------------------------------------------------
#
# 250 maos com torneios de 100: entram E10, E09 e E08 (o acumulado ANTES de E08 e 200, que ainda
# e menor que 250). O torneio que CRUZA o teto entra INTEIRO, de proposito -- cortar mao no meio
# de um torneio quebraria o modelo, porque toda tela soma por torneio. Entao vem 300 maos para um
# pedido de 250, e passar e melhor que devolver menos do que o jogador pediu.
_de_250 = _ids_do_escopo({'tipo': 'maos', 'n': 250})
check(_de_250 == ['E08', 'E09', 'E10'], 'maos=250 deveria pegar os tres mais recentes: %s' % _de_250)
check(_ids_do_escopo({'tipo': 'maos', 'n': 100}) == ['E10'],
      'maos=100 deveria pegar SO o mais recente')

# o teto: pedir mais que o teto nao pode virar consulta sem limite
_, params_teto = _build_tournament_filter(UID, 90, {'tipo': 'maos', 'n': 999999})
check(params_teto[-1] == TETO_DE_MAOS_DO_ESCOPO,
      'o teto de maos nao foi aplicado: %s' % (params_teto,))
check(TETO_DE_MAOS_DO_ESCOPO == 30000, 'o teto de maos mudou sem ninguem pedir')

# e o eixo e o de JOGO: com o `imported_at` invertido no semeador, o eixo errado devolveria E01
check('E01' not in _de_250, 'o escopo de maos voltou a usar o eixo do UPLOAD')


# -- 2. FAIXA DE DATA ------------------------------------------------------------------------
#
# E01..E10 foram jogados de 02/01 a 11/01. A faixa 04/01..06/01 tem de trazer E03, E04 e E05, e o
# dia final entra INTEIRO (o torneio jogado no dia 6 conta), que e o que o jogador espera de
# "de 04 a 06".
_faixa = _ids_do_escopo({'tipo': 'periodo', 'de': '2026-01-04', 'ate': '2026-01-06'})
check(_faixa == ['E03', 'E04', 'E05'], 'a faixa de data trouxe o conjunto errado: %s' % _faixa)
check(_ids_do_escopo({'tipo': 'periodo', 'de': '2026-01-10'}) == ['E09', 'E10'],
      'so com `de`, a faixa deveria ir do dia 10 em diante')
check(_ids_do_escopo({'tipo': 'periodo', 'ate': '2026-01-03'}) == ['E01', 'E02'],
      'so com `ate`, a faixa deveria ir ate o dia 3')
check(MESES_MAXIMOS_DO_ESCOPO == 12, 'o teto de meses mudou sem ninguem pedir')


# -- 3. O LEGADO NAO MUDOU -------------------------------------------------------------------
#
# CONTROLE: sem isto, um construtor que devolvesse HISTORICO para tudo passaria verde em todos os
# casos acima.
_todos = sorted('E%02d' % i for i in range(1, N_TORNEIOS + 1))
check(_ids_do_escopo(0) == _todos, '`0` deixou de ser historico genuino')
check(_ids_do_escopo(3) == ['E08', 'E09', 'E10'], '`3` deixou de ser os tres ultimos torneios')
check(len(_ids_do_escopo({})) == N_TORNEIOS,
      'dict vazio deveria cair em historico, e nao em zero linhas')


# -- 4. A VARREDURA: o tipo alargado alcanca TODAS as funcoes --------------------------------
#
# Por INTROSPECCAO, e nao por lista: a casa tem a cicatriz da varredura que enumerava os arquivos
# que eu tinha na cabeca enquanto o terceiro quebrava na tela do dono.
_ESCOPOS = ({'tipo': 'maos', 'n': 250},
            {'tipo': 'periodo', 'de': '2026-01-04', 'ate': '2026-01-06'})

#: Argumentos que a varredura sabe preencher. O que nao esta aqui vira PULADA declarada.
_ARGS_PLAUSIVEIS = {
    'days': 90,
    'street': 'preflop',
    'action_taken': 'call',
    'best_action': 'raise',
    'position': 'BTN',
    'stack_band': None,
    # `three_bet` e nao `vpip`: o `_DETALHE` so tem detalhe para dois stats, e o `KeyError` de um
    # stat invalido e do endpoint validar, nao desta varredura.
    'stat': 'three_bet',
    'tipo': 'rfi',
}

alcancadas = []
puladas = []
quebradas = []
for nome, fn in sorted(vars(repo).items()):
    if not (inspect.isfunction(fn) and fn.__module__ == repo.__name__):
        continue
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        continue
    if 'last_n' not in sig.parameters:
        continue
    faltando = [p.name for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
                and p.name not in ('user_id', 'last_n', 'self')
                and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
    # O que a funcao exige alem do escopo, preenchido com valor plausivel: cada argumento que eu
    # NAO sei preencher e uma funcao fora da varredura, e varredura com furo e o defeito que ela
    # deveria achar. Sobra o que pede recorte de assento, e isso fica declarado abaixo.
    extras = {}
    nao_sei = []
    for arg in faltando:
        if arg in _ARGS_PLAUSIVEIS:
            extras[arg] = _ARGS_PLAUSIVEIS[arg]
        else:
            nao_sei.append(arg)
    if nao_sei:
        puladas.append('%s (exige %s)' % (nome, ','.join(nao_sei)))
        continue
    for escopo in _ESCOPOS:
        try:
            fn(UID, last_n=escopo, **extras)
        except Exception as e:
            quebradas.append('%s com %s -> %s: %s'
                             % (nome, escopo.get('tipo'), type(e).__name__, e))
            break
    else:
        alcancadas.append(nome)

print('  varredura: %d funcoes chamadas com escopo de dict, %d puladas, %d quebradas'
      % (len(alcancadas), len(puladas), len(quebradas)))
for _p in puladas:
    print('     PULADA  %s' % _p)
for _q in quebradas:
    print('     QUEBROU %s' % _q)

check(not quebradas, '%d funcoes quebraram com escopo de dict' % len(quebradas))
# CONTROLE da propria varredura: sem ele, um filtro de introspeccao que nao achasse nada passaria
# verde com zero funcoes alcancadas.
check(len(alcancadas) >= 15,
      'a varredura alcancou so %d funcoes: o filtro de introspeccao quebrou' % len(alcancadas))


# -- 4b. NENHUM endpoint le o `last_n` da query por fora do helper ---------------------------
#
# A varredura que achou um furo real: `/player/ev-summary` lia `request.args.get('last_n')` direto,
# entao as duas dimensoes novas NAO chegavam naquele card -- o jogador escolheria "ultimas 5.000
# maos" e o EV continuaria nos 50 torneios do default, sem nada na tela dizendo.
#
# Le o FONTE de proposito: o defeito nao aparece em nenhuma chamada, ele aparece na ausencia de
# uma. Um endpoint novo que copie a linha cai aqui.
_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api', 'app.py')
with open(_APP, encoding='utf-8') as _f:
    _fonte_app = _f.read()
_leituras = _fonte_app.count("request.args.get('last_n')") + _fonte_app.count('request.args.get("last_n")')
check(_leituras == 1,
      '%d lugares leem `last_n` da query: so o helper pode, senao o escopo novo nao os alcanca'
      % _leituras)
# CONTROLE: se o nome do parametro mudar, a contagem acima passaria a valer zero e o guarda
# viraria decoracao.
check("request.args.get('last_n')" in _fonte_app,
      'o parametro HTTP mudou de nome: este guarda precisa ser reescrito')


# -- 4c. Os TETOS batem entre servidor e tela ------------------------------------------------
#
# Os dois numeros vivem nas duas linguagens, e divergir seria calado: a tela ofereceria uma faixa
# que o servidor apara sem avisar, e o jogador veria um numero que nao corresponde ao que pediu.
# Mesmo padrao do guarda dos rotulos de posicao: le o arquivo do outro lado.
# `escopo.ts` e nao `api.ts`: as constantes sairam do modulo de rede em 18/09, porque quem mocka a
# API perdia as constantes junto ("No TETO_DE_MAOS_DO_ESCOPO export is defined on the @/lib/api
# mock"). Constante e tipo nao sao chamada de rede.
_API_TS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       '..', 'frontend', 'src', 'lib', 'escopo.ts')
_API_TS = os.path.abspath(_API_TS)
check(os.path.exists(_API_TS), 'nao achei o escopo.ts do front: %s' % _API_TS)
if os.path.exists(_API_TS):
    import re

    with open(_API_TS, encoding='utf-8') as _f:
        _ts = _f.read()
    _m_maos = re.search(r'TETO_DE_MAOS_DO_ESCOPO\s*=\s*(\d+)', _ts)
    _m_meses = re.search(r'MESES_MAXIMOS_DO_ESCOPO\s*=\s*(\d+)', _ts)
    check(_m_maos is not None and int(_m_maos.group(1)) == TETO_DE_MAOS_DO_ESCOPO,
          'teto de maos divergiu: front %s, servidor %s'
          % (_m_maos.group(1) if _m_maos else None, TETO_DE_MAOS_DO_ESCOPO))
    check(_m_meses is not None and int(_m_meses.group(1)) == MESES_MAXIMOS_DO_ESCOPO,
          'teto de meses divergiu: front %s, servidor %s'
          % (_m_meses.group(1) if _m_meses else None, MESES_MAXIMOS_DO_ESCOPO))


# -- 5. Ponta a ponta: o ev_summary responde ao escopo novo -----------------------------------
#
# Cada torneio i tem UMA decisao de ev_loss_bb = i. Historico = 1..10 = 55. Ultimas 250 maos = os
# tres ultimos = 8+9+10 = 27.
r_hist = get_ev_summary(UID, last_n=0)
r_maos = get_ev_summary(UID, last_n={'tipo': 'maos', 'n': 250})
r_faixa = get_ev_summary(UID, last_n={'tipo': 'periodo', 'de': '2026-01-04', 'ate': '2026-01-06'})
check(bool(r_hist) and bool(r_maos), 'o ev_summary nao respondeu')
# Os numeros sao EXATOS, e nao "menor que": a soma conhecida e o que separa "cortou" de "cortou o
# pedaco certo". Um filtro que pegasse os tres PRIMEIROS torneios tambem daria "menor".
check(r_hist['total_loss_bb'] == 55.0, 'historico deveria somar 1..10 = 55: %s' % r_hist['total_loss_bb'])
check(r_maos['total_loss_bb'] == 27.0,
      'ultimas 250 maos deveriam somar 8+9+10 = 27: %s' % r_maos['total_loss_bb'])
check(r_faixa['total_loss_bb'] == 12.0,
      'a faixa 04-06/01 deveria somar 3+4+5 = 12: %s' % r_faixa['total_loss_bb'])

print('\n' + '=' * 50)
print('Total: %d | Passed: %d | Failed: %d' % (passed + failed, passed, failed))
sys.exit(1 if failed else 0)
