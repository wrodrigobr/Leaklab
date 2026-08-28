"""
trainer_catalog.py — os treinos com NOME, para o jogador escolher o que praticar.

O motor do treino sempre soube receber um foco (`adaptive` / `fund:<cenário>` / `leak:<chave>`) e a
tela sempre soube abrir num foco (`/leak-trainer?foco=`). O que faltava era **agência**: quem chega
sabendo o que quer treinar hoje não tinha como pedir, porque não havia vitrine nem nome. A chave
que o sistema usa por dentro é `vs_3bet:HJ:BTN:50`, que é linguagem de banco, não de jogador.

Este módulo é só a camada de apresentação em cima do que já roda. **Não há motor novo aqui** — se
houvesse, seria a segunda fonte de verdade sobre o que é treinável, e este projeto já pagou caro
por segundas fontes.

## Duas decisões que valem explicar

**O adaptativo continua sendo o primeiro da lista, e é o padrão.** O catálogo é a porta para quem
chega sabendo o que quer; a prescrição por leak é o que ele encontra quando não sabe. Se o catálogo
virasse a entrada principal, o produto trocaria fisioterapeuta por academia — e a academia qualquer
um tem.

**Treino nunca praticado mostra `—`, nunca `0%`.** Zero é uma afirmação sobre desempenho; ausência
de dado é outra coisa. É a mesma régua do relatório de evolução, onde célula sem dado nunca vira
zero.
"""
from __future__ import annotations

from typing import Optional

# (id, foco, prefixo da category_key para somar o histórico)
#
# O `prefixo` é como o treino reencontra o que o jogador já praticou: as chaves gravadas são
# `rfi:UTG::50`, `vs_rfi:SB:BTN:100`, `vs_3bet:HJ:BTN:50`. Prefixo `None` = soma tudo (o adaptativo
# cobre qualquer categoria); prefixo `''` = não há histórico agregável para este treino.
# `rota` só aparece em item que NÃO abre o Leak Trainer. O modo grind é uma tela própria porque o
# laço é outro (percorrer os passos de uma mão), mas entra como ITEM do catálogo e não como modo à
# parte — é como o próprio GTO Wizard trata: "Full Hand" é um drill, não um modo.
CATALOGO = [
    # `ilustracao` diz QUAL desenho o card usa. Mora aqui, junto do resto da definicao do treino,
    # em vez de a tela adivinhar pelo `id`: um treino novo sem ilustracao aparece sem desenho, que
    # e honesto, em vez de cair num desenho de outro spot.
    {'id': 'meus_leaks', 'foco': 'adaptive',        'prefixo': None,      'destaque': True},
    {'id': 'grind',      'foco': 'grind',           'prefixo': '',        'rota': '/grind',
     'ilustracao': 'mesa'},
    {'id': 'abrir',      'foco': 'fund:rfi',        'prefixo': 'rfi:',    'ilustracao': 'abrir'},
    {'id': 'defender',   'foco': 'fund:vs_rfi',     'prefixo': 'vs_rfi:', 'ilustracao': 'defender'},
    {'id': 'vs_3bet',    'foco': 'fund:vs_3bet',    'prefixo': 'vs_3bet:','ilustracao': 'vs_3bet'},
    {'id': 'ranges',     'foco': 'fund:range_grid', 'prefixo': '',        'ilustracao': 'abrir'},
]


def _historico(user_id: int) -> list:
    from database.schema import get_conn
    from database.repositories import _adapt
    conn = get_conn()
    try:
        return conn.execute(_adapt(
            "SELECT category_key, attempts, correct FROM training_skill_progress WHERE user_id=?"),
            (user_id,)).fetchall()
    finally:
        conn.close()


def catalogo_do_jogador(user_id: Optional[int]) -> list[dict]:
    """O catálogo com o histórico do jogador em cada treino.

    `maos` e `acerto` vêm `None` quando ele nunca praticou aquilo — e a tela mostra `—`. A conta é
    de TODO o histórico, não da sessão: o número responde "como eu vou nisto", não "como fui agora".
    """
    try:
        linhas = _historico(user_id) if user_id else []
    except Exception:
        linhas = []                       # sem histórico o catálogo ainda serve; ele não depende disso

    fora = []
    for item in CATALOGO:
        pref = item.get('prefixo')
        if pref is None:
            casadas = list(linhas)
        elif pref == '':
            casadas = []
        else:
            casadas = [r for r in linhas if (r['category_key'] or '').startswith(pref)]
        tent = sum(int(r['attempts'] or 0) for r in casadas)
        cert = sum(int(r['correct'] or 0) for r in casadas)
        fora.append({
            'id':      item['id'],
            'foco':    item['foco'],
            'rota':    item.get('rota'),
            'destaque': bool(item.get('destaque')),
            'ilustracao': item.get('ilustracao'),
            # None, e não 0: nunca praticado não é desempenho zero
            'maos':    tent or None,
            'acerto':  (round(cert * 100.0 / tent, 1) if tent else None),
        })
    return fora
