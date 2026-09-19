# -*- coding: utf-8 -*-
"""O importador do SharkScope, contra o JSON REAL capturado em 19/09.

── O caso ───────────────────────────────────────────────────────────────────────────────────

O dono: "podemos criar um importador com base no json... ela deve ser apenas para uso admin por
enquanto". O buraco que ele fecha esta medido: `buy_in` preenchido em 8,9% dos torneios e `profit`
em 6,7%, e o PartyPoker (que o SharkScope rastreia bem) nao publica summary que saibamos ler.

── As tres armadilhas do formato, e por que cada uma tem caso aqui ─────────────────────────

1. **`@reEntries` NAO e do jogador.** No JSON real ele vale 16, 32, 19 -- sao as re-entradas DO
   TORNEIO. O numero do jogador e `@multientries`. Confundir multiplicaria o custo por vinte, e o
   resultado ainda pareceria plausivel, que e o pior tipo de erro.
2. **Freeroll tem stake zero.** Precisa chegar marcado, senao entra no ROI com denominador falso.
3. **O `@id` e do SharkScope, nao da sala**, entao nao serve de chave de pareamento.

── E a armadilha do MEDIDOR, que eu cometi antes de escrever isto ──────────────────────────

Na primeira comparacao deste JSON com producao eu casei por dia + buy-in, e em dias com DOIS
torneios do mesmo buy-in os pares trocaram: apareceram divergencias que nao existiam no dado. Por
isso o pareamento e por dia + COLOCACAO primeiro, e ha caso abaixo forjando exatamente essa
situacao.
"""
import io
import json
import os
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


from leaklab.importador_sharkscope import normalizar, parear, planejar, ORIGEM, MAIS_CONFIAVEL

# ── O JSON real, reduzido aos campos que o importador le ────────────────────────────────────
#
# Tres torneios do dia 17/09 do MusashiBR, escolhidos de proposito: DOIS deles tem buy-in 1.10 no
# mesmo dia, que e a situacao que quebrou o meu primeiro pareamento.
REAL = {"Response": {"PlayerResponse": {"PlayerView": {"Player": {
    "@name": "MusashiBR", "@network": "PartyPoker",
    "CompletedTournaments": {"Tournament": [
        {"@date": "1789689189", "@stake": "0.5", "@rake": "0.05", "@currency": "USD",
         "@name": "7-Max Deepstack: $50 Gtd", "@network": "PartyPoker", "@totalEntrants": "86",
         "@prizePool": "52.5", "@reEntries": "19", "@gameClass": "scheduled",
         "TournamentEntry": {"@multientries": "1", "@position": "3", "@prize": "5.58"}},
        {"@date": "1789680314", "@stake": "1", "@rake": "0.1", "@currency": "USD",
         "@name": "8-Max Deepstack: $100 Gtd", "@network": "PartyPoker", "@totalEntrants": "92",
         "@prizePool": "110", "@reEntries": "18", "@gameClass": "scheduled",
         "TournamentEntry": {"@position": "5", "@prize": "6.16"}},
        {"@date": "1789660337", "@stake": "1", "@rake": "0.1", "@currency": "USD",
         "@name": "6-Max Deepstack: $100 Gtd", "@network": "PartyPoker", "@totalEntrants": "94",
         "@prizePool": "113", "@reEntries": "19", "@gameClass": "scheduled",
         "TournamentEntry": {"@multientries": "1", "@position": "22", "@prize": "2.08"}},
        {"@date": "1789333758", "@stake": "0", "@rake": "0", "@currency": "USD",
         "@name": "Free To Play - Round The Clock: $100 Gtd", "@network": "PartyPoker",
         "@totalEntrants": "1337", "@prizePool": "101.64", "@gameClass": "scheduled",
         "TournamentEntry": {"@position": "165"}},
    ]}}}}}}

rs = normalizar(REAL)
check(len(rs) == 4, 'deviam sair 4 resultados, sairam %d' % len(rs))
por_pos = {r['colocacao']: r for r in rs}

# ── 1. A conta do buy-in e do lucro ─────────────────────────────────────────────────────────
r3 = por_pos[3]
check(r3['buy_in'] == 0.55, 'buy-in do 3o lugar devia ser stake+rake=0,55: %r' % r3['buy_in'])
check(r3['premio'] == 5.58, 'premio do 3o: %r' % r3['premio'])
check(r3['lucro'] == 5.03, 'lucro devia ser premio-buyin=5,03: %r' % r3['lucro'])
check(r3['field'] == 86, 'field do 3o: %r' % r3['field'])

# A ARMADILHA 1: `@reEntries` daquele torneio e 19. Se ele virasse o custo do jogador, o buy-in
# sairia 0,55 x 19 = 10,45 em vez de 0,55.
check(r3['buy_in'] != round(0.55 * 19, 2),
      'o buy-in usou `@reEntries` (19) em vez de `@multientries`: %r' % r3['buy_in'])
check(r3['entradas'] == 1, 'entradas do jogador deviam ser 1: %r' % r3['entradas'])

# ── 2. Freeroll chega MARCADO ───────────────────────────────────────────────────────────────
free = por_pos[165]
check(free['freeroll'] is True, 'o freeroll nao veio marcado')
check(free['buy_in'] == 0.0 and free['lucro'] == 0.0, 'freeroll com numero estranho: %r' % free)
check(all(not r['freeroll'] for r in rs if r['colocacao'] != 165),
      'torneio pago foi marcado como freeroll')

# ── 3. O pareamento NAO troca os pares no dia com dois buy-ins iguais ──────────────────────
#
# Este e o caso que existe por causa de um erro meu. Os dois torneios de 1,10 do dia 17/09 tem
# premios e colocacoes diferentes; casar por dia+buy-in pega o primeiro da lista e erra.
#
# A ORDEM desta lista importa, e ela reproduz a de producao: o torneio SEM colocacao gravada vem
# PRIMEIRO. Com o pareamento por buy-in na frente, o 5o lugar casaria com ele (2280) e o 22o
# sobraria para o 2287 -- os dois trocados, exatamente o que aconteceu comigo. Com a lista na
# ordem "certinha", a resposta sai correta por SORTE e a guarda nao prova nada: foi o que
# aconteceu na primeira versao deste arquivo, e ela passou verde ao quebrar a ordem de proposito.
NOSSOS = [
    {'id': 2280, 'tournament_id': 'T-2280', 'played_at': '2026-09-17 15:52:00',
     'buy_in': 1.1, 'prize': None, 'place': None, 'financeiro_origem': None},
    {'id': 2287, 'tournament_id': 'T-2287', 'played_at': '2026-09-17 21:25:00',
     'buy_in': 1.1, 'prize': 6.16, 'place': 5, 'financeiro_origem': None},
    {'id': 2289, 'tournament_id': 'T-2289', 'played_at': '2026-09-17 23:53:00',
     'buy_in': 1.1, 'prize': 5.58, 'place': 3, 'financeiro_origem': None},
]
pareados = parear(normalizar(REAL), list(NOSSOS))
casou = {r['colocacao']: (r['par'] or {}).get('id') for r in pareados}
check(casou.get(5) == 2287, 'o 5o lugar devia casar com o torneio 2287: %r' % casou.get(5))
check(casou.get(3) == 2289, 'o 3o lugar devia casar com o torneio 2289: %r' % casou.get(3))
check(casou.get(22) == 2280,
      'o 22o devia sobrar para o 2280 (o unico sem colocacao gravada): %r' % casou.get(22))
# CONTROLE: nenhum torneio nosso foi usado duas vezes. Sem isto, um pareamento que casasse tudo
# no mesmo torneio passaria nos tres casos acima.
usados = [v for v in casou.values() if v]
check(len(usados) == len(set(usados)), 'o mesmo torneio foi casado duas vezes: %r' % usados)

# Referencia por ID, e nunca por indice: reordenar a fixture (o que eu precisei fazer para a
# guarda da ordem valer) mudaria em silencio qual torneio estes casos usam.
POR_ID = {t['id']: t for t in NOSSOS}
IGUAL = POR_ID[2287]          # o unico ja identico ao que o SharkScope devolve (pos 5, 6.16)

# ── 4. O plano PROTEGE o que veio do arquivo da sala ───────────────────────────────────────
com_arquivo = [dict(IGUAL, financeiro_origem='arquivo')]
p = planejar(1, REAL, com_arquivo)
check(len(p['protegidos']) == 1, 'o torneio com resultado de arquivo nao foi protegido: %r' % p)
check(not p['atualizar'], 'o plano quer sobrescrever dado de arquivo: %r' % p['atualizar'])
check('arquivo' in MAIS_CONFIAVEL, 'o arquivo deixou de ser a fonte mais confiavel')

# CONTROLE: com origem `manual`, o MESMO torneio entra para atualizar. Sem este caso, um plano
# que protegesse tudo passaria no de cima.
com_manual = [dict(IGUAL, financeiro_origem='manual', prize=None, place=None)]
p2 = planejar(1, REAL, com_manual)
check(len(p2['atualizar']) == 1,
      'dado digitado devia ser atualizavel pelo SharkScope: %r' % p2)

# ── 5. O que ja esta igual nao vira escrita ────────────────────────────────────────────────
p3 = planejar(1, REAL, [dict(IGUAL)])
check(len(p3['iguais']) == 1 and not p3['atualizar'],
      'torneio ja identico devia entrar em `iguais`, nao em `atualizar`: %r' % p3)

# ── 6. O JSON sem torneio nenhum nao estoura ───────────────────────────────────────────────
check(normalizar({}) == [], 'payload vazio devia devolver lista vazia')
check(normalizar({'Response': {'PlayerResponse': {}}}) == [], 'payload torto devia devolver vazio')
um_so = {"Response": {"PlayerResponse": {"PlayerView": {"Player": {
    "@name": "X", "CompletedTournaments": {"Tournament": {
        "@date": "1789660337", "@stake": "1", "@rake": "0.1", "@totalEntrants": "10",
        "TournamentEntry": {"@position": "1", "@prize": "5"}}}}}}}}
check(len(normalizar(um_so)) == 1, 'um torneio so (dict, nao lista) devia ser aceito')

# ── 7. A procedencia ────────────────────────────────────────────────────────────────────────
check(ORIGEM == 'sharkscope', 'a procedencia gravada mudou: %r' % ORIGEM)

# ── 8. O endpoint e ADMIN, e seco por padrao ───────────────────────────────────────────────
app_src = io.open(os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py'),
                  encoding='utf-8').read()
i = app_src.find("def admin_importar_sharkscope")
check(i > 0, 'o endpoint sumiu')
if i > 0:
    cabeca = app_src[max(0, i - 220):i]
    # A funcao INTEIRA, delimitada pela proxima rota. A primeira versao cortava em 3.000
    # caracteres e a linha do seco estava em 3.030: a guarda acusou o codigo certo. Janela
    # arbitraria em varredura estrutural e defeito da guarda, nao do produto.
    _fim = app_src.find("@app.route(", i)
    corpo = app_src[i:_fim if _fim > i else len(app_src)]
    check(len(corpo) > 1000, 'nao consegui delimitar o corpo da funcao: %d chars' % len(corpo))
    check('@require_admin' in cabeca, 'o endpoint do importador NAO exige admin')
    check("body.get('aplicar') is True" in corpo,
          'o endpoint nao exige `aplicar: true` explicito: o seco deixou de ser o padrao')

print("\n" + "=" * 50)
print("Total: %d | Passed: %d | Failed: %d" % (passed + failed, passed, failed))
sys.exit(1 if failed else 0)
