# -*- coding: utf-8 -*-
"""O resumo do plano de estudos nunca mostra JSON ao jogador (09/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

O dono abriu o proprio plano em PRODUCAO e disse "achei bem confuso". Era pior: o campo
`resumo` tinha 2.401 caracteres e terminava com o JSON de `nao_focar_agora` e
`observar_mais_dados` em texto cru — chaves, colchetes e aspas na tela do jogador. E os dois
campos NAO existiam no plano: o modelo fechou a aspas do resumo so no fim, o JSON continuou
valido, `json.loads` aceitou, e nos gravamos e exibimos sem conferir nada.

O defeito e NOSSO. Resposta de LLM e entrada nao confiavel, e entre `json.loads` e o cache nao
havia validacao nenhuma. O caso tambem explica por que a tela parecia quebrada sem estar: o
front renderiza `observar` e `naoFocar` como secoes proprias, so que elas nunca chegaram la.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. JSON dentro do resumo e cortado, e o que da para recuperar volta a ser campo;
2. resumo honesto passa intacto (a validacao nao pode mutilar o caso bom);
3. resumo comprido demais e cortado em fronteira de frase, nunca no meio da palavra.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.llm_explainer import _desaninha_resumo, LIMITE_DO_RESUMO      # noqa: E402

# a forma EXATA do que foi para a tela em producao (texto trocado, estrutura idêntica)
RESUMO_VAZADO = (
    'Jogador com padrao paradoxal: loose no preflop e tight na defesa do flop OOP. '
    'Os tres leaks principais custam 30 bb.", '
    '"nao_focar_agora": [ { "item": "SB river (2 decisoes)", "motivo": "Amostra pequena." } ], '
    '"observar_mais_dados": [ { "indicador": "BTN flop", "sample_atual": 2, '
    '"sample_necessario": 8, "por_que_esperar": "Aguarde mais maos." } ] }'
)


def test_o_json_sai_do_resumo_e_volta_a_ser_campo():
    plano = _desaninha_resumo({'nivel': 'intermediario', 'resumo': RESUMO_VAZADO, 'cards': [{'x': 1}]})
    r = plano['resumo']
    assert '"nao_focar_agora"' not in r and '{' not in r and '[' not in r, r[-120:]
    assert r.endswith('custam 30 bb.'), r[-40:]
    # e o que estava preso na string volta ao lugar, em vez de sumir
    assert len(plano.get('nao_focar_agora') or []) == 1, plano.get('nao_focar_agora')
    assert plano['nao_focar_agora'][0]['item'].startswith('SB river'), plano['nao_focar_agora']
    assert len(plano.get('observar_mais_dados') or []) == 1, plano.get('observar_mais_dados')
    assert plano['observar_mais_dados'][0]['sample_necessario'] == 8
    assert plano['cards'] == [{'x': 1}], 'o resto do plano nao pode ser tocado'


def test_resumo_honesto_passa_intacto():
    bom = ('Voce abre muito no pre-flop e defende de menos no flop fora de posicao. '
           'O caminho e ajustar a abertura no CO e no SB antes de mexer no pos-flop.')
    plano = _desaninha_resumo({'resumo': bom, 'cards': []})
    assert plano['resumo'] == bom, 'a validacao nao pode mexer no caso bom'


def test_resumo_comprido_e_cortado_em_frase():
    longo = ('Frase completa numero um sobre o perfil do jogador. ' * 40)
    plano = _desaninha_resumo({'resumo': longo, 'cards': []})
    r = plano['resumo']
    assert len(r) <= LIMITE_DO_RESUMO, len(r)
    assert r.endswith('.'), 'o corte tem de cair em fim de frase, nao no meio da palavra'


def test_sem_resumo_nao_quebra():
    assert _desaninha_resumo({'cards': []}) == {'cards': []}
    assert _desaninha_resumo({'resumo': None, 'cards': []})['resumo'] is None
    assert _desaninha_resumo({'resumo': '', 'cards': []})['resumo'] == ''


def test_secao_que_veio_como_texto_vira_lista_e_nao_derruba_a_tela():
    """Achado auditando producao: o plano do aluno 22 tinha `nao_focar_agora` como STRING com
    JSON dentro. A tela testa `.length > 0` (numa string, conta caracteres, entao passa) e
    depois chama `.map` (que string nao tem): a tela de plano DAQUELE aluno quebrava."""
    from leaklab.llm_explainer import _normaliza_secoes_do_plano
    como_texto = '[{"item": "VPIP", "motivo": "amostra pequena"}]'
    p = _normaliza_secoes_do_plano({'nao_focar_agora': como_texto, 'observar_mais_dados': [], 'cards': []})
    assert isinstance(p['nao_focar_agora'], list) and p['nao_focar_agora'][0]['item'] == 'VPIP', p
    # o que nao parseia sai do plano: secao ausente e melhor que secao que derruba a tela
    p2 = _normaliza_secoes_do_plano({'nao_focar_agora': 'texto solto que nao e json', 'cards': []})
    assert p2['nao_focar_agora'] == [], p2
    # lista continua lista, e None nao vira []
    p3 = _normaliza_secoes_do_plano({'nao_focar_agora': [{'item': 'x'}], 'observar_mais_dados': None, 'cards': []})
    assert p3['nao_focar_agora'] == [{'item': 'x'}] and p3['observar_mais_dados'] is None


def test_o_plano_respeita_um_intervalo_minimo_entre_geracoes():
    """Dono, 09/09: "1x por mes ou algo assim, ao inves de mudar a todo momento que um indicador
    altere... pra pessoas com muito volume devemos estar consumindo muitos tokens".

    O drift decide SE o plano ficou velho; o intervalo decide QUANDO vale pagar a conta de LLM.
    Plano sem data (os antigos) segue a regra de antes: so o drift."""
    import datetime as dt
    from leaklab.llm_explainer import _plano_novo_demais, STUDY_PLAN_INTERVALO_DIAS
    agora = dt.datetime.utcnow()
    ontem = (agora - dt.timedelta(days=1)).isoformat(timespec='seconds')
    velho = (agora - dt.timedelta(days=STUDY_PLAN_INTERVALO_DIAS + 1)).isoformat(timespec='seconds')
    assert _plano_novo_demais({'_em': ontem}) is True, 'plano de ontem nao regenera so porque driftou'
    assert _plano_novo_demais({'_em': velho}) is False, 'passado o intervalo, o drift volta a mandar'
    assert _plano_novo_demais({}) is False, 'plano antigo (sem data) segue so o drift'
    assert _plano_novo_demais({'_em': 'data podre'}) is False, 'data ilegivel nao pode travar a regeracao'


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
