"""
test_trainer_catalog.py — os treinos com nome, e o que eles NÃO podem afirmar.

O catálogo é camada de apresentação sobre o que já rodava: o motor sempre aceitou um foco
(`adaptive` / `fund:<cenário>` / `leak:<chave>`) e a tela sempre soube abrir por `?foco=`. O que
faltava era agência — a chave interna é `vs_3bet:HJ:BTN:50`, que ninguém pede em voz alta.

O que está travado aqui:

1. **Todo foco do catálogo tem que ser um foco que o motor aceita.** Se alguém renomear um cenário
   e esquecer do catálogo, o jogador clica num treino e cai no fallback genérico sem entender por
   quê. É a falha silenciosa clássica: a tela funciona, o treino é outro.
2. **Nunca praticado é `None`, nunca `0`.** Zero afirma desempenho; ausência de dado não afirma
   nada. Mesma régua do relatório de evolução, onde célula sem dado nunca vira zero.
3. **O agregado por prefixo tem que somar as chaves certas.** Prefixo errado mistura o histórico de
   um cenário no de outro, e o número fica plausível — que é o pior tipo de errado.
4. **O adaptativo é o primeiro e é destaque.** Se o catálogo virar a entrada principal, o produto
   troca fisioterapeuta por academia.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.trainer_catalog as TC


class _Linha(dict):
    def __getitem__(self, k):
        return dict.get(self, k)


def _com_historico(linhas):
    original = TC._historico
    TC._historico = lambda uid: [_Linha(x) for x in linhas]
    return original


def test_todo_foco_do_catalogo_e_aceito_pelo_motor():
    """O foco é um contrato entre o catálogo e o `leaktrainer_next`. Quebrar em silêncio faz o
    jogador treinar outra coisa achando que treina a que escolheu."""
    from leaklab.leak_trainer import TRAINABLE_SCENARIOS, fundamentals_catalog
    for item in TC.CATALOGO:
        foco = item['foco']
        if item.get('rota'):
            # Item com TELA PROPRIA (o modo grind) nao passa pelo Leak Trainer, entao o
            # `foco` dele nao precisa ser um foco do motor. O que ele precisa e de ROTA:
            # sem ela o cartao nao leva a lugar nenhum e o jogador clica no vazio.
            assert str(item['rota']).startswith('/'), f"rota invalida em {item['id']}"
            continue
        if foco == 'adaptive':
            continue
        assert foco.startswith('fund:'), f'foco fora do contrato: {foco}'
        cenario = foco.split(':', 1)[1]
        if cenario == 'range_grid':
            continue                       # tratado por caminho próprio no endpoint
        assert cenario in TRAINABLE_SCENARIOS, f'{cenario} nao e cenario treinavel'
        assert fundamentals_catalog(cenario), f'{cenario} nao produz categoria nenhuma'
    print('OK  test_todo_foco_do_catalogo_e_aceito_pelo_motor')


def test_nunca_praticado_e_None_e_nao_zero():
    original = _com_historico([])
    try:
        for d in TC.catalogo_do_jogador(1):
            assert d['maos'] is None, f"{d['id']}: maos deveria ser None, veio {d['maos']!r}"
            assert d['acerto'] is None, f"{d['id']}: acerto deveria ser None, veio {d['acerto']!r}"
    finally:
        TC._historico = original
    print('OK  test_nunca_praticado_e_None_e_nao_zero')


def test_praticado_com_zero_acerto_mostra_zero_de_verdade():
    """O contraponto do teste acima: quem praticou 10 e errou 10 tem 0% REAL, e isso precisa
    aparecer. Se o código confundisse 'sem dado' com 'zero', esconderia o pior caso."""
    original = _com_historico([{'category_key': 'rfi:UTG::50', 'attempts': 10, 'correct': 0}])
    try:
        abrir = next(d for d in TC.catalogo_do_jogador(1) if d['id'] == 'abrir')
        assert abrir['maos'] == 10, abrir
        assert abrir['acerto'] == 0.0, abrir
    finally:
        TC._historico = original
    print('OK  test_praticado_com_zero_acerto_mostra_zero_de_verdade')


def test_prefixo_nao_mistura_cenarios():
    """`vs_rfi:` não pode capturar `rfi:`, e vice-versa. O número misturado é plausível, que é o
    pior tipo de errado — ninguém desconfia dele."""
    original = _com_historico([
        {'category_key': 'rfi:UTG::50',        'attempts': 10, 'correct': 10},
        {'category_key': 'vs_rfi:SB:BTN:100',  'attempts': 20, 'correct': 10},
        {'category_key': 'vs_3bet:HJ:BTN:50',  'attempts': 4,  'correct': 1},
    ])
    try:
        por_id = {d['id']: d for d in TC.catalogo_do_jogador(1)}
        assert por_id['abrir']['maos'] == 10, por_id['abrir']
        assert por_id['abrir']['acerto'] == 100.0, por_id['abrir']
        assert por_id['defender']['maos'] == 20, por_id['defender']
        assert por_id['defender']['acerto'] == 50.0, por_id['defender']
        assert por_id['vs_3bet']['maos'] == 4, por_id['vs_3bet']
        # o adaptativo soma TUDO
        assert por_id['meus_leaks']['maos'] == 34, por_id['meus_leaks']
    finally:
        TC._historico = original
    print('OK  test_prefixo_nao_mistura_cenarios')


def test_adaptativo_e_o_primeiro_e_o_destaque():
    """Ordem é decisão de produto: o catálogo é a porta para quem sabe o que quer, e a prescrição
    por leak é o que ele encontra quando não sabe."""
    assert TC.CATALOGO[0]['id'] == 'meus_leaks', 'o adaptativo saiu do topo'
    assert TC.CATALOGO[0]['foco'] == 'adaptive'
    destaques = [c['id'] for c in TC.CATALOGO if c.get('destaque')]
    assert destaques == ['meus_leaks'], f'destaque errado: {destaques}'
    print('OK  test_adaptativo_e_o_primeiro_e_o_destaque')


def test_banco_fora_do_ar_nao_derruba_o_catalogo():
    """A vitrine não depende do histórico. Sem ele, mostra os treinos sem número em vez de
    sumir da tela."""
    original = TC._historico

    def explode(uid):
        raise RuntimeError('banco fora do ar')
    TC._historico = explode
    try:
        d = TC.catalogo_do_jogador(1)
        assert len(d) == len(TC.CATALOGO), d
        assert all(x['acerto'] is None for x in d), d
    finally:
        TC._historico = original
    print('OK  test_banco_fora_do_ar_nao_derruba_o_catalogo')


def test_todo_treino_tem_texto_nas_tres_locales():
    """Texto novo sem as 3 locales aparece como a CHAVE na tela do usuário."""
    import json
    base = os.path.join(os.path.dirname(__file__), '..', '..',
                        'frontend', 'src', 'i18n', 'locales')
    for loc in ('pt-BR', 'en', 'es'):
        with open(os.path.join(base, loc, 'training.json'), encoding='utf-8') as f:
            d = json.load(f)
        cat = d.get('catalog') or {}
        assert cat, f'{loc}: bloco catalog ausente'
        for chave in ('title', 'subtitle', 'never', 'hands'):
            assert cat.get(chave), f'{loc}: falta catalog.{chave}'
        for item in TC.CATALOGO:
            drill = (cat.get('drills') or {}).get(item['id']) or {}
            assert drill.get('name'), f"{loc}: falta nome de {item['id']}"
            assert drill.get('desc'), f"{loc}: falta descricao de {item['id']}"
    print('OK  test_todo_treino_tem_texto_nas_tres_locales')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
