"""
Leitura de linha que funciona nos DOIS bancos.

── Por que este módulo existe ────────────────────────────────────────────────────────────────

No SQLite a linha é `sqlite3.Row`/tupla e `row[0]` devolve a primeira coluna. No Postgres, com o
cursor de dicionário que a aplicação usa, a linha é um `dict` e `row[0]` levanta `KeyError: 0`.

O efeito é sempre o mesmo e sempre tardio: o script roda perfeito no desenvolvimento, alguém o
executa em produção meses depois e ele estoura com um traceback cru na primeira linha lida. Já
aconteceu com backfill, com auditoria e com diagnóstico nesta base.

`first_value` resolve o caso que responde por quase todas as ocorrências: `SELECT COUNT(*)` e
companhia, onde só existe uma coluna e o código quer o escalar.

`value` cobre o resto, e a ordem dos argumentos não é acidental: **nome primeiro, posição como
último recurso**. Nome sobrevive a mudança na ordem do SELECT; posição não.

Mora em `database/` porque é onde vivem as outras diferenças entre os dois bancos, e num arquivo
só porque a alternativa já foi tentada: cada script definiu o seu `_v` local, e o décimo esqueceu.
"""
from typing import Any


def first_value(row: Any, default: Any = None) -> Any:
    """Primeira coluna da linha, seja ela dict (PG) ou tupla (SQLite). `None` → `default`."""
    if row is None:
        return default
    if isinstance(row, dict):
        for v in row.values():
            return v
        return default
    try:
        return row[0]
    except (KeyError, IndexError, TypeError):
        return default


def value(row: Any, key: str, idx: int = 0, default: Any = None) -> Any:
    """Coluna por NOME, caindo para a posição só se o nome não existir.

    Use sempre com alias no SQL (`SELECT COUNT(*) AS n`): com alias, o nome funciona nos dois
    bancos e a posição nunca é exercida.
    """
    if row is None:
        return default
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return row[idx]
    except (KeyError, IndexError, TypeError):
        pass
    if isinstance(row, dict):
        vals = list(row.values())
        if idx < len(vals):
            return vals[idx]
    return default


def values(row: Any) -> list:
    """Linha inteira como lista posicional. Em dict, respeita a ordem das colunas do SELECT."""
    if row is None:
        return []
    if isinstance(row, dict):
        return list(row.values())
    return list(row)
