"""
O HUD tem de bater com o PokerTracker 4, num torneio real com gabarito externo.

── O que originou (04/09/2026) ───────────────────────────────────────────────────────────

O Rullian, fundador que tem PT4 do lado, mostrou que o nosso HUD nao batia com o dele. Seis
defeitos sairam dessa comparacao, e o padrao que une TODOS e o mesmo: **o dado dizia uma
coisa e a consulta perguntava outra.**

  1. `shove` invisivel  — o parser grava `shove`, 8 consultas procuravam `jam`, que nao
     aparece uma vez no acervo. 1.005 all-ins preflop fora de VPIP, PFR, AF, c-bet, steal.
  2. WTSD media "chegou ao river" em vez de "foi a showdown" (18pp de diferenca).
  3. "viu o flop" ignorava all-in preflop: ve o flop sem ter o que decidir, e nos so
     gravamos linha onde ha decisao.
  4. Fold to 3Bet era a stat `After Raise` do PT4 com o nome da outra.
  5. C-Bet chamava de agressor quem deu raise em ALGUM momento, nao quem tem a iniciativa.
  6. Steal contava raise sobre limp, que o PT4 nao conta (o limpador ja abriu o pote).

── Por que este teste existe, e nao so o script ──────────────────────────────────────────

`scripts/comparar_hud_com_pt4.py` compara qualquer pasta contra qualquer gabarito, e serve
para investigar. Ele nao roda sozinho. Este teste congela UM torneio com UM gabarito e roda
na suite: qualquer mexida futura que desvie do PT4 falha aqui, sem depender de alguem
lembrar de comparar.

O fixture e anonimizado (`Hero` + `V_<hash>`), e a anonimizacao foi VERIFICADA: 2.616
ocorrencias do heroi no original e 2.616 no anonimizado, 19 "and won" nos dois, e os 10
numeros identicos. A 1a versao do anonimizador tinha um bug que so apareceu porque eu
conferi: o regex `^Seat \\d+: (.+?) \\(` capturava "ddamataa collected" como se fosse um
nome na linha "Seat 4: ddamataa collected (81600)"; por ser mais longo que o nome do heroi,
era substituido primeiro e o apagava de 205 linhas. O W$SD despencou de 65,5 para 27,6 e
foi assim que o defeito apareceu.

── Manutencao ────────────────────────────────────────────────────────────────────────────

`alvo_pt4.json` veio do ReportExport.csv do PT4, linha "MTT PROGBOUNT" (402 maos), torneio
PokerStars #4002468231. **Nao ajuste o alvo para o teste passar**: o alvo e o oraculo
externo. Se divergir, ou o nosso calculo mudou, ou a definicao mudou — as duas coisas
merecem investigacao, nao um numero novo no JSON.
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'hud_pt4')
_DB = os.path.join(tempfile.gettempdir(), 'hud_pt4_suite.db')
if os.path.exists(_DB):
    os.remove(_DB)
os.environ['LEAKLAB_DB'] = _DB
os.environ.pop('DATABASE_URL', None)

import database.schema as sch
import database.repositories as repo
sch.init_db()

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

# Tolerancia: NAO e zero de proposito. O PT4 conta MAO RECEBIDA e nos contamos MAO COM
# DECISAO, entao ha diferenca legitima de definicao. 0,5pp em 402 maos sao ~2 maos: aperta
# o bastante para nenhum dos 6 defeitos acima passar (o menor deles valia 3,4pp).
TOLERANCIA_PP = 0.5
TOLERANCIA_MAOS_PCT = 2.0

_ALVO = json.load(io.open(os.path.join(_FIXTURE, 'alvo_pt4.json'), encoding='utf-8'))
_CAMPOS = [
    ('vpip', 'vpip'), ('pfr', 'pfr'), ('three_bet', 'three_bet'),
    ('wtsd', 'wtsd'), ('w_at_sd', 'w_at_sd'), ('af', 'af'),
    ('cbet_pct', 'cbet_pct'), ('steal_pct', 'steal_pct'),
    ('fold_to_3bet', 'fold_to_3bet'),
]

_stats_cache = {}


def _stats():
    if _stats_cache:
        return _stats_cache
    from database.auth import generate_token
    from api.app import app
    uid = repo.create_user('fixture_pt4', 'fixture_pt4@test.local', 'fixture1234', 'player')
    cliente = app.test_client()
    tok = generate_token(uid, 'player')
    bruto = io.open(os.path.join(_FIXTURE, 'torneio_402_maos.txt'),
                    encoding='utf-8', errors='ignore').read()
    r = cliente.post('/analyze?explain=false', json={'content': bruto},
                     headers={'Authorization': 'Bearer %s' % tok})
    assert r.status_code == 200, 'import do fixture falhou: HTTP %s' % r.status_code
    # last_n=0 = historico genuino. Com o default (50) o recorte mudaria e a comparacao
    # mediria escopos diferentes — foi exatamente o mal-entendido que abriu esta investigacao.
    _stats_cache.update(repo.get_player_stats(uid, days=3650, last_n=0))
    return _stats_cache


def test_o_fixture_esta_anonimizado():
    """Sao maos reais de um fundador. Nome real no repositorio nao volta atras."""
    txt = io.open(os.path.join(_FIXTURE, 'torneio_402_maos.txt'), encoding='utf-8').read()
    assert 'ddamataa' not in txt, 'nome real do heroi vazou para o fixture'
    assert 'Dealt to Hero' in txt, 'o heroi deveria se chamar Hero'
    print("OK  test_o_fixture_esta_anonimizado")


def test_contagem_de_maos_bate():
    s = _stats()
    alvo = _ALVO['hands']
    delta = abs(s['total_hands'] - alvo)
    assert delta <= alvo * TOLERANCIA_MAOS_PCT / 100.0, \
        'maos: nosso %s vs PT4 %s' % (s['total_hands'], alvo)
    print("OK  test_contagem_de_maos_bate (%s vs %s)" % (s['total_hands'], alvo))


def test_todos_os_indicadores_batem_com_o_pokertracker():
    s = _stats()
    fora = []
    for chave, campo in _CAMPOS:
        nosso, deles = s.get(campo), _ALVO.get(chave)
        if deles is None:
            continue
        if nosso is None:
            fora.append('%s: nosso None vs PT4 %s' % (chave, deles))
            continue
        if abs(float(nosso) - float(deles)) > TOLERANCIA_PP:
            fora.append('%s: nosso %s vs PT4 %s (delta %+.2f)' % (
                chave, nosso, deles, float(nosso) - float(deles)))
    assert not fora, 'fora da tolerancia de %.1fpp:\n  %s' % (TOLERANCIA_PP, '\n  '.join(fora))
    print("OK  test_todos_os_indicadores_batem_com_o_pokertracker (%d indicadores)" % len(_CAMPOS))


def test_CONTRAPROVA_o_teste_acha_um_desvio_plantado():
    """Sem isto, uma tolerancia larga demais deixaria os testes acima verdes para sempre.

    Planta o menor dos 6 defeitos reais (VPIP subestimado em 3,36pp pelo `shove` invisivel)
    e exige que a comparacao acuse.
    """
    s = dict(_stats())
    s['vpip'] = round(float(_ALVO['vpip']) - 3.36, 2)
    assert abs(s['vpip'] - float(_ALVO['vpip'])) > TOLERANCIA_PP, \
        'a tolerancia esta larga demais: nao acusaria nem o defeito do shove'
    # e um desvio DENTRO da tolerancia nao pode acusar (senao o teste vira alarme falso)
    s['vpip'] = round(float(_ALVO['vpip']) + 0.2, 2)
    assert abs(s['vpip'] - float(_ALVO['vpip'])) <= TOLERANCIA_PP
    print("OK  test_CONTRAPROVA_o_teste_acha_um_desvio_plantado")


def test_o_vocabulario_de_acao_cobre_all_in():
    """Regra 5: a definicao de acao agressiva vive num lugar so, e inclui `shove`.

    O defeito original era 8 copias da mesma lista, todas com 'jam' e nenhuma com 'shove'.
    """
    fonte = io.open(os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py'),
                    encoding='utf-8').read()
    assert "'shove'" in repo._SQL_ALLIN or 'shove' in repo._SQL_ALLIN, \
        'o vocabulario de all-in perdeu o shove'
    import re
    cruas = re.findall(r"action_taken IN \('[^)]*jam'[^)]*\)", fonte)
    assert not cruas, 'voltou lista crua de acao no SQL (regra 5): %s' % cruas[:3]
    print("OK  test_o_vocabulario_de_acao_cobre_all_in")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print("FALHOU  %s: %s" % (t.__name__, e))
            import traceback; traceback.print_exc()
            failed += 1
    print("\n%s" % ('=' * 50))
    print("Total: %d | Passed: %d | Failed: %d" % (passed + failed, passed, failed))
    raise SystemExit(1 if failed else 0)
