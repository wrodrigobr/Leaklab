"""
Todo worker que só sobe no `__main__` do app precisa de um par em produção.

Esta é a classe de bug mais cara desta base, e ela já apareceu quatro vezes com o MESMO sintoma:
o dashboard anuncia "N spots ainda sendo validados pelo solver, suas estatísticas serão
recomputadas automaticamente" e nunca concluem. A causa é sempre a mesma: `python api/app.py`
(dev) executa o bloco `__main__` e sobe o worker; gunicorn (prod) IMPORTA o módulo e nunca
executa o `__main__`. O código está lá, roda no dev, e não existe em produção.

O que não funcionou como defesa: lembrar. O cron de `expire_coach_trials` está pendente no host
desde junho pelo mesmo motivo — depender de configuração manual é depender de memória.

O que este teste trava: que cada loop de worker declarado no app tenha um consumidor de verdade
em `run_solver_consumer.py`, que é um serviço já rodando. Se alguém acrescentar um worker novo ao
`__main__` sem o par, ou renomear um existente, isto cai — em vez de virar um bug silencioso que
só aparece semanas depois como número errado na tela do jogador.
"""
import sys, os, ast, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BACKEND  = os.path.join(os.path.dirname(__file__), '..')
_APP      = os.path.join(_BACKEND, 'api', 'app.py')
_CONSUMER = os.path.join(_BACKEND, 'run_solver_consumer.py')

# Workers que PRECISAM rodar em produção. Nome → por que existe (aparece na falha).
_WORKERS_OBRIGATORIOS = {
    '_solver_queue_worker_loop': 'fila do solver postflop (gto_solver_queue)',
    '_gto_hand_worker_loop':     'fila de pedidos por mão (gto_hand_requests) — o aviso '
                                 '"spots sendo validados" no dashboard depende dela',
    '_evolution_report_worker_loop': 'congela os retratos datados do relatório de evolução; '
                                     'sem ela a cadência automática nunca dispara',
}


def _nomes_importados(caminho):
    """Nomes que o entrypoint importa de `api.app` (via AST — não por substring, que casaria
    com uma menção em comentário)."""
    arvore = ast.parse(open(caminho, encoding='utf-8').read())
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and (no.module or '').startswith('api.app'):
            nomes.update(a.name for a in no.names)
    return nomes


def test_consumidor_sobe_todos_os_workers_obrigatorios():
    importados = _nomes_importados(_CONSUMER)
    faltando = {w: p for w, p in _WORKERS_OBRIGATORIOS.items() if w not in importados}
    assert not faltando, (
        "run_solver_consumer.py não sobe: "
        + "; ".join(f"{w} ({p})" for w, p in faltando.items())
        + ". Sem isso o worker roda no dev e NÃO em produção.")
    print("OK  test_consumidor_sobe_todos_os_workers_obrigatorios "
          f"({len(_WORKERS_OBRIGATORIOS)} workers)")


def test_workers_existem_mesmo_no_app():
    """Protege contra rename: o entrypoint importar um nome que não existe mais só falharia na
    hora de subir o serviço em produção, longe de qualquer teste."""
    import api.app as app
    for w in _WORKERS_OBRIGATORIOS:
        assert callable(getattr(app, w, None)), f"api.app.{w} não existe (renomeado?)"
    print("OK  test_workers_existem_mesmo_no_app")


def test_nenhum_worker_novo_ficou_so_no_main():
    """Varre o bloco `__main__` do app atrás de threads de worker e exige que cada alvo esteja
    na lista obrigatória. Worker novo sem par em produção não passa despercebido."""
    arvore = ast.parse(open(_APP, encoding='utf-8').read())
    alvos = set()
    for no in ast.walk(arvore):
        # threading.Thread(target=<nome>, ...)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) \
                and no.func.attr == 'Thread':
            for kw in no.keywords:
                if kw.arg == 'target' and isinstance(kw.value, ast.Name) \
                        and kw.value.id.endswith('_loop'):
                    alvos.add(kw.value.id)
    desconhecidos = alvos - set(_WORKERS_OBRIGATORIOS)
    assert not desconhecidos, (
        f"worker(s) em thread sem par declarado em produção: {sorted(desconhecidos)}. "
        f"Ou suba em run_solver_consumer.py e acrescente a _WORKERS_OBRIGATORIOS, ou documente "
        f"aqui por que roda só em dev.")
    print(f"OK  test_nenhum_worker_novo_ficou_so_no_main ({len(alvos)} threads de worker)")


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
