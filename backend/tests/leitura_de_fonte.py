# -*- coding: utf-8 -*-
"""`so_codigo(fonte)`: as linhas de um arquivo Python com COMENTARIOS e STRINGS apagados.

── Por que existe ─────────────────────────────────────────────────────────────────────────

Guarda que varre fonte com grep le tudo: comentario, docstring, mensagem de erro. Em 12/09 isso
produziu QUATRO resultados falsos num dia, nas duas direcoes:

  · um comentario meu com `score` + `=` + `?` ABSOLVEU uma porta no guarda do score;
  · um comentario com "`reveals=`" ACUSOU uma fiacao que estava intacta;
  · a docstring que explicava o bug do `fetchone()[0]` foi ACUSADA pelo guarda desse mesmo bug;
  · e o `test_row_access` acusou os comentarios do conserto, depois de ele estar feito.

Em todos, o texto que EXPLICA a cicatriz virou prova a favor ou contra. Regra 8 do CLAUDE.md diz
que comentario nao e evidencia; isto e a outra metade: comentario tambem nao pode ser prova
contraria. **Guarda que le fonte le CODIGO.**

**O nome nao comeca com `_` de proposito.** A primeira versao se chamava `_fonte.py` e o
`.gitignore` tem `backend/tests/_*.py` (a pasta usa esse prefixo para rascunho local). O
arquivo nunca foi commitado: a suite passava verde na minha maquina, onde ele existe, e os
dois guardas quebravam com ImportError em qualquer clone limpo. Quem achou foi a
homologacao, que clona do git. Ver `reference_worktree_faltam_artefatos_de_teste`.

Mora em `tests/` e num arquivo so porque a alternativa foi tentada no mesmo dia: dois guardas do
MESMO padrao (`test_linha_de_banco_por_nome` e `test_row_access`), cada um com a sua varredura, e
so um deles aprendeu a ignorar texto.

── Cuidado que custou uma quebra de proposito ─────────────────────────────────────────────

Apagar a LINHA INTEIRA por ela conter uma string cega o guarda justamente onde o bug vive:
`conn.execute("SELECT ...").fetchone()[0]` tem SQL inline na MESMA linha do indice. A primeira
versao fazia isso, e o script forjado com a forma real do bug nao movia o contador. So o TRECHO
do token e apagado, por coluna; a linha inteira sai apenas quando o token cobre varias linhas
(docstring).
"""
import io as _io
import tokenize as _tk


def so_codigo(fonte: str) -> dict:
    """`{numero_da_linha: texto_sem_comentario_nem_string}`.

    Arquivo que nao tokeniza (sintaxe invalida) volta cru: e melhor varrer com texto do que
    deixar de varrer.
    """
    linhas = {n: l for n, l in enumerate(fonte.splitlines(), 1)}
    try:
        toks = list(_tk.generate_tokens(_io.StringIO(fonte).readline))
    except (_tk.TokenError, IndentationError, SyntaxError):
        return linhas
    for t in toks:
        if t.type not in (_tk.COMMENT, _tk.STRING):
            continue
        if t.start[0] == t.end[0]:
            n = t.start[0]
            if n in linhas:
                l = linhas[n]
                linhas[n] = l[:t.start[1]] + ' ' * (t.end[1] - t.start[1]) + l[t.end[1]:]
        else:
            for n in range(t.start[0], t.end[0] + 1):
                if n in linhas:
                    linhas[n] = ''
    return linhas
