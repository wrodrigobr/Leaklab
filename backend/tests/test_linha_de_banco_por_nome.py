# -*- coding: utf-8 -*-
"""Linha de banco se le por NOME, nunca por indice nem desempacotando (07/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Na homologacao do pacote de 07/09 contra Postgres de verdade, o modal "contra quem" dava 500:
"could not convert string to float: 'effective_stack_bb'". No Postgres a linha e um dict
(RealDictCursor): desempacotar (`for a, b, c in rows`) itera as CHAVES, e `r[0]` e KeyError.
No SQLite (`sqlite3.Row`) os dois funcionam, entao a suite inteira passou verde com tres
funcoes novas quebradas em prod. E a classe de bug numero 8 da lista de "SQLite tolera,
Postgres rejeita" (ver memoria project_production_live).

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Varre `repositories.py` e acusa (1) `r[N]` / `row[N]` sem guarda `isinstance(..., dict)` na
mesma linha, e (2) `for a, b, ... in rows:` (desempacotamento de linhas). As ocorrencias
antigas sao todas guardadas por isinstance; a lista de excecoes fica VAZIA de proposito.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_REPO = os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py')

_INDICE = re.compile(r"\b(r|row|linha)\[\d\]")
_DESEMPACOTA = re.compile(r"^\s*for\s+[a-z_0-9]+(?:\s*,\s*[a-z_0-9]+)+\s+in\s+rows\s*:")   # `is_3bet` tem digito


def _ocorrencias():
    fonte = open(_REPO, encoding='utf-8').read().splitlines()
    achados = []
    for n, linha in enumerate(fonte, 1):
        sem_comentario = linha.split('#', 1)[0]
        if _INDICE.search(sem_comentario) and 'isinstance' not in sem_comentario:
            achados.append((n, 'indice', linha.strip()[:100]))
        if _DESEMPACOTA.match(sem_comentario):
            achados.append((n, 'desempacota', linha.strip()[:100]))
    return achados


def test_nenhuma_linha_de_banco_lida_por_indice_ou_desempacotada():
    achados = _ocorrencias()
    assert not achados, 'linha de banco por indice/desempacotamento (quebra no Postgres):\n' + '\n'.join(
        '  repositories.py:%d [%s] %s' % a for a in achados)


def test_o_varredor_acha_os_tres_casos_reais():
    """Os tres trechos que quebraram na homologacao, forjados: o varredor tem de acusar."""
    forjado = [
        "        if r[0] in vistas:",
        "        return [(r[0], r[1], r[2]) for r in rows]",
        "    for vs, vs_chart, pos_chart, stack, acao, is_3bet in rows:",
        "        spot = row['spot'] if isinstance(row, dict) else row[0]",      # guardado: nao acusa
        "    for r in rows:",                                                    # certo: nao acusa
    ]
    acusa = [l for l in forjado if (_INDICE.search(l) and 'isinstance' not in l) or _DESEMPACOTA.match(l)]
    assert acusa == forjado[:3], acusa


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
