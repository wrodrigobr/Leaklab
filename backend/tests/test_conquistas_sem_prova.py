"""test_conquistas_sem_prova.py — o caminho quente do corretor não pode pagar a prova.

**Origem:** o usuário mediu no navegador que o veredito do Leak Trainer levava **6,19 segundos**.
Medido peça por peça em produção, `evaluate_training_achievements` sozinho custava 3.115ms, dos
quais **2.677ms eram `get_training_proof`** — a prova de leak comprovado nas mesas, recalculada a
cada clique só para somar três inteiros. O cálculo de GTO do spot leva 57ms.

A prova mede hand history NOVA. Nenhuma resposta no treino a altera. Então o corretor passa
`com_prova=False` e quem concede as quatro medalhas de prova-no-jogo é `/player/training/overview`,
que já calcula a prova para desenhar a tela.

**O risco do conserto (CLAUDE.md nº 7):** pular a prova poderia fazer as quatro medalhas sumirem
para sempre, caladas — dano que o bug de lentidão não causava. Por isso os testes daqui exigem
as duas metades: que o caminho rápido NÃO conceda **e** que o caminho com prova conceda.
"""
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name

from database.schema import init_db, get_conn
import database.repositories as R
from database.repositories import (_training_state, evaluate_training_achievements,
                                   record_training_attempt, _TRAINING_ACHIEVEMENT_DEFS)

init_db()

# As quatro que dependem da prova. Derivadas da própria tabela de defs para não congelar uma
# cópia: se alguém acrescentar uma medalha de prova, ela entra aqui sozinha.
_CAMPOS_DE_PROVA = {'count_provados', 'count_reconquistados', 'count_com_amostra'}
_MEDALHAS_DE_PROVA = {k for k, campo, _ in _TRAINING_ACHIEVEMENT_DEFS if campo in _CAMPOS_DE_PROVA}


def _mk_user(nome='cp'):
    c = get_conn()
    c.execute("DELETE FROM decisions")
    c.execute("DELETE FROM tournaments")
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM training_skill_progress")
    c.execute("DELETE FROM training_achievements")
    c.execute("INSERT INTO users (username,email,password_hash,plan) VALUES (?,?,?,?)",
              (nome, f'{nome}@t', 'x', 'free'))
    uid = c.execute("SELECT id FROM users WHERE username = ?", (nome,)).fetchone()['id']
    c.commit(); c.close()
    return uid


class _Espiao:
    """Troca `get_training_proof` por um contador. A prova é uma consulta N+1: o teste não mede
    tempo (que varia com a máquina), mede se ela foi CHAMADA."""

    def __enter__(self):
        self.n = 0
        self._orig = R.get_training_proof

        def falso(uid, *a, **kw):
            self.n += 1
            return self._orig(uid, *a, **kw)

        R.get_training_proof = falso
        return self

    def __exit__(self, *e):
        R.get_training_proof = self._orig
        return False


def test_ha_medalhas_de_prova_para_medir():
    """Sem isto, todos os outros testes deste arquivo passariam medindo o conjunto vazio."""
    assert _MEDALHAS_DE_PROVA, f'nenhuma medalha usa {_CAMPOS_DE_PROVA} — o arquivo mede nada'
    print(f'OK  test_ha_medalhas_de_prova_para_medir ({len(_MEDALHAS_DE_PROVA)} medalhas)')


def test_com_prova_false_nao_consulta_a_prova():
    """O ponto do conserto: a consulta cara não pode acontecer no clique."""
    uid = _mk_user()
    with _Espiao() as e:
        evaluate_training_achievements(uid, com_prova=False)
    assert e.n == 0, f'a prova foi consultada {e.n}x no caminho rápido'
    # e o contraste: sem o parâmetro, ela É consultada — senão o teste acima passaria por acidente
    with _Espiao() as e2:
        evaluate_training_achievements(uid)
    assert e2.n == 1, f'o caminho normal deveria consultar a prova 1x, consultou {e2.n}'
    print('OK  test_com_prova_false_nao_consulta_a_prova')


def test_campo_sem_prova_e_None_e_nao_zero():
    """Zero negaria a medalha em silêncio. `None` diz "não perguntei" — e o avaliador pula."""
    uid = _mk_user()
    st = _training_state(uid, com_prova=False)
    for campo in _CAMPOS_DE_PROVA:
        assert st.get(campo) is None, f'{campo} veio {st.get(campo)!r}, esperado None'
    # com prova, os mesmos campos são números (mesmo que zero)
    st2 = _training_state(uid, com_prova=True)
    for campo in _CAMPOS_DE_PROVA:
        assert isinstance(st2.get(campo), int), f'{campo} veio {st2.get(campo)!r}'
    print('OK  test_campo_sem_prova_e_None_e_nao_zero')


def test_medalha_de_prova_nao_e_concedida_no_caminho_rapido():
    """A metade defensiva: o corretor não pode conceder o que não mediu."""
    uid = _mk_user()
    for _ in range(30):
        record_training_attempt(uid, 'rfi:BB::50', True)
    novas = set(evaluate_training_achievements(uid, com_prova=False))
    vazou = novas & _MEDALHAS_DE_PROVA
    assert not vazou, f'medalha de prova concedida sem medir a prova: {vazou}'
    print('OK  test_medalha_de_prova_nao_e_concedida_no_caminho_rapido')


def test_medalha_de_contador_continua_saindo_no_clique():
    """A outra metade: se o caminho rápido não concedesse NADA, o veredito ficaria mudo e o
    teste anterior passaria sem significar nada."""
    uid = _mk_user()
    record_training_attempt(uid, 'rfi:BB::50', True)
    novas = set(evaluate_training_achievements(uid, com_prova=False))
    assert 'train:first' in novas, f'o clique deixou de conceder conquista de contador: {novas}'
    print('OK  test_medalha_de_contador_continua_saindo_no_clique')


def test_a_medalha_de_prova_sai_quando_a_prova_entra():
    """O conserto não pode APOSENTAR as quatro medalhas. Com a prova em mãos — como o hub de
    treino a passa — elas voltam a ser concedidas."""
    uid = _mk_user()
    prova = [{'validacao': {'veredito': 'melhorou'}, 'reopen_count': 0}]
    novas = set(evaluate_training_achievements(uid, proof=prova))
    assert 'train:cycle' in novas, f'ciclo fechado não concedido com prova em mãos: {novas}'
    assert 'train:proved' in novas, f'leak comprovado não concedido com prova em mãos: {novas}'
    # e não concede a de 2 provas com uma só — o alvo continua valendo
    assert 'train:proved2' not in novas, novas
    print('OK  test_a_medalha_de_prova_sai_quando_a_prova_entra')


def test_campo_desconhecido_nao_concede_nem_com_alvo_zero():
    """O `continue` do campo `None` só é observável quando o alvo é 0 — e nenhuma medalha de hoje
    tem alvo 0. Sem construir esse caso o guarda seria decoração.

    Conferido quebrando: removido o `continue`, `float(None or 0)` vira `0 >= 0` e a medalha é
    concedida **sem ninguém ter medido a prova**. O teste acusa.
    """
    uid = _mk_user()
    orig = R._TRAINING_ACHIEVEMENT_DEFS
    R._TRAINING_ACHIEVEMENT_DEFS = list(orig) + [('train:_zero_de_prova', 'count_provados', 0)]
    try:
        novas = set(evaluate_training_achievements(uid, com_prova=False))
    finally:
        R._TRAINING_ACHIEVEMENT_DEFS = orig
    assert 'train:_zero_de_prova' not in novas, \
        'medalha de prova concedida a partir de campo NÃO MEDIDO tratado como zero'
    print('OK  test_campo_desconhecido_nao_concede_nem_com_alvo_zero')


def test_o_hub_concede_as_medalhas_de_prova():
    """Varredura de ponta a ponta pela porta real: `/player/training/overview` é o único lugar
    que ainda avalia com prova, então é ele que precisa conceder."""
    import re
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as f:
        src = f.read()
    corpo = src.split('def training_overview(')[1].split('\n@app.route')[0]
    assert re.search(r'evaluate_training_achievements\(\s*g\.user_id\s*,\s*proof=', corpo), \
        'o hub não concede as medalhas de prova — as quatro ficariam órfãs'
    # E o corretor NÃO pode: se voltar a pagar a prova, os 2,7s voltam junto. Casa na CHAMADA e
    # não na string solta — a primeira versão deste assert procurava `com_prova=False` em qualquer
    # lugar do bloco e passava encontrando a expressão no COMENTÁRIO logo acima da chamada. Guarda
    # que lê comentário não guarda nada (CLAUDE.md nº 8).
    corretor = src.split('def leaktrainer_grade(')[1].split('\n@app.route')[0]
    corretor = re.sub(r'#[^\n]*', '', corretor)          # fora comentários
    assert re.search(r'evaluate_training_achievements\([^)]*com_prova\s*=\s*False', corretor), \
        'o corretor voltou a calcular a prova a cada clique'
    print('OK  test_o_hub_concede_as_medalhas_de_prova')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
    raise SystemExit(1 if fail else 0)
