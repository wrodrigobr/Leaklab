#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Varre um acervo inteiro atrás de violações de invariante e falha se alguma PIOROU.

    python scripts/varre_invariantes.py                     # usa DATABASE_URL, ou o SQLite local
    python scripts/varre_invariantes.py --db caminho.sqlite # um snapshot
    python scripts/varre_invariantes.py --detalhe           # com linhas de exemplo
    python scripts/varre_invariantes.py --atualiza-baseline # depois de um conserto

Código de saída: 0 quando nada piorou, 1 quando alguma invariante cresceu. É o que permite
pendurar isto no deploy sem depender do CI (bloqueado por cobrança desde 01/08).

    ssh deploy@<host> 'docker compose exec -T api python scripts/varre_invariantes.py'

Rodar DEPOIS do reprocesso, não antes: número colhido com processo em andamento já me fez
concluir errado duas vezes no mesmo dia (CLAUDE.md, item 3).

── Sobre o baseline ───────────────────────────────────────────────────────────────────────────

Ele não é meta, é dívida medida. O que a varredura protege é a DIREÇÃO: um deploy pode consertar
e reduzir, nunca introduzir. `--atualiza-baseline` reescreve os números no módulo e deve entrar
no MESMO commit do conserto, senão a próxima varredura aceita a regressão de volta em silêncio.
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from leaklab.invariantes_acervo import INVARIANTES, melhorias, regressoes, varrer

MODULO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'leaklab', 'invariantes_acervo.py')


def _conectar(caminho):
    if caminho:
        import sqlite3
        return sqlite3.connect(f'file:{caminho}?mode=ro', uri=True)
    import database.schema as sch
    return sch.get_conn()


def _atualiza_baseline(resultado):
    """Reescreve os baselines que MELHORARAM. Nunca sobe um baseline: regressão se conserta,
    não se legaliza."""
    texto = io.open(MODULO, encoding='utf-8').read()
    mudou = []
    for r in melhorias(resultado):
        alvo = re.search(r"(id='%s', baseline=)(\d+)" % re.escape(r['id']), texto)
        if alvo and int(alvo.group(2)) != r['medido']:
            texto = texto[:alvo.start()] + alvo.group(1) + str(r['medido']) + texto[alvo.end():]
            mudou.append(f"{r['id']}: {alvo.group(2)} → {r['medido']}")
    if mudou:
        io.open(MODULO, 'w', encoding='utf-8').write(texto)
    return mudou


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', help='caminho de um SQLite (snapshot). Sem isto usa a conexão do app.')
    p.add_argument('--detalhe', action='store_true', help='mostra linhas de exemplo')
    p.add_argument('--atualiza-baseline', action='store_true')
    a = p.parse_args()

    conn = _conectar(a.db)
    resultado = varrer(conn)

    largura = max(len(r['id']) for r in resultado)
    print(f"{'invariante'.ljust(largura)}  baseline   medido    delta")
    print('-' * (largura + 30))
    for r in resultado:
        sinal = 'PIOROU' if r['delta'] > 0 else ('melhorou' if r['delta'] < 0 else '')
        print(f"{r['id'].ljust(largura)}  {r['baseline']:>8}  {r['medido']:>7}  "
              f"{r['delta']:>+7}  {sinal}")
        if a.detalhe and r['exemplos']:
            for e in r['exemplos']:
                print(f"{' ' * largura}    · {e}")

    piores = regressoes(resultado)
    melhores = melhorias(resultado)

    if melhores:
        print('\nMELHOROU (baixe o baseline no mesmo commit do conserto):')
        for r in melhores:
            print(f"  {r['id']}: {r['baseline']} → {r['medido']}")
        if a.atualiza_baseline:
            for linha in _atualiza_baseline(resultado):
                print(f'  baseline reescrito — {linha}')

    if piores:
        print('\nREGRESSÃO — alguma coisa que era impossível passou a existir:')
        for r in piores:
            print(f"  {r['id']}: {r['baseline']} → {r['medido']}  ({r['titulo']})")
            print(f"    porta: {r['porta']}")
            for e in r['exemplos']:
                print(f"    · {e}")
        return 1

    print('\nNenhuma invariante piorou.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
