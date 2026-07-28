"""
O board do hash tem que ser SEMPRE a fatia da street, em todo chamador.

── O bug que este arquivo existe para não deixar voltar (2026-07-28) ──────────────────────────

O banco guarda o board COMPLETO da mão em toda decisão. A decisão 14260, de FLOP, carregava
`["Qd","Th","7h","7s","3h"]` — as cinco cartas do river. Quem consome tem que cortar, e a regra
vivia COPIADA em cada chamador: dois lookups cortavam, o enfileiramento não.

Consequência: o spot de flop era GRAVADO com board de 5 cartas e PROCURADO com board de 3. Os
hashes não podiam coincidir. O solve ficava guardado sob uma chave que ninguém consultava, e o
pedido rechecava de 5 em 5 minutos, para sempre, sem nunca poder concluir — em produção,
`req_id=12` girou até morrer por idade, e a decisão jamais recebeu `gto_label`.

E não parava no hash: o payload mandado ao solver levava o mesmo board inteiro, então ele recebia
`street: flop` com cinco cartas na mesa. Mesmo com hashes casando, o nó descreveria outra decisão.

── Por que um teste ESTRUTURAL, e não só de comportamento ────────────────────────────────────

Testar `board_for_street` sozinho não teria pego nada: a função não existia, e o defeito era um
chamador esquecer a regra. O que precisa ser travado é a REGRA NO PONTO DE USO — todo
`compute_spot_hash` do app tem que receber um board que passou pela fatia. É a mesma espécie de
guarda do `test_worker_entrypoints.py`, e pela mesma razão: o que falhou aqui não foi a lógica,
foi lembrar de aplicá-la num lugar novo.
"""
import sys, os, ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_APP = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
_FATIA = 'board_for_street'
_HASH = 'compute_spot_hash'


def _nome_da_func(no):
    f = no.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)


def test_todo_hash_do_app_recebe_board_fatiado():
    """Percorre cada função do app: nomes vindos de `board_for_street` são os únicos boards
    aceitáveis como 3º argumento de `compute_spot_hash`."""
    arvore = ast.parse(open(_APP, encoding='utf-8').read())
    violacoes = []
    vistos = 0

    for func in [n for n in ast.walk(arvore)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        # nomes que RECEBERAM a fatia dentro desta função
        fatiados = set()
        for no in ast.walk(func):
            if isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) \
                    and _nome_da_func(no.value) == _FATIA:
                fatiados.update(a.id for a in no.targets if isinstance(a, ast.Name))

        for no in ast.walk(func):
            if not (isinstance(no, ast.Call) and _nome_da_func(no) == _HASH):
                continue
            vistos += 1
            if len(no.args) < 3:
                continue                      # chamada por keyword: fora do alcance desta regra
            arg = no.args[2]
            if isinstance(arg, ast.Name) and arg.id in fatiados:
                continue
            # lista literal (teste/constante) é explícita e não vem do banco
            if isinstance(arg, (ast.List, ast.Tuple)):
                continue
            violacoes.append(f"{func.name}() linha {no.lineno}: board "
                             f"'{getattr(arg, 'id', ast.dump(arg)[:40])}' não passou por {_FATIA}()")

    assert vistos >= 3, f"esperava achar chamadas de {_HASH} no app; achei {vistos}"
    assert not violacoes, (
        "board NÃO fatiado indo para o hash — grava com uma chave e procura com outra:\n  "
        + "\n  ".join(violacoes))
    print(f"OK  test_todo_hash_do_app_recebe_board_fatiado ({vistos} chamadas)")


def test_fatia_corta_por_street():
    from leaklab.gto_utils import board_for_street
    river = ['Qd', 'Th', '7h', '7s', '3h']
    assert board_for_street(river, 'preflop') == []
    assert board_for_street(river, 'flop') == ['Qd', 'Th', '7h']
    assert board_for_street(river, 'turn') == ['Qd', 'Th', '7h', '7s']
    assert board_for_street(river, 'river') == river
    assert board_for_street(river, 'FLOP') == ['Qd', 'Th', '7h'], 'street tem que ser case-insensitive'
    assert board_for_street([], 'flop') == []
    assert board_for_street(None, 'flop') == []
    # street desconhecida NÃO pode virar lista vazia: silenciar seria pior que passar reto
    assert board_for_street(river, 'showdown') == river
    print("OK  test_fatia_corta_por_street")


def test_board_inteiro_produz_hash_DIFERENTE_do_fatiado():
    """O que torna o esquecimento fatal: não é um hash aproximado, é outro spot.
    Se este teste passasse a falhar, a fatia teria virado inócua e o guarda acima, teatro."""
    from leaklab.gto_utils import compute_spot_hash, board_for_street
    river = ['Qd', 'Th', '7h', '7s', '3h']
    mao = ['Jc', 'Kd']
    inteiro = compute_spot_hash('flop', 'UTG+1', river, mao, 21.82, 6.0)
    fatiado = compute_spot_hash('flop', 'UTG+1', board_for_street(river, 'flop'), mao, 21.82, 6.0)
    assert inteiro != fatiado, 'a fatia não mudou o hash — o guarda estrutural viraria decoração'
    print("OK  test_board_inteiro_produz_hash_DIFERENTE_do_fatiado")


if __name__ == '__main__':
    falhas = 0
    for t in (test_todo_hash_do_app_recebe_board_fatiado,
              test_fatia_corta_por_street,
              test_board_inteiro_produz_hash_DIFERENTE_do_fatiado):
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f"FALHOU  {t.__name__}: {e}")
    # Formato COM barras: o runner faz `split('Passed:')[1].split('|')[0]`, e sem o separador
    # ele estoura em vez de contar — o teste passaria e a suíte inteira quebraria.
    print(f"\nTotal: 3 | Passed: {3 - falhas} | Failed: {falhas}")
    sys.exit(1 if falhas else 0)
