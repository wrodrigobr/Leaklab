# -*- coding: utf-8 -*-
"""O solver guarda e procura o spot pelo ASSENTO EFETIVO, e a chave antiga continua achando.

── O caso (AY-29, corrigido em 19/09) ───────────────────────────────────────────────────────

A sala chama de "UTG" tanto quem tem 8 jogadores atras (mesa 9) quanto quem tem 5 (mesa 6). Quem
decide como se joga e o segundo numero: o "UTG" de mesa 6 abre como o LJ de mesa 9 (24,7% contra
16,4% em 30bb). O solver guardava e resolvia pelo NOME, e producao e 45% mesa 8, 28% mesa 7, 12%
mesa 6 e so 5% mesa 9.

Medido no solver de PRODUCAO, 10 spots: a recomendacao se desloca ~10 pontos percentuais em media
(maximo 21,7), e em 1 de 10 a acao recomendada troca. O veredito quase nao muda (2 em 1.431)
porque a regua tem faixas largas -- mas a PORCENTAGEM que o jogador le erra por esse tanto.

── As duas coisas que este arquivo trava ────────────────────────────────────────────────────

1. **A traducao e COMPLETA.** Traduzir so a posicao do heroi produz um payload PIOR do que nao
   traduzir: `opener` e `threebettor` sao rotulos de assento no mesmo vocabulario, e
   `resolve_solver_ranges` compara `opener == oop_pos` para decidir quem leva range de abertura.
   Com a traducao pela metade o opener deixa de casar, o ramo troca, e o range capturado (168
   chars) vira o generico (71). Aconteceu numa medicao de 19/09.

   O caso nao ENUMERA os campos: compara o payload inteiro montado com `num_players` contra o
   payload montado ja no dialeto certo. Se algum rotulo ficar por traduzir, os dois diferem.

2. **A chave antiga continua sendo encontrada.** O hash e recalculado NA LEITURA. Trocar o
   assento sem o degrau legado faria toda decisao ja existente calcular uma chave nova, nao achar
   o no dela e ficar SEM VEREDITO -- a familia do bug do board, que passou tres meses gravando
   com uma chave e procurando com outra.
"""
import os
import sqlite3
import sys
import tempfile

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


from leaklab.gto_solver import assento_efetivo, montar_payload_postflop

# ── 1. A traducao em si ──────────────────────────────────────────────────────────────────────
check(assento_efetivo('UTG', 6) == 'LJ', 'UTG de mesa 6 devia virar LJ: %r' % assento_efetivo('UTG', 6))
check(assento_efetivo('UTG', 9) == 'UTG', 'UTG de mesa 9 nao muda: %r' % assento_efetivo('UTG', 9))
check(assento_efetivo('UTG+1', 7) == 'LJ', 'UTG+1 de mesa 7: %r' % assento_efetivo('UTG+1', 7))
check(assento_efetivo('BTN', 6) == 'BTN', 'BTN e BTN em qualquer mesa: %r' % assento_efetivo('BTN', 6))
check(assento_efetivo('BB', 6) == 'BB', 'BB e BB: %r' % assento_efetivo('BB', 6))
# Sem o tamanho da mesa, o comportamento LEGADO: devolve o rotulo cru, sem inventar.
check(assento_efetivo('UTG', None) == 'UTG', 'sem mesa nao traduz')
check(assento_efetivo('UTG', 0) == 'UTG', 'mesa 0 nao traduz')
check(assento_efetivo('utg', 6) == 'LJ', 'minusculo tambem traduz')
check(assento_efetivo('', 6) == '', 'vazio continua vazio')
check(assento_efetivo(None, 6) == '', 'None vira vazio sem estourar')
check(assento_efetivo('UTG', 'lixo') == 'UTG', 'tamanho ilegivel cai no legado, nao estoura')


# ── 2. A traducao e COMPLETA (sem enumerar campos) ───────────────────────────────────────────
#
# Mesa 6: UTG -> LJ. O payload montado com `num_players=6` e os rotulos CRUS tem de ser
# identico ao montado sem `num_players` e com os rotulos JA traduzidos.
BOARD = ['Qh', '7d', '2s']
MAO = ['As', 'Kd']
COMUM = dict(street='flop', board=BOARD, hero_cards=MAO, stack_bb=30.0, facing_bb=0.0,
             pot_bb=6.0, pot_type='', n_ativos=1)

com_mesa = montar_payload_postflop(position='UTG', vs_position='CO', opener='UTG',
                                   threebettor='', num_players=6, **COMUM)
ja_traduzido = montar_payload_postflop(position='LJ', vs_position='CO', opener='LJ',
                                       threebettor='', num_players=None, **COMUM)
check(com_mesa is not None and ja_traduzido is not None, 'o gate recusou o spot do caso')
if com_mesa and ja_traduzido:
    check(com_mesa[0] == ja_traduzido[0],
          'o HASH difere: algum rotulo de assento ficou por traduzir')
    check(com_mesa[1] == ja_traduzido[1],
          'o PAYLOAD difere: algum rotulo de assento ficou por traduzir')

# E o controle: sem a mesa, o payload TEM de ser o legado (diferente do traduzido). Sem este
# caso, uma traducao que nao acontecesse passaria verde nos dois acima.
legado = montar_payload_postflop(position='UTG', vs_position='CO', opener='UTG',
                                 threebettor='', num_players=None, **COMUM)
check(legado is not None, 'o gate recusou o spot legado')
if legado and com_mesa:
    check(legado[0] != com_mesa[0],
          'CONTROLE: com e sem tamanho de mesa deram o MESMO hash, logo nada foi traduzido')

# A direcao do erro: o assento efetivo abre MAIS LARGO. Medido em prod, o range assumido era
# mais estreito que o real em 100% dos casos.
import json as _json
if legado and com_mesa:
    r_legado = _json.loads(legado[1])
    r_novo = _json.loads(com_mesa[1])
    check(r_legado['position'] == 'UTG' and r_novo['position'] == 'LJ',
          'a posicao do payload nao acompanhou a traducao')


# ── 3. O degrau LEGADO da cascata de leitura ────────────────────────────────────────────────
#
# Banco do AMBIENTE. A versao anterior trocava `get_conn` por um `sqlite3.connect` e nunca
# rodava em Postgres -- e este caso e sobre HASH e LEITURA DE NO, que e o que producao faz o dia
# inteiro contra Postgres.
from banco_de_teste import banco_de_teste, rotulo

print("banco: %s" % rotulo())
_ctx = banco_de_teste()
_ctx.__enter__()

from database.repositories import insert_gto_nodes
from leaklab.gto_solver import lookup_gto

# Um no ANTIGO, gravado sob o rotulo da sala (UTG), como todo o acervo de hoje.
insert_gto_nodes([{
    'street': 'flop', 'position': 'UTG', 'board': BOARD, 'hero_hand': MAO,
    'hero_stack_bb': 30.0, 'facing_size_bb': 0.0,
    'gto_action': 'check', 'gto_frequency': 0.8, 'exploitability_pct': 0.5,
    'strategy_json': _json.dumps({'check': 0.8, 'bet_75pct': 0.2}),
    'source': 'solver_cli',
}])

achado = lookup_gto(street='flop', position='UTG', board=BOARD, hero_hand=MAO,
                    hero_stack_bb=30.0, vs_position='CO', facing_size_bb=0.0, pot_bb=6.0,
                    num_players=6, block_remote=True, allow_remote_solve=False)
check(achado.get('found') is True,
      'a decisao ANTIGA perdeu o no dela: o degrau legado nao pegou (%r)' % achado.get('source'))
check(bool(achado.get('strategy')), 'achou o no mas sem estrategia')

# E o spot_hash devolvido (o que o enfileiramento usa) tem de ser o do assento EFETIVO, senao o
# no NOVO nasceria de novo sob a chave velha.
from leaklab.gto_utils import compute_spot_hash
h_efetivo = compute_spot_hash('flop', 'LJ', BOARD, MAO, 30.0, 0.0, '')
h_legado = compute_spot_hash('flop', 'UTG', BOARD, MAO, 30.0, 0.0, '')
check(achado.get('spot_hash') == h_efetivo,
      'o spot_hash devolvido nao e o do assento efetivo: %r' % achado.get('spot_hash'))
check(h_efetivo != h_legado, 'CONTROLE: os dois hashes sao iguais, o caso acima nao prova nada')

# Sem o tamanho da mesa, nada muda para quem ainda nao passa o dado.
antigo = lookup_gto(street='flop', position='UTG', board=BOARD, hero_hand=MAO,
                    hero_stack_bb=30.0, vs_position='CO', facing_size_bb=0.0, pot_bb=6.0,
                    block_remote=True, allow_remote_solve=False)
check(antigo.get('spot_hash') == h_legado,
      'sem num_players o comportamento devia ser o legado: %r' % antigo.get('spot_hash'))

_ctx.__exit__(None, None, None)

print("\n" + "=" * 50)
print("Total: %d | Passed: %d | Failed: %d" % (passed + failed, passed, failed))
sys.exit(1 if failed else 0)
