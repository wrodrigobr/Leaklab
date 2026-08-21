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

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_FATIA = 'board_for_street'
_HASH = 'compute_spot_hash'

# ── O ALCANCE, e por que ele é este ───────────────────────────────────────────────────────────
#
# Existem DUAS fontes de board nesta base, e só uma é perigosa:
#
#   · board COMPLETO da mão — `decisions.board` no banco e `hand.board` no pipeline. Guarda as
#     cinco cartas em TODA decisão, inclusive nas de preflop. Quem lê daqui PRECISA cortar.
#   · board da STREET — `spot['board']`, que o parser acumula carta a carta conforme a mão anda
#     ("board só traz a(s) carta(s) nova(s), então acumulamos"). Já chega certo.
#
# O bug de 12/05 foi exatamente misturar as duas: o enfileiramento lia `d['board']` (completo) e
# o lookup do worker lia `spot['board']` (da street). Mesma decisão, dois hashes.
#
# Por isso o teste cobre os arquivos que leem da fonte PERIGOSA. `gto_solver.lookup_gto` e
# `strategy_provider` ficam de fora de propósito: lá o board é PARÂMETRO, entregue por um chamador
# que já está coberto aqui. Incluí-los produziria dez falsos positivos, e teste que grita onde não
# há problema é teste que alguém desliga.
_ARQUIVOS = [
    os.path.join('api', 'app.py'),
    os.path.join('database', 'repositories.py'),
]

# Recebe o board pronto de quem chama, pelo contrato acima. `insert_gto_nodes` ingere o RESULTADO
# do solver e as importações de range, e nos dois casos o board já vem na street correta.
# `_hashes_da_linha` monta as variantes de hash de UMA linha e recebe `board_for_hash`, que os
# dois chamadores (`app.py`) fatiam antes de passar.
#
# **A allowlist não é declaração de confiança: é contrato VERIFICADO.** Até 21/08 ela apenas
# pulava a função, e quem a alimentasse com board inteiro passava batido — o buraco pelo qual
# um `_hashes_da_linha` mal chamado entraria sem acusar nada. `test_allowlist_recebe_de_quem_
# fatia` confere cada chamador.
#
# São DOIS contratos, e misturá-los foi o que quase me fez enfraquecer o guarda:
#
#   `_INGERE_EXTERNO`     — o board vem de fora (payload do solver, arquivo de ranges) e já
#                           chega na street certa. Não há como conferir isso estaticamente:
#                           o dado nasce fora do nosso código.
#   `_RECEBE_DE_QUEM_FATIA` — o board vem de OUTRA função nossa. Aqui dá para cobrar, e o
#                           `test_allowlist_recebe_de_quem_fatia` cobra de cada chamador.
#
_INGERE_EXTERNO = {'insert_gto_nodes'}
_RECEBE_DE_QUEM_FATIA = {'_hashes_da_linha'}
_RECEBE_PRONTO = _INGERE_EXTERNO | _RECEBE_DE_QUEM_FATIA


def _apelidos(arvore, alvo):
    """Nomes locais que apontam para `alvo`, incluindo `import X as _y`.

    O teste original casava só o nome literal, e por isso não viu
    `from leaklab.gto_utils import compute_spot_hash as _csh` dentro do worker por mão — uma
    chamada com board não fatiado, no mesmo arquivo que o teste já varria. Guarda que se
    contorna com um apelido de duas letras não guarda nada.
    """
    nomes = {alvo}
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            for a in no.names:
                if a.name == alvo and a.asname:
                    nomes.add(a.asname)
    return nomes


def _nome_da_func(no):
    f = no.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)


def _arg_board(no):
    """3º posicional ou o keyword `board` — a chamada existe nas duas formas na base."""
    if len(no.args) >= 3:
        return no.args[2]
    for kw in no.keywords:
        if kw.arg == 'board':
            return kw.value
    return None


def test_todo_hash_recebe_board_fatiado():
    """Percorre cada função: nomes vindos de `board_for_street` são os únicos boards aceitáveis
    como argumento `board` de `compute_spot_hash`."""
    violacoes = []
    vistos = 0

    for rel in _ARQUIVOS:
        caminho = os.path.join(_BACKEND, rel)
        if not os.path.exists(caminho):
            continue
        arvore = ast.parse(open(caminho, encoding='utf-8').read())
        nomes_hash  = _apelidos(arvore, _HASH)
        nomes_fatia = _apelidos(arvore, _FATIA)

        for func in [n for n in ast.walk(arvore)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            # A allowlist isenta da VALIDAÇÃO, não da CONTAGEM. `vistos` existe para provar
            # que o teste ainda enxerga as chamadas (o zero tranquilizador de um varredor que
            # parou de casar nomes); descontá-lo ao isentar uma função faria o próprio guarda
            # de detecção encolher junto com a allowlist.
            isenta = func.name in _RECEBE_PRONTO
            # nomes que RECEBERAM a fatia dentro desta função
            fatiados = set()
            for no in ast.walk(func):
                if isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) \
                        and _nome_da_func(no.value) in nomes_fatia:
                    fatiados.update(a.id for a in no.targets if isinstance(a, ast.Name))

            for no in ast.walk(func):
                if not (isinstance(no, ast.Call) and _nome_da_func(no) in nomes_hash):
                    continue
                vistos += 1
                if isenta:
                    continue
                arg = _arg_board(no)
                if arg is None:
                    continue
                if isinstance(arg, ast.Name) and arg.id in fatiados:
                    continue
                # chamada aninhada direta: compute_spot_hash(..., board_for_street(b, s), ...)
                if isinstance(arg, ast.Call) and _nome_da_func(arg) in nomes_fatia:
                    continue
                # lista literal (constante no código) é explícita e não vem do banco
                if isinstance(arg, (ast.List, ast.Tuple)):
                    continue
                violacoes.append(
                    f"{rel}:{no.lineno} em {func.name}(): board "
                    f"'{getattr(arg, 'id', ast.dump(arg)[:44])}' não passou por {_FATIA}()")

    assert vistos >= 6, f"esperava achar chamadas de {_HASH}; achei {vistos}"
    assert not violacoes, (
        "board NÃO fatiado indo para o hash — grava com uma chave e procura com outra:\n  "
        + "\n  ".join(violacoes))
    print(f"OK  test_todo_hash_recebe_board_fatiado ({vistos} chamadas, {len(_ARQUIVOS)} arquivos)")


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


def test_allowlist_recebe_de_quem_fatia():
    """Quem está em `_RECEBE_PRONTO` promete receber o board já fatiado. Este teste cobra a
    promessa de cada CHAMADOR, em vez de acreditar nela.

    Sem isto a allowlist era um buraco: bastava alguém entrar nela para que o board inteiro
    passasse batido — e a única evidência de que estava tudo bem seria o comentário ao lado
    do nome. Comentário não é evidência.
    """
    violacoes = []
    conferidos = 0

    for rel in _ARQUIVOS:
        caminho = os.path.join(_BACKEND, rel)
        if not os.path.exists(caminho):
            continue
        arvore = ast.parse(open(caminho, encoding='utf-8').read())
        nomes_fatia = _apelidos(arvore, _FATIA)

        for func in [n for n in ast.walk(arvore)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            # nomes que receberam a fatia DENTRO desta função chamadora
            fatiados = set()
            for no in ast.walk(func):
                if isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) \
                        and _nome_da_func(no.value) in nomes_fatia:
                    fatiados.update(a.id for a in no.targets if isinstance(a, ast.Name))

            for no in ast.walk(func):
                if not (isinstance(no, ast.Call) and _nome_da_func(no) in _RECEBE_DE_QUEM_FATIA):
                    continue
                if func.name in _RECEBE_PRONTO:
                    continue          # recursão/encadeamento entre as próprias allowlisted
                conferidos += 1
                # Basta UM argumento vir da fatia: a assinatura varia por função, e o que
                # importa é que o board entregue tenha passado por `board_for_street`.
                argumentos = list(no.args) + [k.value for k in no.keywords]
                ok = any(
                    (isinstance(a, ast.Name) and a.id in fatiados)
                    or (isinstance(a, ast.Call) and _nome_da_func(a) in nomes_fatia)
                    for a in argumentos)
                if not ok:
                    violacoes.append(
                        f"  {rel}:{no.lineno} em {func.name}(): chamada a "
                        f"{_nome_da_func(no)}() sem board vindo de {_FATIA}()")

    assert conferidos > 0, (
        'nenhuma chamada a função da allowlist foi encontrada — o teste não está medindo '
        'nada (os arquivos varridos ou os nomes da allowlist mudaram?)')
    assert not violacoes, (
        'função da allowlist recebendo board NÃO fatiado:\n' + '\n'.join(violacoes))
    print(f"OK  test_allowlist_recebe_de_quem_fatia ({conferidos} chamadas conferidas)")


if __name__ == '__main__':
    falhas = 0
    for t in (test_todo_hash_recebe_board_fatiado,
              test_allowlist_recebe_de_quem_fatia,
              test_fatia_corta_por_street,
              test_board_inteiro_produz_hash_DIFERENTE_do_fatiado):
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f"FALHOU  {t.__name__}: {e}")
    # Formato COM barras: o runner faz `split('Passed:')[1].split('|')[0]`, e sem o separador
    # ele estoura em vez de contar — o teste passaria e a suíte inteira quebraria.
    print(f"\nTotal: 4 | Passed: {4 - falhas} | Failed: {falhas}")
    sys.exit(1 if falhas else 0)
