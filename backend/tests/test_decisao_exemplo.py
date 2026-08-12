"""
test_decisao_exemplo.py — a decisão de exemplo da landing / dashboard vazio.

O exemplo mostrado a quem ainda não subiu arquivo nenhum era escrito à mão: números plausíveis,
uma frase, e nada da evidência que a análise de verdade produz. Quem via aquilo não via o
produto, via uma maquete dele. Agora é uma análise REAL, congelada de uma mão jogada pela mesma
pipeline do /replay.

O que estes testes defendem:

1. **O exemplo é público.** A landing é deslogada; se o endpoint exigir auth, o visitante não vê
   nada e o card volta a ser um espaço vazio.
2. **A fixture está COMPLETA.** Uma fixture pobre não quebra nada: ela renderiza meio card e
   ninguém percebe. É a falha silenciosa que interessa aqui.
3. **A fixture é ANÔNIMA.** Ela vai para uma página pública, para sempre. Nick, id de mão e id de
   torneio não podem viajar junto.
4. **A ausência do arquivo é 404, não 500.** Falta de exemplo não é incidente de servidor, e o
   frontend precisa distinguir para não quebrar a landing.
5. **A mão não tem `open_size_mismatch`.** Este é o guarda que já mudou uma escolha: a primeira
   mão eleita tinha o maior EV perdido da amostra (2,0bb) e foi descartada porque o vilão abriu
   17bb onde o GTO abre 3bb — a range de defesa exibida é vs open MÍNIMO, então ela não descrevia
   o spot enfrentado. No replay a análise segue honesta (o card avisa); como vitrine, seria uma
   análise com asterisco.
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

FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'decisao_exemplo.json')


def _client():
    from api.app import app
    app.config['TESTING'] = True
    return app.test_client()


def _fixture():
    with open(FIXTURE, encoding='utf-8') as f:
        return json.load(f)


def test_fixture_existe_e_esta_versionada():
    """`backend/data/` é ignorado pelo git — uma fixture ali nunca chegaria à imagem, e o
    endpoint responderia vazio em produção sem falhar no dev. Por isso ela vive em
    `backend/fixtures/`, e este teste morre se alguém a mover de volta."""
    assert os.path.exists(FIXTURE), f'fixture ausente em {FIXTURE}'
    assert 'fixtures' in FIXTURE.replace('\\', '/').split('backend/')[-1]
    print('OK  test_fixture_existe_e_esta_versionada')


def test_endpoint_e_publico():
    c = _client()
    r = c.get('/sample/decision')
    assert r.status_code == 200, f'esperava 200 sem auth, veio {r.status_code}'
    d = r.get_json()
    assert 'decision' in d, d
    print('OK  test_endpoint_e_publico')


def test_fixture_tem_a_evidencia_toda():
    """Fixture pobre renderiza meio card e não quebra nada — é a falha silenciosa."""
    d = _fixture()
    pg = d.get('preflop_gto') or {}
    assert pg.get('available') is True, 'sem cobertura GTO o card fica sem a evidência principal'
    for campo in ('hand_type', 'scenario', 'position', 'vs_position', 'stack_bucket',
                  'range_pct', 'recommended_actions', 'pro_notes'):
        assert pg.get(campo), f'preflop_gto.{campo} ausente'
    assert pg.get('hand_freq') or pg.get('fold_pct'), 'sem frequência não há barras de estratégia'
    assert d.get('hand_equity') is not None, 'hand_equity ausente'
    assert d.get('adjusted_required_equity') is not None or d.get('pot_odds_equity') is not None, \
        'equity necessária ausente'
    assert d.get('error_label'), 'sem error_label o card não tem veredito'
    assert d.get('hero_stack_bb') is not None and d.get('m_ratio') is not None, 'rodapé incompleto'
    print(f"OK  test_fixture_tem_a_evidencia_toda | {pg['hand_type']} {pg['position']} vs "
          f"{pg['vs_position']} @ {pg['stack_bucket']}")


def test_fixture_e_anonima():
    """Vai para uma página pública, para sempre."""
    d = _fixture()
    assert not d.get('hero'), 'nick do herói na fixture'
    assert not d.get('seats'), 'assentos (com nicks de vilões) na fixture'
    for proibido in ('hand_id', 'tournament_id', 'user_id', 'desc_raw'):
        assert not d.get(proibido), f'campo identificável presente: {proibido}'
    # varredura no texto inteiro: nick vaza fácil por dentro de nota ou descrição
    bruto = json.dumps(d, ensure_ascii=False).lower()
    for nick in ('phpro', 'musashibr'):
        assert nick not in bruto, f'nick "{nick}" vazou no corpo da fixture'
    print('OK  test_fixture_e_anonima')


def test_fixture_mostra_um_erro():
    """O exemplo existe para mostrar o produto ACHANDO algo, não confirmando um acerto."""
    d = _fixture()
    assert d.get('is_error') is True, 'o exemplo não é um erro'
    assert d['error_label'] in ('small_mistake', 'clear_mistake'), \
        f"error_label {d['error_label']} não mapeia para o nível Erro no card"
    print(f"OK  test_fixture_mostra_um_erro | {d['action']} -> GTO {d.get('gto_action')}")


def test_fixture_sem_descasamento_de_sizing():
    """Ver o cabeçalho do arquivo: este guarda já trocou a mão escolhida uma vez."""
    pg = _fixture().get('preflop_gto') or {}
    assert not pg.get('open_size_mismatch'), (
        f"open_size_mismatch {pg.get('open_size_mismatch')}: a range de defesa exibida é vs open "
        f"mínimo e não descreve o open enfrentado — análise com asterisco não serve de vitrine")
    print('OK  test_fixture_sem_descasamento_de_sizing')


def test_fixture_ausente_vira_404():
    """404 e não 500: falta de exemplo não é incidente, e o frontend precisa distinguir."""
    import api.app as app_mod
    original_dir, original_cache = app_mod._FIXTURES_DEMO, dict(app_mod._fixtures_demo_cache)
    app_mod._FIXTURES_DEMO = original_dir / 'nao_existe_de_proposito'
    app_mod._fixtures_demo_cache.clear()
    try:
        r = _client().get('/sample/decision')
        assert r.status_code == 404, f'esperava 404, veio {r.status_code}'
        assert 'error' in r.get_json()
    finally:
        app_mod._FIXTURES_DEMO = original_dir
        app_mod._fixtures_demo_cache.clear()
        app_mod._fixtures_demo_cache.update(original_cache)
    print('OK  test_fixture_ausente_vira_404')


def test_endpoint_devolve_o_que_esta_no_arquivo():
    """O endpoint não pode filtrar nem enriquecer: o que a landing mostra é o que foi revisado."""
    r = _client().get('/sample/decision')
    assert r.get_json()['decision'] == _fixture()
    print('OK  test_endpoint_devolve_o_que_esta_no_arquivo')


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
    raise SystemExit(1 if failed else 0)
