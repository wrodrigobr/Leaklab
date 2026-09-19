# -*- coding: utf-8 -*-
"""O reparo do assento antigo consome sobra, e NUNCA faz o solver gastar dinheiro.

── O pedido (19/09) ─────────────────────────────────────────────────────────────────────────

O dono: "pode criar uma rotina de resolve de spots antigos incluindo 300 spots sempre que o
solver estiver ocioso". E, logo depois, as duas restricoes que definem o desenho: "**quero usar o
solver ocioso, mas nao quero disparar novos solvers**... e estes spots tem que entrar com a
**menor prioridade possivel**, pq se entrar um torneio de um jogador, eles devem ser
despriorizados".

── As tres coisas que este arquivo trava ────────────────────────────────────────────────────

1. **Prioridade de PORAO.** O lote entra em 0, abaixo ate do lote de import (1), e a fila ordena
   por `priority DESC`. Spot de jogador (5 a 18) e servido primeiro, sempre.

2. **O burst NAO conta o porao.** Esta e a que protege o bolso. `burst_do_solver._pending()`
   decide criar um servidor cobrado por hora na Hetzner quando a fila passa de 400. Contar o
   reparo ali faria trabalho de fundo, que nao tem ninguem esperando, subir um box pago -- o
   oposto do pedido. O caso varre o SQL do script: guarda estrutural, porque o defeito nao seria
   de logica, seria alguem mexer naquela consulta sem saber desta regra.

3. **Desligado por padrao.** Trabalho de fundo que consome recurso compartilhado nao comeca
   sozinho num deploy. Mesma doutrina do win-back.
"""
import os
import re
import sys

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


from banco_de_teste import banco_de_teste, rotulo

print("banco: %s" % rotulo())
# Banco do AMBIENTE, e ISOLADO: os casos do item 6 e 7 chamam `enfileirar_lote()` de verdade, que
# ENFILEIRA e marca torneio como feito. A primeira versao rodava contra o banco de dev e sujava
# ele -- teste que escreve fora do proprio banco e defeito, nao detalhe.
_ctx = banco_de_teste(limpar=('gto_solver_queue', 'reparo_assento_torneios'))
_ctx.__enter__()

from leaklab.reparo_do_assento import (PRIORIDADE_DO_PORAO, TETO_POR_LOTE, ligado, _stmts)
from leaklab.gto_solver import _priority

# ── 1. O porao e o piso ─────────────────────────────────────────────────────────────────────
check(PRIORIDADE_DO_PORAO == 0, 'o porao deixou de ser 0: %r' % PRIORIDADE_DO_PORAO)
check(TETO_POR_LOTE == 300, 'o teto por lote deixou de ser os 300 que o dono pediu: %r' % TETO_POR_LOTE)

# Todo spot com dono esperando fica ACIMA do porao. Varre as streets pelos dois planos, em vez
# de conferir um caso: plano novo ou street nova nao passa despercebida.
for street in ('preflop', 'flop', 'turn', 'river'):
    for plano in (None, 'free', 'pro'):
        p = _priority(street, plano)
        check(p > PRIORIDADE_DO_PORAO,
              'spot organico (%s/%s) ficou <= porao: %r' % (street, plano, p))

# E o lote de IMPORT, que ja era o porao antigo, tambem fica acima deste.
os.environ['LEAKLAB_IMPORT_LOTE'] = '1'
try:
    p_lote = _priority('flop', None)
finally:
    del os.environ['LEAKLAB_IMPORT_LOTE']
check(p_lote > PRIORIDADE_DO_PORAO,
      'o lote de import (%r) devia ficar acima do reparo (%r)' % (p_lote, PRIORIDADE_DO_PORAO))


# ── 2. O BURST nao conta o porao (a guarda do bolso) ────────────────────────────────────────
_BURST = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'burst_do_solver.py')
fonte = open(_BURST, encoding='utf-8').read()
m = re.search(r'def _pending\(\).*?\n(?=\ndef |\Z)', fonte, re.S)
check(m is not None, 'nao achei `_pending()` no script do burst')
if m:
    corpo = m.group(0)
    # A DOCSTRING sai antes da varredura.
    #
    # A primeira versao desta guarda procurava `priority > 0` no corpo inteiro e PASSOU VERDE
    # quando eu tirei o corte do SQL de proposito -- porque a propria docstring da funcao explica
    # a regra e contem aquele texto. O comentario satisfazia o teste. Regra 8 da casa, cometida
    # dentro do arquivo que existe para aplicar as regras da casa.
    corpo_sem_doc = re.sub(r'"""LEAKLAB_DOC"""', '', re.sub(r'""".*?"""', '"""LEAKLAB_DOC"""',
                                                            corpo, flags=re.S))
    check('gto_solver_queue' in corpo_sem_doc, 'o `_pending()` mudou de tabela: revisar esta guarda')
    check(re.search(r"priority\s*>\s*0", corpo_sem_doc) is not None,
          'o `_pending()` do burst voltou a contar TODA a fila: o reparo de assento passaria a '
          'disparar um servidor COBRADO. Ver o pedido do dono em 19/09.')
    # CONTROLE: a remocao da docstring tem de ter acontecido de verdade, senao o caso acima
    # volta a ser satisfeito pelo comentario sem ninguem perceber.
    check('Por que' not in corpo_sem_doc,
          'CONTROLE: a docstring NAO foi removida do corpo varrido, entao a guarda acima pode '
          'estar sendo satisfeita pelo proprio comentario')

# O controle: a regra do burst continua sendo a que gasta dinheiro, entao ela tem de existir.
from leaklab.burst_solver import decidir, PENDING_ALTO
d = decidir(pending=PENDING_ALTO, bursts_ativos=0)
check(d.acao == 'subir', 'a regra de burst nao sobe mais com a fila alta: %r' % d.acao)
d2 = decidir(pending=TETO_POR_LOTE, bursts_ativos=0)
check(d2.acao != 'subir',
      'um lote de %d spots sozinho ja faria o burst subir (alto=%d). O corte por prioridade no '
      '`_pending()` e a unica protecao, e ela precisa continuar valendo.' % (TETO_POR_LOTE, PENDING_ALTO))


# ── 3. Desligado por padrao ─────────────────────────────────────────────────────────────────
_antes = os.environ.pop('REPARO_ASSENTO_ENABLED', None)
try:
    check(ligado() is False, 'o reparo veio LIGADO por padrao')
    for v in ('1', 'true', 'YES'):
        os.environ['REPARO_ASSENTO_ENABLED'] = v
        check(ligado() is True, 'REPARO_ASSENTO_ENABLED=%r devia ligar' % v)
    for v in ('0', 'false', '', 'nao'):
        os.environ['REPARO_ASSENTO_ENABLED'] = v
        check(ligado() is False, 'REPARO_ASSENTO_ENABLED=%r NAO devia ligar' % v)
finally:
    os.environ.pop('REPARO_ASSENTO_ENABLED', None)
    if _antes is not None:
        os.environ['REPARO_ASSENTO_ENABLED'] = _antes


# ── 4. O gatilho esta no ramo da fila VAZIA, e passa a prioridade do porao ──────────────────
#
# Guarda estrutural: o valor de chamar isto com fila cheia nao apareceria em teste de unidade,
# e o defeito seria "alguem moveu a chamada duas linhas acima".
_APP = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
app_src = open(_APP, encoding='utf-8').read()
loop = app_src[app_src.index('def _solver_queue_worker_loop'):]
loop = loop[:loop.index("\nif __name__ == '__main__':")]
i_continua = loop.find('continue   # re-checa J')
# Ancora em `enfileirar_lote`, e NAO no nome do modulo: o loop tambem importa
# `marcar_atividade_organica` do mesmo modulo, e mais acima. Ancorar no modulo faria esta guarda
# apontar para o import e acusar em falso -- foi o que aconteceu ao escrever a regra da carona.
i_reparo = loop.find('enfileirar_lote()')
check(i_continua > 0 and i_reparo > 0, 'nao achei o ramo de drenagem ou a chamada do lote')
if i_continua > 0 and i_reparo > 0:
    check(i_reparo > i_continua,
          'a chamada do lote esta ANTES do `continue` da drenagem: ela rodaria com a fila cheia')
check('_reparo_ligado()' in loop, 'o gatilho do reparo nao confere a flag')

check('prioridade=PRIORIDADE_DO_PORAO' in
      open(os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'reparo_do_assento.py'),
           encoding='utf-8').read(),
      'o lote deixou de enfileirar no porao')

# E o enfileirador do app aceita a prioridade explicita (senao o lote cairia no calculo normal,
# e um spot de reparo entraria empatado com o de um jogador).
check('prioridade: int = None' in app_src,
      'o `_enfileirar_spot_da_decisao` perdeu o parametro de prioridade')


# ── 5. A DDL da tabela de progresso roda nas duas gramaticas ───────────────────────────────
for pg in (True, False):
    sqls = _stmts(pg)
    check(len(sqls) == 1 and 'reparo_assento_torneios' in sqls[0],
          'DDL do progresso faltando para postgres=%s' % pg)
    check('SERIAL' not in sqls[0], 'a tabela de progresso nao tem id proprio, nao precisa de SERIAL')

# ── 6. O lote DORME quando nao ha nada, para nao acordar o Neon a cada 60s ─────────────────
#
# O consumidor chama `enfileirar_lote()` a cada 60s com a fila vazia, e a consulta de pendentes
# varre as decisoes pos-flop (o assento vem de um CASE, que nenhum indice cobre). Sem o intervalo,
# o reparo trocaria o box pago do burst por conta de compute no Neon.
import leaklab.reparo_do_assento as RA

check(RA.INTERVALO_SEM_TRABALHO_S >= 3600,
      'o intervalo sem trabalho ficou curto demais (%ss): a varredura voltaria a ser por minuto'
      % RA.INTERVALO_SEM_TRABALHO_S)

_saved = (RA._proxima_varredura, RA._ultima_atividade_organica)
try:
    import time as _t
    RA.marcar_atividade_organica()          # com carona, para isolar o efeito do intervalo
    RA._proxima_varredura = _t.monotonic() + 9999
    r = RA.enfileirar_lote()
    check(r.get('dormindo') is True, 'o lote nao respeitou o intervalo: %r' % r)
    check(r.get('spots') == 0, 'o lote dormindo enfileirou spot: %r' % r)
finally:
    RA._proxima_varredura, RA._ultima_atividade_organica = _saved

# CONTROLE: com o relogio liberado ele NAO diz que esta dormindo. Sem este caso, um
# `enfileirar_lote` que sempre dormisse passaria verde no de cima.
_saved = (RA._proxima_varredura, RA._ultima_atividade_organica)
try:
    RA.marcar_atividade_organica()
    RA._proxima_varredura = 0.0
    r2 = RA.enfileirar_lote()
    check(r2.get('dormindo') is not True,
          'CONTROLE: o lote se diz dormindo mesmo com o relogio liberado')
finally:
    RA._proxima_varredura, RA._ultima_atividade_organica = _saved


# ── 7. A CARONA: sem jogador por perto, o reparo NAO acorda o Neon ─────────────────────────
#
# Pedido do dono (19/09): "nao podemos deixa-lo ligado, vai gerar um custo alto". O intervalo do
# item 6 cobre a varredura ociosa; esta regra cobre o resto -- enquanto o reparo RODA, ele
# manteria o banco acordado por horas se nada o segurasse.
check(RA.JANELA_DE_CARONA_S <= 3600,
      'a janela de carona ficou larga demais (%ss): o reparo rodaria muito depois de o banco ter '
      'esfriado' % RA.JANELA_DE_CARONA_S)

_saved = (RA._proxima_varredura, RA._ultima_atividade_organica)
try:
    RA._ultima_atividade_organica = 0.0     # ninguem por perto desde o inicio do processo
    RA._proxima_varredura = 0.0
    check(RA.pode_pegar_carona() is False, 'sem atividade organica ele acha que pode pegar carona')
    r3 = RA.enfileirar_lote()
    check(r3.get('sem_carona') is True, 'o lote rodou sem carona: %r' % r3)
    check(r3.get('spots') == 0, 'o lote sem carona enfileirou spot: %r' % r3)
    # E a marca ABRE a janela — controle que prova que o caso acima falha pelo motivo certo.
    RA.marcar_atividade_organica()
    check(RA.pode_pegar_carona() is True, 'a marca de atividade organica nao abriu a carona')
finally:
    RA._proxima_varredura, RA._ultima_atividade_organica = _saved

# A ancora e a atividade ORGANICA, nunca a do proprio reparo: senao o lote se auto-sustenta.
# Guarda estrutural no loop do consumidor, porque o defeito seria marcar no lugar errado.
i_org = loop.find('marcar_atividade_organica')
i_prio = loop.find('priority > 0')
check(i_org > 0 and i_prio > 0, 'o loop nao marca atividade organica, ou nao filtra por prioridade')
if i_org > 0 and i_prio > 0:
    check(i_prio < i_org,
          'a marca de atividade organica nao vem do filtro por prioridade: o reparo se '
          'auto-sustentaria')

_ctx.__exit__(None, None, None)

print("\n" + "=" * 50)
print("Total: %d | Passed: %d | Failed: %d" % (passed + failed, passed, failed))
sys.exit(1 if failed else 0)
