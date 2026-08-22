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
from test_i18n_copy_do_frontend import _sem_comentario, _PORTUGUES, _LITERAL, _FRONT  # noqa

# Texto entre `>` e `<` com pelo menos uma palavra de 3+ letras. Exclui o que e so
# {expressao}, espaco ou pontuacao.
_JSX = re.compile(r'>([^<>{}]*[A-Za-zÀ-ÿ]{3}[^<>{}]*)<')
# Template literal com interpolacao: `Assinar ${x} - ${y}`. A v2 tambem perdia estes.
_TEMPLATE = re.compile(r'`([^`]*[A-Za-zÀ-ÿ]{3}[^`]*)`')
_URLISH = re.compile(r'^\S+\.(com|br|io|net|org|gg|tsx?|jsx?|json|svg|png)(/\S*)?$', re.I)


def literais(texto):
    for m in _LITERAL.finditer(texto):
        yield m.start(), (m.group(1) or m.group(2)), 'aspas'
    for m in _JSX.finditer(texto):
        bruto = ' '.join(m.group(1).split())
        if bruto:
            yield m.start(), bruto, 'jsx'
    for m in _TEMPLATE.finditer(texto):
        bruto = ' '.join(m.group(1).split())
        if bruto:
            yield m.start(), bruto, 'template'


def portugues(lit):
    if _URLISH.match(lit):
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
            achados = [(texto.count('\n', 0, p) + 1, lit, origem)
                       for p, lit, origem in literais(texto) if portugues(lit)]
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
            for n, lit, origem in detalhe[rel]:
                print('  %5d [%s] %s' % (n, origem, lit[:105]))
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
