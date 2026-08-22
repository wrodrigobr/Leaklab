# -*- coding: utf-8 -*-
"""Quanta copy em portugues ainda esta CRAVADA no codigo do frontend, e onde.

    python scripts/medir_copy_cravada.py            # placar por audiencia
    python scripts/medir_copy_cravada.py --detalhe  # cada string, com arquivo e linha
    python scripts/medir_copy_cravada.py Replayer --detalhe   # filtra por caminho

── Por que este script existe ─────────────────────────────────────────────────────────────

Uma pendencia sem numero envelhece calada. Esta tem numero, e ele so ficou honesto na
TERCEIRA tentativa -- as duas primeiras erraram por defeito do MEDIDOR, nunca do codigo:

    v1  so literais entre aspas .......................... 308
    v2  + texto JSX solto (`<h2>O que voce recebe</h2>`) .. 537
    v3  + template literal (`Assinar ${plano}`) .......... 628

As tres formas de escrever texto na tela sao equivalentes para quem LE, e so a primeira
estava sendo contada. Por isso o varredor olha as tres.

── O que NAO conta como divida ────────────────────────────────────────────────────────────

- `lib/api.ts`: valores de UNIAO que o backend envia ("alta" | "media" | "baixa"). Traduzir
  quebraria o contrato de dados.
- Componentes `ui/` (shadcn) e os bundles de `i18n/`.
- Comentario de desenvolvedor (recortado antes de varrer).
- Dominios e URLs (`pokerstars.com` casava "com" como palavra portuguesa).

E ha copy que e divida mas NAO deve ser traduzida, por decisao registrada:

- `pages/Privacy.tsx`: politica de privacidade. Traducao imprecisa de termo legal cria
  exposicao real, e em portugues o texto esta correto hoje.
- `pages/admin/*` e `components/admin/*`: o painel tem UM leitor, que fala portugues.
- `pages/coach/*`: 1 coach em producao. Vale quando houver coach que nao fale portugues.
"""
import os
import re
import sys

sys.path.insert(0, r'C:\Projetos\leaklab\backend\tests')
# Os detectores moram no TESTE e sao importados daqui: tê-los em dois arquivos foi
# exatamente o que deixou este medidor mais frouxo que o guarda por um tempo.
from test_i18n_copy_do_frontend import (  # noqa
    _sem_comentario, _PORTUGUES, _FRONT, _todo_texto_de_tela, _URLISH, _NAO_E_COPY)

def portugues(lit):
    if _URLISH.match(lit):
        return False
    # identificador que so PARECE copy (valor de tipo, termo de busca, chave de mapa, log)
    if any(marca in lit for marca in _NAO_E_COPY):
        return False
    return bool(_PORTUGUES.search(lit))


def audiencia(rel):
    p = rel.replace('\\', '/')
    if '/admin/' in p or p.startswith('admin/'):
        return 'admin'
    base = os.path.basename(p)
    if '/coach/' in p or p.startswith('coach/') or 'Coach' in base or 'Student' in base:
        return 'coach'
    return 'jogador'


def varrer(filtro=None):
    grupos = {'jogador': {}, 'coach': {}, 'admin': {}}
    detalhe = {}
    for raiz, _, nomes in os.walk(_FRONT):
        partes = raiz.replace('\\', '/').split('/')
        if 'i18n' in partes or 'ui' in partes:
            continue
        for nome in sorted(nomes):
            if not nome.endswith(('.ts', '.tsx')) or '.test.' in nome or '.spec.' in nome:
                continue
            caminho = os.path.join(raiz, nome)
            rel = os.path.relpath(caminho, _FRONT).replace('\\', '/')
            if rel == 'lib/api.ts':          # contrato de dados, nao copy
                continue
            if filtro and filtro not in rel:
                continue
            with open(caminho, encoding='utf-8') as fh:
                texto = _sem_comentario(fh.read())
            achados = [(texto.count('\n', 0, p) + 1, lit)
                       for p, lit in _todo_texto_de_tela(texto) if portugues(lit)]
            if achados:
                grupos[audiencia(rel)][rel] = len(achados)
                detalhe[rel] = achados
    return grupos, detalhe


if __name__ == '__main__':
    filtro = next((a for a in sys.argv[1:] if not a.startswith('--')), None)
    grupos, detalhe = varrer(filtro)
    if '--detalhe' in sys.argv:
        for rel in sorted(detalhe):
            print('\n=== %s (%d)' % (rel, len(detalhe[rel])))
            for n, lit in detalhe[rel]:
                print('  %5d  %s' % (n, lit[:110]))
    else:
        for quem in ('jogador', 'coach', 'admin'):
            g = grupos[quem]
            print('=== %s: %d arquivos, %d strings' % (quem, len(g), sum(g.values())))
            for rel, n in sorted(g.items(), key=lambda x: -x[1])[:18]:
                print('   %4d  %s' % (n, rel))
            resto = sorted(g.items(), key=lambda x: -x[1])[18:]
            if resto:
                print('   ... +%d arquivos, %d strings' % (len(resto), sum(n for _, n in resto)))
            print()
