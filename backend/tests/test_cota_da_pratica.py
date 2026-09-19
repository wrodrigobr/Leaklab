# -*- coding: utf-8 -*-
"""test_cota_da_pratica.py - o Free treina no Pratica com 2 mesas e 30 spots por mes.

── O pedido (18/09) ─────────────────────────────────────────────────────────────────────────

O dono: "o modo pratica pode ser liberado para plano free, mas eu quero que eles tenham uma
limitacao de apenas 2 mesas simultaneas e no maximo 30 spots por mes... e isto precisa ficar
explicito pra eles na tela".

── O que este arquivo cobra, e por que cada parte ───────────────────────────────────────────

1. **A conta pura** (mes, renovacao, clamp de mesas). Barata, e pega o virar do ano.
2. **O FILTRO do mes contra o banco.** A pegadinha e de dialeto: `criado_em >= ?` roda cru nos
   dois bancos, e um `CAST(... AS TIMESTAMP)` quebraria SO no SQLite (afinidade NUMERIC faria
   '2026-09-01' virar 2026, comparacao sempre falsa, cota sempre zerada). Sem um caso que grava
   mao de mes ANTERIOR, um filtro quebrado passa verde: a contagem do mes corrente estaria
   certa por acidente.
3. **Os dois portoes, pelo COMPORTAMENTO do endpoint** e nao por leitura de fonte. O teto de
   mesas tem de valer com o cliente MENTINDO (`n=4` no POST), e o `/grade` tem de recusar mesmo
   sem ninguem ter pedido mesa -- ele e o unico que gasta cota de verdade.
4. **A varredura por declaracao** do `PLAN_LIMITS`: todo plano carrega as duas chaves novas. Uma
   lista escrita a mao aqui envelheceria no dia em que nascesse o terceiro plano.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("  FAIL: %s" % msg)


# ── 1. A conta pura ──────────────────────────────────────────────────────────────────────────
from leaklab.cota_da_pratica import (inicio_do_mes, renovacao, teto_de_mesas, mesas_permitidas)

check(inicio_do_mes(date(2026, 9, 18)) == '2026-09-01 00:00:00',
      'corte do mes errado: %r' % inicio_do_mes(date(2026, 9, 18)))
check(inicio_do_mes(date(2026, 1, 1)) == '2026-01-01 00:00:00', 'corte no dia 1 do mes')
check(renovacao(date(2026, 9, 18)) == '2026-10-01', 'renovacao errada: %r' % renovacao(date(2026, 9, 18)))
# o virar do ano, que e onde este tipo de conta costuma morrer
check(renovacao(date(2026, 12, 31)) == '2027-01-01',
      'dezembro nao virou para janeiro do ano seguinte: %r' % renovacao(date(2026, 12, 31)))
# e a coerencia entre os dois: a renovacao e exatamente o corte do mes seguinte
check(renovacao(date(2026, 9, 18)) + ' 00:00:00' == inicio_do_mes(date(2026, 10, 5)),
      'a promessa da tela (renova_em) nao bate com o corte usado na contagem')

from leaklab.pratica_preflop import MAX_MESAS

check(teto_de_mesas(2) == 2, 'teto do free deixou de ser 2')
check(teto_de_mesas(None) == MAX_MESAS, 'sem teto deveria cair no MAX_MESAS do modo')
check(teto_de_mesas(99) == MAX_MESAS, 'teto de plano acima do modo tinha de ser aparado')
check(mesas_permitidas(4, 2) == 2, 'o clamp nao aparou 4 mesas para 2')
check(mesas_permitidas(1, 2) == 1, 'pedir 1 mesa com teto 2 devolveu outra coisa')
for lixo in (None, 0, -5, 'abc', '', {}):
    check(mesas_permitidas(lixo, 2) == 1, 'entrada invalida %r devia cair em 1 mesa' % (lixo,))


# ── 2. O filtro do mes, contra o banco ───────────────────────────────────────────────────────
#
# Banco do AMBIENTE (decisao do dono, 19/09: "nao quero mais testar em sqlite"). A versao
# anterior deste arquivo trocava `schema.get_conn` por um `sqlite3.connect` e, por construcao,
# NUNCA rodava em Postgres -- o dialeto do filtro de data (a pegadinha central deste arquivo)
# ficava sem prova no banco que producao usa.
from banco_de_teste import banco_de_teste, rotulo

print("banco: %s" % rotulo())

UID = 987654321          # id alto: em Postgres o banco e COMPARTILHADO entre rodadas e suites
_ctx = banco_de_teste(limpar=('pratica_maos',), user_id=UID)
_ctx.__enter__()

import leaklab.historico_de_pratica as H

H._CRIADA = False
SPOT = {'hand': 'AKs', 'position': 'BTN', 'vs_position': None, 'stack_bb': 50, 'scenario': 'rfi'}
GRADE = {'best_action': 'raise', 'nivel': 'otima', 'ev_loss_bb': 0.0, 'is_correct': True}

for _ in range(3):
    H.gravar(UID, SPOT, 'raise', GRADE)

check(H.contagem_desde(UID, inicio_do_mes()) == 3,
      'as 3 maos do mes corrente nao foram contadas: %r' % H.contagem_desde(UID, inicio_do_mes()))

# A mao de um mes ANTERIOR nao pode entrar. Sem este caso, filtro quebrado passa verde.
#
# `_adapt` e obrigatorio: em Postgres ele troca `?` por `%s`, e sem isso o INSERT estoura. E o
# `criado_em` vai como STRING crua de proposito -- e exatamente o caminho que o produto usa em
# `contagem_desde`, e o que prova que a comparacao de data funciona nos dois dialetos.
from database.schema import get_conn as _gc_real
from database.repositories import _adapt as _ad

_conn = _gc_real()
_conn.execute(
    _ad("INSERT INTO pratica_maos (user_id, mao, acao, criado_em) VALUES (?,?,?,?)"),
    (UID, 'QQ', 'raise', '2020-01-15 10:00:00'))
_conn.commit()
_conn.close()

check(H.contagem_desde(UID, inicio_do_mes()) == 3,
      'a mao de 2020 entrou na cota DESTE mes (o filtro de data nao esta filtrando)')
# controle: sem corte, ela existe -- prova que a linha foi gravada e que a contagem a ACHARIA
check(H.contagem_desde(UID, '1970-01-01 00:00:00') == 4,
      'a mao antiga nao esta na tabela, logo o caso acima passou por ausencia de dado')
# e o vizinho do outro lado: a cota de OUTRO jogador nao e a dele
check(H.contagem_desde(UID + 1, '1970-01-01 00:00:00') == 0, 'a contagem vazou entre usuarios')


# ── 3. Os dois portoes, pelo comportamento do endpoint ───────────────────────────────────────
from api.app import app

app.config['TESTING'] = True
c = app.test_client()

r = c.post('/auth/register', json={'username': 'cotapratica', 'email': 'cota@pratica.test',
                                   'password': 'pass1234'}, content_type='application/json')
_tok = (r.get_json() or {}).get('token', '')
if not _tok:
    r = c.post('/auth/login', json={'email': 'cota@pratica.test', 'password': 'pass1234'},
               content_type='application/json')
    _tok = (r.get_json() or {}).get('token', '')
HDR = {'Authorization': 'Bearer %s' % _tok, 'Content-Type': 'application/json'}
check(bool(_tok), 'nao consegui autenticar o usuario de teste')

_me = c.get('/auth/me', headers=HDR).get_json() or {}
_uid = _me.get('user_id')
check(_me.get('plan') == 'free', 'o usuario de teste nao e free: %r' % _me.get('plan'))
check(_me.get('practice_spots_used') == 0,
      'o contador do /auth/me nao comecou em zero: %r' % _me.get('practice_spots_used'))
check((_me.get('plan_limits') or {}).get('practice_tables') == 2,
      'o /auth/me nao entrega o teto de 2 mesas para a tela')
check((_me.get('plan_limits') or {}).get('practice_spots_per_month') == 30,
      'o /auth/me nao entrega o teto de 30 spots para a tela')

# PORTAO 1: o cliente MENTE e pede 4 mesas. O servidor apara para 2.
r = c.post('/player/practice/tables', json={'n': 4}, headers=HDR)
d = r.get_json() or {}
check(r.status_code == 200, '/tables respondeu %s' % r.status_code)
check(d.get('pedidas') == 2, 'o servidor aceitou 4 mesas de um free: pedidas=%r' % d.get('pedidas'))
check(len(d.get('tables') or []) <= 2, 'vieram %d mesas para um free' % len(d.get('tables') or []))
check((d.get('cota') or {}).get('spots_limite') == 30, 'a cota nao veio na resposta do /tables')
check((d.get('cota') or {}).get('mesas') == 2, 'a cota nao declara o teto de mesas')

# PORTAO 1b: as mesas tambem nao passam dos spots que RESTAM.
#
# Este caso nasceu de uma guarda que passou verde quando eu a quebrei de proposito: o clamp pelos
# restantes existia no codigo e nada o cobrava. Sem ele, o jogador com 1 spot sobrando abre 2
# mesas e a segunda e recusada com a mao ja na tela -- a cota chegando como erro em vez de limite.
for _ in range(29):
    H.gravar(_uid, SPOT, 'raise', GRADE)

r = c.post('/player/practice/tables', json={'n': 2}, headers=HDR)
d = r.get_json() or {}
check(d.get('pedidas') == 1,
      'com 1 spot restando o servidor montou %r mesas' % d.get('pedidas'))
check(len(d.get('tables') or []) <= 1,
      'com 1 spot restando vieram %d mesas' % len(d.get('tables') or []))
check((d.get('cota') or {}).get('spots_restantes') == 1,
      'restantes devia ser 1: %r' % (d.get('cota') or {}).get('spots_restantes'))
check((d.get('cota') or {}).get('esgotado') is False, 'com 1 restante nao esta esgotado')

# PORTAO 2: com o mes esgotado, /tables devolve vazio e /grade RECUSA.
H.gravar(_uid, SPOT, 'raise', GRADE)

_me2 = c.get('/auth/me', headers=HDR).get_json() or {}
check(_me2.get('practice_spots_used') == 30,
      'o contador do /auth/me nao acompanhou as 30 maos: %r' % _me2.get('practice_spots_used'))

r = c.post('/player/practice/tables', json={'n': 2}, headers=HDR)
d = r.get_json() or {}
check(r.status_code == 200, '/tables com cota esgotada devolveu %s (tinha de ser 200)' % r.status_code)
check(d.get('tables') == [], 'com a cota esgotada ainda vieram mesas: %r' % (d.get('tables'),))
check((d.get('cota') or {}).get('esgotado') is True, 'a resposta nao declara a cota esgotada')
check((d.get('cota') or {}).get('spots_restantes') == 0, 'restantes devia ser 0')

r = c.post('/player/practice/grade', json={'spot': SPOT, 'action': 'raise'}, headers=HDR)
check(r.status_code == 403, 'o /grade aceitou corrigir com a cota esgotada (%s)' % r.status_code)
check((r.get_json() or {}).get('erro') == 'cota_esgotada',
      'o /grade nao devolveu o codigo que a tela usa para distinguir cota de falha')


# ── 4. Varredura por declaracao do PLAN_LIMITS ───────────────────────────────────────────────
from database.repositories import PLAN_LIMITS

for nome, lim in PLAN_LIMITS.items():
    check('practice_tables' in lim, 'plano %r sem `practice_tables`' % nome)
    check('practice_spots_per_month' in lim, 'plano %r sem `practice_spots_per_month`' % nome)
check(PLAN_LIMITS['free']['practice_tables'] == 2, 'o free deixou de ter 2 mesas')
check(PLAN_LIMITS['free']['practice_spots_per_month'] == 30, 'o free deixou de ter 30 spots')
check(PLAN_LIMITS['pro']['practice_tables'] is None, 'o pro ganhou teto de mesas')
check(PLAN_LIMITS['pro']['practice_spots_per_month'] is None, 'o pro ganhou teto de spots')

_ctx.__exit__(None, None, None)      # limpa o que o teste sujou (em Postgres o banco e o mesmo)

print("\n" + "=" * 50)
print("Total: %d | Passed: %d | Failed: %d" % (passed + failed, passed, failed))
sys.exit(1 if failed else 0)
