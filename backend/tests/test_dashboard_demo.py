"""
test_dashboard_demo.py — a tela de DEMONSTRAÇÃO do dashboard (`/demo`).

Ela existe porque o tour guiado precisa de uma tela POVOADA para apontar. Rodá-lo sobre o
dashboard de quem acabou de se cadastrar seria apontar para cards vazios, e um tour que aponta
para cards vazios ensina que o produto é vazio.

O que estes testes defendem, e a ordem importa:

1. **É pública.** Serve quem ainda nem se cadastrou. Se exigir auth, não serve para nada.
2. **Tem SUBSTÂNCIA, não só presença.** Um payload `{"insufficient_data": true}` passa em
   qualquer teste de "não-vazio" e produz uma demonstração inteira dizendo "ainda não dá para
   afirmar" — o pior resultado possível numa tela cujo trabalho é mostrar o que a ferramenta
   entrega. Este é o guarda central do arquivo.
3. **Os 13 cards têm o que renderizar.** Falta de um payload não quebra a tela: some um card e
   ninguém percebe.
4. **É anônima.** Vai para uma rota pública, para sempre.
5. **Mostra leaks.** Uma demonstração sem leak nenhum prova o contrário do que a landing vende.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'dashboard_demo.json')

# As chaves que o dashboard consome. Espelha `ROTAS` do gerador; se alguém adicionar um card novo
# sem regenerar a fixture, o card nasce vazio na demonstração e este teste acusa.
CHAVES = [
    'evolution', 'playerStats', 'leakRoi', 'pressureProfile', 'confidenceDrift', 'dna',
    'leakGraph', 'career', 'cognitiveFailures', 'strategicTwin', 'sessionContext', 'evSummary',
    'pendingGtoCount', 'gtoAlignment', 'gtoPosition', 'gtoQuality', 'resultsVsGto', 'leakFinder',
    'tournaments',
]


def _client():
    from api.app import app
    app.config['TESTING'] = True
    return app.test_client()


def _fixture():
    with open(FIXTURE, encoding='utf-8') as f:
        return json.load(f)


def test_endpoint_e_publico():
    r = _client().get('/sample/dashboard')
    assert r.status_code == 200, f'esperava 200 sem auth, veio {r.status_code}'
    print('OK  test_endpoint_e_publico')


def test_traz_todos_os_payloads_do_dashboard():
    d = _fixture()
    faltando = [k for k in CHAVES if k not in d or d[k] in (None, {}, [])]
    assert not faltando, f'payloads ausentes ou vazios: {faltando}'
    print(f'OK  test_traz_todos_os_payloads_do_dashboard ({len(CHAVES)} payloads)')


def test_nenhum_card_diz_sem_dado_suficiente():
    """O guarda central. `insufficient_data: true` passa em qualquer checagem de 'não-vazio' e
    transforma a demonstração numa tela de 'ainda não dá para afirmar'."""
    d = _fixture()
    pobres = [k for k, v in d.items() if isinstance(v, dict) and v.get('insufficient_data') is True]
    assert not pobres, f'payloads sem dado suficiente: {pobres}'
    print('OK  test_nenhum_card_diz_sem_dado_suficiente')


def test_tem_volume_para_a_tela_nao_parecer_vazia():
    d = _fixture()
    tors = (d.get('tournaments') or {}).get('tournaments') or []
    assert len(tors) >= 3, f'só {len(tors)} torneios'
    decisoes = (d.get('gtoAlignment') or {}).get('total_decisions') or 0
    assert decisoes >= 100, f'só {decisoes} decisões — os cards de agregado ficariam magros'
    print(f'OK  test_tem_volume_para_a_tela_nao_parecer_vazia ({len(tors)} torneios, {decisoes} decisões)')


def test_mostra_leaks():
    """A landing promete achar onde o EV vazou. Uma demonstração sem leak prova o contrário."""
    d = _fixture()
    assert (d.get('leakFinder') or {}).get('leaks'), 'leakFinder sem leaks'
    assert (d.get('leakRoi') or {}).get('leaks'), 'leakRoi sem leaks'
    print(f"OK  test_mostra_leaks ({len(d['leakFinder']['leaks'])} no leakFinder)")


def test_e_anonima():
    d = _fixture()
    bruto = json.dumps(d, ensure_ascii=False).lower()
    for nick in ('phpro', 'musashibr', 'rodrigo'):
        assert nick not in bruto, f'nick "{nick}" vazou na fixture publica'
    for tor in (d.get('tournaments') or {}).get('tournaments') or []:
        assert not tor.get('hero'), 'nick do herói num torneio'
        nome = tor.get('tournament_name') or ''
        assert nome.startswith('Torneio '), f'nome de torneio nao anonimizado: {nome!r}'
    print('OK  test_e_anonima')


def test_endpoint_devolve_o_que_esta_no_arquivo():
    """Sem filtrar nem enriquecer: o que a tela mostra é o que foi revisado."""
    assert _client().get('/sample/dashboard').get_json() == _fixture()
    print('OK  test_endpoint_devolve_o_que_esta_no_arquivo')


def test_fixture_ausente_vira_404():
    import api.app as app_mod
    original_dir, original_cache = app_mod._FIXTURES_DEMO, dict(app_mod._fixtures_demo_cache)
    app_mod._FIXTURES_DEMO = original_dir / 'nao_existe_de_proposito'
    app_mod._fixtures_demo_cache.clear()
    try:
        r = _client().get('/sample/dashboard')
        assert r.status_code == 404, f'esperava 404, veio {r.status_code}'
    finally:
        app_mod._FIXTURES_DEMO = original_dir
        app_mod._fixtures_demo_cache.clear()
        app_mod._fixtures_demo_cache.update(original_cache)
    print('OK  test_fixture_ausente_vira_404')


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f'FAIL {name}: {e}')
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f'Total: {passed+failed} | Passed: {passed} | Failed: {failed}')
