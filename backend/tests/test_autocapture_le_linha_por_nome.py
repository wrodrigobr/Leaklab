# -*- coding: utf-8 -*-
"""A captura automatica de preflop estava MORTA em producao, em silencio (12/09).

── O caso ─────────────────────────────────────────────────────────────────────────────────

`_coverable_null_pairs` e `_regrade_tournament` liam o `raw_text` assim:

    row = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()
    if not row or not row[0]:

No Postgres, `fetchone()` devolve `dict` (o wrapper `_PgResult` faz `dict(row)`), e `row[0]` e
`KeyError: 0`. O indice fica FORA do `try`, e o erro sobe para o `except Exception` de
`run_autocapture`, que apenas escreve um warning. Resultado: **desde que o Postgres entrou, a
captura automatica nunca capturou nada em producao**, sem erro na tela, sem alerta, sem nada.

Provado NO AMBIENTE (nao lendo o codigo): chamando `_coverable_null_pairs` dentro do container
de producao, num torneio real, a resposta foi `KeyError 0`.

Em SQLite (`sqlite3.Row`) o indice funciona, e por isso nada nunca acusou. Somava-se a isso o
fato de **nao existir teste nenhum para este modulo**: o bug nao tinha como ser visto.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Um duble de conexao que devolve a linha como `dict`, exatamente como o Postgres. As duas
funcoes tem de LER o texto e seguir. Se alguem voltar a indexar por posicao, elas estouram
`KeyError` aqui, no SQLite da suite, sem precisar de Postgres.

O par negativo importa tanto quanto: com `raw_text` vazio as duas devolvem vazio SEM estourar
(e o caminho legitimo de "torneio sem texto guardado").
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import preflop_autocapture as pac                                  # noqa: E402

_RAW = """***** Hand History For Game 1789081437700muevx600gf *****
12500/25000 Tourney Texas Holdem Game Table (NL) (MTT Tournament #422627148) (Buyin $5.0 + $0.5) - Thu Sep 10 19:03:16 EDT 2026
Table (422627148) Table #12 (Real Money) -- Seat 1 is the button
Total number of players : 3/3
Seat 1: Player1 (698456)
Seat 2: Hero (448615)
Seat 3: Player3 (686443)
Hero posts small blind (12500)
Player3 posts big blind (25000)
** Dealing down cards **
Dealt to Hero [  Qh, Ad ]
Player1 folds
Hero calls (12500)
Player3 checks
"""


class _CursorPG:
    """O que o wrapper `_PgResult` entrega: linha como dict, nunca indexavel por posicao."""

    def __init__(self, linhas):
        self._linhas = linhas

    def fetchone(self):
        return dict(self._linhas[0]) if self._linhas else None

    def fetchall(self):
        return [dict(r) for r in self._linhas]

    def __iter__(self):
        return iter(self.fetchall())


class _ConnPG:
    """Duble minimo: responde a pergunta do `raw_text` como o Postgres responderia."""

    def __init__(self, raw):
        self._raw = raw
        self.vistas = []

    def execute(self, sql, params=None):
        self.vistas.append(' '.join((sql or '').split()))
        low = (sql or '').lower()
        if 'from tournaments' in low and 'raw_text' in low:
            return _CursorPG([{'raw_text': self._raw}] if self._raw is not None else [])
        return _CursorPG([])          # qualquer outro SELECT: vazio, e suficiente para o teste

    def commit(self):
        pass

    def close(self):
        pass


def test_coverable_null_pairs_le_o_raw_text_como_no_postgres():
    conn = _ConnPG(_RAW)
    pares = pac._coverable_null_pairs(conn, 9401)     # nao pode estourar KeyError
    assert isinstance(pares, set), type(pares)
    # CONTROLE: a funcao realmente PERGUNTOU pelo raw_text. Sem isto, uma versao que devolvesse
    # set() na primeira linha passaria sem exercitar nada.
    assert any('raw_text' in s and 'tournaments' in s for s in conn.vistas), conn.vistas


def test_regrade_tournament_le_o_raw_text_como_no_postgres():
    conn = _ConnPG(_RAW)
    n = pac._regrade_tournament(conn, 9401)           # nao pode estourar KeyError
    assert n == 0, n                                  # sem decisoes gravadas no duble
    assert any('raw_text' in s and 'tournaments' in s for s in conn.vistas), conn.vistas


def test_as_duas_funcoes_aceitam_torneio_SEM_texto():
    """Par negativo: `raw_text` nulo e o caminho legitimo, e tem de sair quieto."""
    for raw in (None, ''):
        conn = _ConnPG(raw)
        assert pac._coverable_null_pairs(conn, 9401) == set()
        assert pac._regrade_tournament(conn, 9401) == 0


def test_o_duble_PROVA_que_pegaria_o_bug():
    """CONTROLE DO DUBLE. Se ele aceitasse indice por posicao, os tres testes acima passariam
    com o bug de volta. Aqui o duble e exercitado contra a forma ANTIGA do codigo."""
    conn = _ConnPG(_RAW)
    row = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (9401,)).fetchone()
    assert isinstance(row, dict), type(row)
    try:
        _ = row[0]
        assert False, 'o duble aceitou indice por posicao: ele nao imita o Postgres'
    except KeyError:
        pass
    assert row['raw_text'] == _RAW


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
