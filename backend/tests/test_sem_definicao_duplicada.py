# -*- coding: utf-8 -*-
"""Duas definicoes com o mesmo nome no mesmo modulo: a ultima vence, calada.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

10/08. Duas sessoes chegaram na MESMA necessidade por lados diferentes — o seletor de balde de
ranges precisa conferir a profundidade contra o stack, porque `_stack_bucket` satura nas duas
pontas. Uma veio pelas ranges de open/re-raise (0,2bb recebendo a carta de 10bb), a outra pelo
consumo da range de jam (3,9bb recebendo a de 10bb, o que virou duas acusacoes falsas medidas).

As duas criaram `_profundidade_compativel` **e** `_balde_da_carta`. Mesmos nomes, contratos
diferentes: `(stack_bb) -> rotulo | None` de um lado, `(stack_bb, is_pko) -> dict` do outro.

O merge do git **nao conflitou em nenhuma das quatro**. Elas caem em partes diferentes do arquivo,
entao para o git sao adicoes independentes. Sem marcador, sem aviso, e o arquivo importa limpo.

O que sobreviveria: a segunda `_balde_da_carta` sobrescrevendo a primeira, e os dois call sites da
primeira passando **um argumento so** — `TypeError` em `villain_open_range`, que e o caminho que
decide se a equity do produto e medida contra a range do vilao ou contra mao aleatoria.

── Por que um teste, e nao so cuidado ─────────────────────────────────────────────────────────

Porque este defeito nao aparece onde se olha. Nao ha conflito para resolver, o diff de cada lado
esta correto isoladamente, `python -c "import ..."` passa, e o erro so acontece na chamada. A
unica coisa que o pega antes de produzao e contar as definicoes.
"""
import ast
import collections
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# Modulos do motor: sao os que duas frentes editam ao mesmo tempo e os que gravam veredito.
_ALVOS = ['leaklab', 'database', 'api']


def _arquivos():
    for base in _ALVOS:
        raiz = os.path.join(_RAIZ, base)
        if not os.path.isdir(raiz):
            continue
        for dirpath, dirnames, nomes in os.walk(raiz):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for n in sorted(nomes):
                if n.endswith('.py'):
                    yield os.path.join(dirpath, n)


def _duplicadas(caminho):
    """Nomes definidos mais de uma vez no NIVEL DE TOPO do modulo.

    So o topo: `def` dentro de `if/try` e redefinicao condicional legitima (fallback de import),
    e metodo homonimo em classes diferentes nao colide. Reduzir o escopo e o que mantem o guarda
    sem falso positivo — guarda que grita a toa e desligado na semana seguinte.
    """
    try:
        arvore = ast.parse(io.open(caminho, encoding='utf-8').read())
    except SyntaxError:
        return {}
    nomes = []
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomes.append(no.name)
        elif isinstance(no, ast.Assign):
            # Constante de topo reatribuida some do mesmo jeito. `_MASSA_MINIMA_DE_JAM` definida
            # duas vezes com valores diferentes seria exatamente o mesmo silencio.
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id.isupper():
                    nomes.append(alvo.id)
    return {k: v for k, v in collections.Counter(nomes).items() if v > 1}


def test_nenhum_modulo_do_motor_define_o_mesmo_nome_duas_vezes():
    achados = []
    n = 0
    for f in _arquivos():
        n += 1
        for nome, vezes in _duplicadas(f).items():
            achados.append(f"{os.path.relpath(f, _RAIZ)}: `{nome}` definido {vezes}x")
    assert n > 50, f'a varredura so viu {n} arquivos — o caminho esta errado'
    assert not achados, (
        'definicao duplicada no topo do modulo (a ultima vence, calada):\n  ' + '\n  '.join(achados))


def test_o_VARREDOR_acusa_uma_duplicata_forjada():
    """CONTROLE, e ele e o teste que importa. Um varredor que nunca viu uma duplicata nao esta
    verificado — e este projeto ja teve dois guardas que passavam lendo zero arquivos."""
    import tempfile
    fonte = 'def f():\n    return 1\n\n\nX = 1\n\n\ndef f():\n    return 2\n\n\nX = 2\n'
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as fh:
        fh.write(fonte)
        caminho = fh.name
    try:
        d = _duplicadas(caminho)
        assert d.get('f') == 2, f'nao acusou a funcao duplicada: {d}'
        assert d.get('X') == 2, f'nao acusou a constante reatribuida: {d}'
    finally:
        os.unlink(caminho)

    # CONTROLE 2: o caso LEGITIMO nao pode acusar — `def` dentro de `try/except` e fallback de
    # import, padrao normal, e um guarda que reclama dele vira ruido e morre.
    legitimo = ('try:\n    from x import f\nexcept ImportError:\n    def f():\n        return 1\n'
                '\n\ndef g():\n    return 2\n')
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as fh:
        fh.write(legitimo)
        caminho2 = fh.name
    try:
        assert _duplicadas(caminho2) == {}, 'acusou um fallback de import, que e legitimo'
    finally:
        os.unlink(caminho2)


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
