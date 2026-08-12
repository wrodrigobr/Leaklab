"""
Voto adversarial do Desafio do Dia — a camada 4 da arquitetura de certeza.

Entre o gabarito do solver (camada 1-3) e a aprovação humana (camada 5) faltava um perito
independente perguntando "essa resposta é absurda?".

O risco desta camada NÃO é deixar passar: é **matar questão boa**. Spot difícil parece errado de
propósito — se o refutador for agressivo, ele varre exatamente o que queremos publicar, e o pool
volta a ser só o óbvio. Por isso a maioria dos testes aqui defende o candidato, não o veto.

Sem chamar a API: o `_call_llm_api` é substituído por votos controlados.
"""
import sys, os, json, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.daily_challenge as dc
from leaklab.daily_challenge import (
    verify_challenge, _parse_refute, REFUTE_VOTES, REFUTE_MAJORITY,
)

_SPOT = {'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'CO', 'stack_bb': 20,
         'hand': 'K8s', 'options': ['fold', 'call', 'raise']}
_CTX = {'gto_strategy': [{'action': 'call', 'freq': 0.55}, {'action': 'fold', 'freq': 0.45}],
        'best_action': 'call'}


class _LLM:
    """Substitui _call_llm_api devolvendo respostas em sequência (uma por voto)."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    def __call__(self, payload):
        self.chamadas += 1
        r = self.respostas[min(self.chamadas - 1, len(self.respostas) - 1)]
        if isinstance(r, Exception):
            raise r
        return r


def _com_llm(respostas, **kw):
    """Roda verify_challenge com o LLM controlado. Limpa o cache entre casos."""
    import leaklab.llm_explainer as llm
    dc._REFUTE_CACHE.clear()
    orig = llm._call_llm_api
    fake = _LLM(respostas)
    llm._call_llm_api = fake
    try:
        return verify_challenge(_SPOT, dict(_CTX), **kw), fake
    finally:
        llm._call_llm_api = orig


def _voto(refuta, motivo='x'):
    return json.dumps({'refuta': refuta, 'motivo': motivo})


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_parse_aceita_json_puro_e_dentro_de_texto():
    assert _parse_refute('{"refuta": true, "motivo": "spot impossível"}')[0] is True
    assert _parse_refute('Claro!\n```json\n{"refuta": false, "motivo": "ok"}\n```')[0] is False
    print("OK  test_parse_aceita_json_puro_e_dentro_de_texto")


def test_parse_devolve_none_no_ilegivel():
    """Ilegível NÃO é veto: tratar resposta quebrada como refutação derrubaria candidato bom
    por falha de parsing, que é ruído e não avaliação."""
    for lixo in ('', 'não sei', '{quebrado', '{"outro": 1}', None):
        assert _parse_refute(lixo) is None, lixo
    print("OK  test_parse_devolve_none_no_ilegivel")


# ── Apuração ──────────────────────────────────────────────────────────────────

def test_maioria_refuta_derruba():
    r, _ = _com_llm([_voto(True, 'insustentável'), _voto(True), _voto(False)])
    assert r['veredito'] == 'refutado', r
    assert r['refutacoes'] == 2 and r['votos'] == 3
    print("OK  test_maioria_refuta_derruba")


def test_voto_unico_contrario_NAO_derruba():
    """O ponto da votação múltipla: um perito discordando é ruído, não veredito. Se um voto
    bastasse, spot difícil (que parece errado) morreria na primeira opinião divergente."""
    r, _ = _com_llm([_voto(True, 'não gosto'), _voto(False), _voto(False)])
    assert r['veredito'] == 'aprovado', r
    print("OK  test_voto_unico_contrario_NAO_derruba")


def test_unanimidade_a_favor_aprova():
    r, _ = _com_llm([_voto(False), _voto(False), _voto(False)])
    assert r['veredito'] == 'aprovado' and r['refutacoes'] == 0
    print("OK  test_unanimidade_a_favor_aprova")


def test_sem_llm_nao_bloqueia():
    """Fail-open deliberado: esta é a camada 4 de 5 e a 5 é humana. Bloquear a geração porque o
    modelo caiu seria parar por um motivo que não é de qualidade."""
    r, _ = _com_llm([RuntimeError('sem chave'), RuntimeError('sem chave'), RuntimeError('x')])
    assert r['veredito'] == 'indisponivel' and r['votos'] == 0
    print("OK  test_sem_llm_nao_bloqueia")


def test_votos_ilegiveis_somem_da_apuracao():
    """2 ilegíveis + 1 refutação = 1 voto válido. Com REFUTE_MAJORITY=2 mas só 1 válido, a
    maioria efetiva é 1 — e o candidato cai. É o comportamento certo: o único perito que
    conseguiu opinar disse que é insustentável."""
    r, _ = _com_llm(['lixo', 'também lixo', _voto(True, 'impossível')])
    assert r['votos'] == 1 and r['veredito'] == 'refutado', r
    print("OK  test_votos_ilegiveis_somem_da_apuracao")


def test_cache_evita_repetir_o_custo():
    """N votos por candidato já é caro; repetir o mesmo spot seria desperdício puro."""
    import leaklab.llm_explainer as llm
    dc._REFUTE_CACHE.clear()
    orig = llm._call_llm_api
    fake = _LLM([_voto(False)])
    llm._call_llm_api = fake
    try:
        verify_challenge(_SPOT, dict(_CTX))
        n1 = fake.chamadas
        verify_challenge(_SPOT, dict(_CTX))
        assert fake.chamadas == n1, f"cache não pegou: {fake.chamadas} > {n1}"
    finally:
        llm._call_llm_api = orig
    print("OK  test_cache_evita_repetir_o_custo")


def test_quantidade_de_votos_respeita_a_constante():
    _, fake = _com_llm([_voto(False)])
    assert fake.chamadas == REFUTE_VOTES, f"{fake.chamadas} != {REFUTE_VOTES}"
    print(f"OK  test_quantidade_de_votos_respeita_a_constante ({REFUTE_VOTES} peritos)")


def test_maioria_e_menor_que_o_total():
    """Se REFUTE_MAJORITY == REFUTE_VOTES, exigiria unanimidade e a camada viraria decorativa."""
    assert 1 < REFUTE_MAJORITY <= REFUTE_VOTES
    print("OK  test_maioria_e_menor_que_o_total")


# ── Enquadramento do prompt ───────────────────────────────────────────────────

def test_prompt_avisa_que_a_correcao_e_mixed_aware():
    """REGRESSÃO da primeira rodada em produção.

    O refutador derrubou um spot 54%/46% (AQs em UTG vs 3-bet do CO a 12bb) dizendo que fold
    "é claramente insustentável, pois o solver mostra fold em apenas 54% e allin em 46%" — ou
    seja, refutou por ser MISTO, que o prompt listava como motivo inválido.

    Mas ele estava certo dado o que lhe foi dito: perguntamos "a resposta proposta é correta?"
    sem informar que a correção é mixed-aware e credita a ação de 46%. Ele julgou "fold é A
    resposta?" quando a pergunta real é "isto é uma pergunta justa?".

    O prompt precisa carregar esse enquadramento, senão todo spot da faixa difícil (que é
    mista por definição) vira refutação — e a faixa inteira morre.
    """
    p = dc._refute_prompt(_SPOT, dict(_CTX), 'call')
    sys_txt = p['system'].lower()
    assert 'mixed-aware' in sys_txt, "o prompt não diz que a correção credita a ação alternativa"
    assert 'aceitável' in sys_txt or 'aceitavel' in sys_txt
    assert 'justa' in sys_txt, "o prompt não reformula a pergunta para 'a questão é justa?'"
    # e a referência não pode ser apresentada como resposta ÚNICA
    user_txt = p['messages'][0]['content']
    assert 'REFERÊNCIA' in user_txt and 'como correta' not in user_txt, user_txt
    print("OK  test_prompt_avisa_que_a_correcao_e_mixed_aware")


def test_prompt_carrega_os_fatos_do_spot():
    """Ancoragem: sem os fatos, o modelo julga um spot imaginário."""
    p = dc._refute_prompt(_SPOT, dict(_CTX), 'call')
    u = p['messages'][0]['content']
    for esperado in ('BB', 'CO', '20bb', 'K8s', 'call 55%', 'fold 45%'):
        assert esperado in u, f"falta {esperado!r} nos fatos: {u}"
    print("OK  test_prompt_carrega_os_fatos_do_spot")


# ── Integração com o gerador ──────────────────────────────────────────────────

def test_gerador_descarta_refutado():
    """O efeito que importa: candidato derrubado não chega ao pool."""
    import leaklab.llm_explainer as llm
    dc._REFUTE_CACHE.clear()
    orig = llm._call_llm_api
    llm._call_llm_api = _LLM([_voto(True, 'insustentável')])   # todos refutam
    try:
        import random
        c = dc.build_candidates(n=3, rng=random.Random(7), with_explanation=False,
                                difficulty='dificil', verify=True)
        assert c == [], f"refutados vazaram para o pool: {len(c)}"
    finally:
        llm._call_llm_api = orig
    print("OK  test_gerador_descarta_refutado")


def test_gerador_sem_verify_nao_chama_llm():
    """`verify=False` tem que ser realmente barato — é o modo usado em teste."""
    import leaklab.llm_explainer as llm
    dc._REFUTE_CACHE.clear()
    orig = llm._call_llm_api
    fake = _LLM([_voto(False)])
    llm._call_llm_api = fake
    try:
        import random
        dc.build_candidates(n=2, rng=random.Random(7), with_explanation=False,
                            difficulty='dificil', verify=False)
        assert fake.chamadas == 0, f"chamou o LLM com verify=False: {fake.chamadas}"
    finally:
        llm._call_llm_api = orig
    print("OK  test_gerador_sem_verify_nao_chama_llm")


def test_sem_llm_o_candidato_passa_marcado():
    """Fail-open, mas VISÍVEL: o admin precisa saber que o voto não aconteceu."""
    import leaklab.llm_explainer as llm
    dc._REFUTE_CACHE.clear()
    orig = llm._call_llm_api
    llm._call_llm_api = _LLM([RuntimeError('sem chave')])
    try:
        import random
        c = dc.build_candidates(n=2, rng=random.Random(7), with_explanation=False,
                                difficulty='dificil', verify=True)
        assert c, "fail-open deveria deixar passar"
        assert all('[sem voto do LLM]' in x['note'] for x in c), c[0]['note']
    finally:
        llm._call_llm_api = orig
    print("OK  test_sem_llm_o_candidato_passa_marcado")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
    raise SystemExit(1 if failed else 0)
