# -*- coding: utf-8 -*-
"""
Revisor do texto gerado — concordancia dos termos de poker.

── A ancora deste arquivo e o texto REAL que o usuario recebeu ────────────────────────────────────

Ele colou a explicacao do desafio do dia e apontou tres coisas: "ir straight para o shove", "ruas
de decisao" e "se shover toda vez". O primeiro teste passa esse paragrafo inteiro, sem recortar,
e exige que o revisor ache os tres. Um revisor testado so com frases que eu mesmo inventei
provaria que ele acha o que eu previ, e nao o que o modelo de fato escreve.

── O que este arquivo trava ───────────────────────────────────────────────────────────────────────

1. Que os tres problemas reais sejam detectados.
2. Que o revisor NAO reescreva o que exigiria mexer na oracao. Remendo cego produz portugues
   quebrado, e frase quebrada e pior que termo torto: o termo o leitor contorna, a frase nao.
3. Que ele nao acuse as formas CONSAGRADAS ('shovou', 'foldou'). Revisor que acusa o certo treina
   quem o le a ignora-lo, e ai ele deixa de servir.
4. Que ele nao acuse 'straight' quando a palavra e a MAO, que e o uso legitimo.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.revisor_pt import problemas, revisar, instrucao_de_correcao

# O paragrafo exato que o usuario recebeu na tela, sem recorte.
_TEXTO_REAL = (
    "O KK aqui e uma mao premium que voce deve defender agressivamente, mas a profundidade de "
    "apenas 40bb cria uma tensao estrategica deliciosa: voce pode 4-bet e deixar a decisao aberta "
    "pos-flop com controle do pote, ou ir straight para o shove e forcar o vilao a tomar a decisao "
    "mais dificil agora mesmo. O GTO mistura porque o CO esta 3-bettando de uma posicao forte, e "
    "seu range de CO inclui desde maos premium ate bluffs com conectores, entao voce nao pode "
    "sempre fazer a mesma coisa: se shover toda vez, vilao nunca paga com maos marginais e voce "
    "perde value. Com 40bb a profundidade muda tudo: e fundo demais para simplesmente fold, mas "
    "raso demais para ter muitas ruas de decisao confortaveis pos-flop."
)


def test_acha_os_TRES_problemas_do_texto_real():
    """A prova de que o revisor detecta. Sem ela, 'zero problemas' seria indistinguivel de um
    revisor que nao olha nada — o resultado tranquilizador que este projeto ja pagou caro."""
    tipos = {p['tipo'] for p in problemas(_TEXTO_REAL)}
    trechos = ' | '.join(p['trecho'] for p in problemas(_TEXTO_REAL))
    assert 'termo_como_palavra_comum' in tipos, trechos   # "straight para"
    assert 'conjugacao_inventada' in tipos, trechos        # "shover", "3-bettando"
    assert 'termo_traduzido' in tipos, trechos             # "ruas"


def test_o_trecho_acusado_e_o_certo():
    """Acusar sem apontar onde nao serve para regerar nem para revisar a mao."""
    achados = {p['trecho'].lower() for p in problemas(_TEXTO_REAL)}
    assert any('straight para' in a for a in achados), achados
    assert 'shover' in achados, achados
    assert 'ruas' in achados, achados


def test_corrige_o_inequivoco_e_DEVOLVE_o_resto():
    t, graves = revisar(_TEXTO_REAL)
    assert 'ruas' not in t.lower(), 'a troca 1 para 1 tinha que ter sido aplicada'
    assert 'streets de decisao' in t
    # o que exige reescrever a oracao continua la, e volta na lista
    assert 'shover' in t
    assert any(p['tipo'] == 'conjugacao_inventada' for p in graves), graves


def test_NAO_acusa_as_formas_consagradas():
    """'shovou' e 'foldou' sao o jeito CERTO. Revisor que acusa o certo treina quem o le a
    ignora-lo, e ai ele deixa de servir para qualquer coisa.

    A protecao e a lista de terminacoes ser FECHADA e nao conter `-ou`. A primeira versao tinha
    tambem uma lista de excecao, e ela era codigo morto: `-ou` nunca casava, entao a excecao nunca
    era consultada. O teste passava pelo motivo errado, e so a sabotagem revelou isso."""
    ok = "O vilao shovou de SB e o heroi foldou. Depois ele limpou de BTN."
    assert problemas(ok) == [], problemas(ok)


def test_a_protecao_das_consagradas_e_a_terminacao_FECHADA():
    """Trava o mecanismo, e nao so o resultado. Se alguem adicionar `-ou` a lista de terminacoes
    achando que amplia a deteccao, as formas certas passam a ser acusadas e este teste cai."""
    from leaklab.revisor_pt import _CONJUGADO
    assert 'ou' not in _CONJUGADO.pattern.split('(')[-1], _CONJUGADO.pattern
    for certa in ('shovou', 'foldou', 'limpou'):
        assert not _CONJUGADO.search(certa), certa


def test_NAO_acusa_straight_quando_e_a_MAO():
    """O uso legitimo. Acusar aqui seria pedir para o texto parar de falar da mao."""
    assert problemas("Voce tinha um straight no turn e o board pareou.") == []
    assert problemas("O flush bate o straight.") == []


def test_acusa_rotulo_de_frequencia_em_ingles():
    p = problemas("Weekly: treine SB. Depois revise.")
    assert any(x['tipo'] == 'rotulo_em_ingles' for x in p), p


def test_travessao_e_trocado_por_virgula():
    t, _ = revisar("O KK e premium — voce deve defender.")
    assert '—' not in t and 'premium, voce' in t


def test_preserva_a_caixa_no_inicio_da_frase():
    t, _ = revisar("Ruas seguintes ficam dificeis.")
    assert t.startswith('Streets'), t


def test_texto_limpo_nao_gera_problema_nem_muda():
    limpo = ("Com 40bb voce pode dar 4-bet e manter controle do pote, ou dar shove e forcar a "
             "decisao. As streets seguintes ficam curtas.")
    t, graves = revisar(limpo)
    assert graves == [] and t == limpo


def test_texto_vazio_nao_estoura():
    assert problemas('') == [] and problemas(None) == []
    assert revisar(None) == ('', [])


def test_a_instrucao_de_correcao_cita_o_TRECHO():
    """'Evite anglicismos' o modelo ja recebeu no prompt e ignorou. 'Voce escreveu X, corrija' e
    acionavel."""
    _, graves = revisar(_TEXTO_REAL)
    instr = instrucao_de_correcao(graves)
    assert 'shover' in instr and 'straight para' in instr.lower(), instr
    assert instrucao_de_correcao([]) == ''


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
