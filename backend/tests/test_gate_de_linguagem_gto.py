# -*- coding: utf-8 -*-
"""Só quem tem equilíbrio COM custo pode falar a linguagem de GTO — no texto e na tela.

── O buraco que este teste fecha (25/08) ──────────────────────────────────────────────────

A procedência foi entregue e um validador apontou o óbvio: quem de fato escreve "Range GTO" e
"Ação GTO recomendada" na tela do jogador é o `llm_explainer`, e ele **não consultava o gate**.
As 189 acusações sem custo que motivaram todo o trabalho saíam por ali.

Medido no acervo: **14,8% das decisões são heurístico puro** e **38% das acusações em que a
carta reprova a jogada saem sem um bb de custo**. Todas falando como equilíbrio.

── Por que testar o PROMPT, e não a saída do modelo ───────────────────────────────────────

A saída do LLM não é determinística e testá-la seria testar o modelo, não o produto. O que o
produto controla é o que ele PEDE: se o prompt carrega a proibição, a instrução existe; se não
carrega, nenhuma revisão de texto adianta. O teste exercita `_build_payload` de verdade e lê o
prompt gerado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BASE = {
    'hand_id': 'T1', 'street': 'flop', 'player_action': 'bet', 'hero_cards': 'AhKh',
    'spot': {'position': 'BTN', 'board': ['2c', '7d', '9s'], 'facingSize': 0},
    'context': {'mRatio': 12, 'heroStackBb': 30},
    'math': {'estimatedHandEquity': 0.4},
    'hand_profile': {'handClass': 'overcards'},
    'range_evaluation': {'rangeZone': 'marginal'},
    'evaluation': {'label': 'small_mistake', 'scoreBreakdown': {}},
    'thresholds': {},
}


def _prompt(extra):
    from leaklab.llm_explainer import _build_payload
    d = dict(_BASE)
    d.update(extra)
    return _build_payload([d])['messages'][0]['content']


def test_o_prompt_PROIBE_a_linguagem_de_gto_sem_equilibrio():
    """Decisão de procedência `motor`: o texto tem que sair como leitura do motor."""
    txt = _prompt({'verdict_source': 'motor', 'verdict_has_cost': False})
    assert 'PROCEDENCIA DO VEREDITO' in txt, 'o bloco de procedência sumiu do prompt'
    assert 'PROIBIDO' in txt, (
        'decisão sem equilíbrio não recebe a proibição: o modelo volta a escrever "Range GTO" '
        'sobre heurística de equity e pot odds')
    assert 'LEITURA DO MOTOR' in txt, 'a proibição não diz o que escrever no lugar'
    print('OK  test_o_prompt_PROIBE_a_linguagem_de_gto_sem_equilibrio')


def test_o_prompt_LIBERA_quando_ha_equilibrio_com_custo():
    """Contraprova — sem ela, proibir sempre passaria no teste acima e calaria o produto."""
    txt = _prompt({'verdict_source': 'solver', 'verdict_has_cost': True})
    assert 'PERMISSAO' in txt, 'nó do solver com custo medido deixou de poder falar como GTO'
    assert 'PROIBIDO' not in txt, 'a proibição vazou para uma decisão que TEM equilíbrio e custo'
    print('OK  test_o_prompt_LIBERA_quando_ha_equilibrio_com_custo')


def test_equilibrio_SEM_custo_tambem_e_proibido():
    """A carta diz o que o equilíbrio joga; sem EV ela não diz quanto custou desviar — e é o
    "quanto custou" que sustenta a palavra leak. Foi este o caso das 189 acusações."""
    txt = _prompt({'verdict_source': 'carta', 'verdict_has_cost': False})
    assert 'PROIBIDO' in txt, (
        'equilíbrio SEM custo medido voltou a poder acusar com a linguagem de GTO')
    print('OK  test_equilibrio_SEM_custo_tambem_e_proibido')


def test_a_regra_esta_no_system_prompt_e_tem_precedencia():
    """A instrução por decisão só vale se a regra geral existir e for declarada como superior às
    outras — o mesmo prompt manda escrever a seção "Range GTO" logo acima."""
    from leaklab.llm_explainer import _build_payload
    sistema = _build_payload([dict(_BASE)])['system']
    assert 'PROCEDÊNCIA' in sistema or 'PROCEDENCIA' in sistema, (
        'a regra de procedência sumiu do system prompt')
    assert 'acima de todas as outras' in sistema, (
        'a regra perdeu a precedência: o template manda escrever "Range GTO" e sem precedência '
        'declarada as duas instruções competem')
    print('OK  test_a_regra_esta_no_system_prompt_e_tem_precedencia')


def test_a_tela_usa_o_GATE_do_backend_e_nao_deriva_sozinha():
    """A cascata de etiqueta de fonte do card deriva de campos locais — uma segunda porta para o
    mesmo fato. Quando o backend diz que não há equilíbrio, ele manda."""
    caminho = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src',
                           'components', 'replayer', 'SidePanels.tsx')
    assert os.path.exists(caminho), 'SidePanels.tsx sumiu — o teste perdeu o alvo'
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    # A CASCATA em si (do `const _src:` até o `;` que a fecha), sem comentários. A primeira
    # versão olhava uma janela ao redor e aceitava a DECLARAÇÃO de `_semEquilibrio` — a mutação
    # que removia o gate da cascata, deixando a variável declarada e sem uso, passou verde.
    i = fonte.index('const _src:')
    # A busca começa DEPOIS do `=` da atribuição: a anotação de tipo
    # `{ name: string; tip: string }` tem um `;` dentro dela, e cortar nele devolvia só o
    # cabeçalho — o teste falhava até no estado bom.
    eq = fonte.index('=', fonte.index('tip: string }', i))
    fim = fonte.index(';', eq)
    cascata = fonte[eq:fim]
    cascata = chr(10).join(l.split('//')[0] for l in cascata.split(chr(10)))
    assert '_semEquilibrio' in cascata, (
        'o gate de procedência saiu da cascata que decide a etiqueta: heurístico volta a '
        'aparecer rotulado como Solver')
    # e tem que ser o PRIMEIRO ramo, senão outro o encobre
    j = cascata.index('_semEquilibrio')
    k = cascata.index('multiway_advice', j)
    assert j < k, 'o gate de procedência ficou depois de outros ramos e pode ser encoberto'
    # a declaração precisa vir do campo do backend, não de uma heurística local
    decl = fonte[max(0, i - 400):i]
    assert 'step.pode_falar_como_gto' in decl, (
        '`_semEquilibrio` deixou de vir do gate do backend')
    print('OK  test_a_tela_usa_o_GATE_do_backend_e_nao_deriva_sozinha')


def test_o_texto_da_fonte_esta_traduzido_nos_tres_locales():
    """Chave crua na tela é ruim sempre, e pior aqui: esta etiqueta aparece justamente quando o
    produto está admitindo que não tem equilíbrio."""
    import json
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'i18n', 'locales')
    for idioma in ('pt-BR', 'en', 'es'):
        with open(os.path.join(base, idioma, 'replayer.json'), encoding='utf-8') as fh:
            dados = json.load(fh)
        card = dados.get('card') or {}
        assert card.get('srcMotor'), 'card.srcMotor ausente em %s' % idioma
        tip = card.get('tipSemEquilibrio') or ''
        assert len(tip) > 60, (
            '%s: o tooltip precisa EXPLICAR que não é equilíbrio, não só rotular' % idioma)
    print('OK  test_o_texto_da_fonte_esta_traduzido_nos_tres_locales')


def _gate(**linha):
    """Chama o helper REAL do app com uma linha gravada."""
    import importlib
    app = importlib.import_module('api.app')
    return app._pode_falar_como_gto_da_linha(linha)


def test_o_gate_da_linha_recusa_multiway_e_heuristico():
    """Comportamento, não fiação. As três recusas que importam, cada uma com o seu controle."""
    solver_hu = dict(street='turn', gto_label='gto_critical', ev_loss_bb=1.2,
                     ev_loss_source='solver_hand', n_active_opponents=1)
    assert _gate(**solver_hu) is True, 'nó do solver heads-up com custo deixou de poder falar GTO'

    # multiway: o produto se recusa a graduar, então não pode acusar com autoridade de gabarito
    mw = dict(solver_hu, n_active_opponents=3)
    assert _gate(**mw) is False, 'multiway voltou a liberar a linguagem de GTO'

    # equilíbrio sem custo medido
    sem_custo = dict(solver_hu, ev_loss_bb=None, ev_loss_source=None)
    assert _gate(**sem_custo) is False, 'equilíbrio sem custo voltou a poder acusar'

    # heurístico puro
    motor = dict(street='flop', gto_label=None, ev_loss_bb=None, ev_loss_source=None,
                 n_active_opponents=1)
    assert _gate(**motor) is False, 'heurístico voltou a poder dizer leak'

    # multiway no PREFLOP não é o caso: o solver HU-only é problema de postflop
    pre = dict(street='preflop', gto_label='gto_critical', ev_loss_bb=0.9,
               ev_loss_source='gw_har', n_active_opponents=4)
    assert _gate(**pre) is True, (
        'o gate multiway vazou para o preflop, onde a carta de range vale com mesa cheia')
    print('OK  test_o_gate_da_linha_recusa_multiway_e_heuristico')


def test_as_TRES_portas_servem_o_gate_pela_mesma_funcao():
    """Regra 5. O `/replay` tinha a expressão inline e a lista do torneio não tinha nada — ela
    servia o veredito sem dizer se ele tem direito à linguagem de GTO."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    codigo = chr(10).join(l.split('#')[0] for l in fonte.split(chr(10)))
    usos = codigo.count('_pode_falar_como_gto_da_linha(')
    assert usos >= 3, (
        'o helper do gate é usado em %d lugares (definição + chamadas): alguma porta voltou a '
        'servir veredito sem o gate, ou a decidir sozinha' % usos)
    # e ninguém pode ter voltado a montar a regra inline
    assert 'False if _mw_spot else _verdict_mod.pode_falar_como_gto' not in codigo, (
        'a regra do gate voltou a ser montada inline — segunda porta para o mesmo fato')
    print('OK  test_as_TRES_portas_servem_o_gate_pela_mesma_funcao (%d usos)' % usos)


def test_o_texto_tambem_recusa_multiway():
    """O card recusava multiway e o TEXTO não: o mesmo spot recebia "≈ Aproximação" no card e
    permissão para escrever "leak" na narrativa. Gate fechado numa porta só é gate aberto."""
    hu = _prompt({'verdict_source': 'solver', 'verdict_has_cost': True,
                  'n_active_opponents': 1})
    assert 'PERMISSAO' in hu, 'heads-up com solver e custo deixou de poder falar como GTO'

    mw = _prompt({'verdict_source': 'solver', 'verdict_has_cost': True,
                  'n_active_opponents': 3})
    assert 'PROIBIDO' in mw, (
        'multiway postflop voltou a liberar a linguagem de GTO no texto, enquanto o card se '
        'recusa a graduar o mesmo spot')

    # o gate multiway é de POSTFLOP: no preflop a carta de range vale com mesa cheia
    pre = _prompt({'street': 'preflop', 'verdict_source': 'carta', 'verdict_has_cost': True,
                   'n_active_opponents': 4})
    assert 'PROIBIDO' not in pre, 'o gate multiway vazou para o preflop'
    print('OK  test_o_texto_tambem_recusa_multiway')


def test_a_ETIQUETA_QUE_CHEGA_AO_CARD_usa_o_gate():
    """A cascata `_src` alimenta `verdict.source`, que NÃO é renderizado. Quem chega ao card é
    `sourceVariant` -> `SOURCE_LABEL`. O primeiro conserto foi na cascata errada e a etiqueta
    continuava dizendo "Solver" em decisão sem custo medido — gate desligado por falta de
    consumidor, a terceira vez que este padrão apareceu nesta série."""
    caminho = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src',
                           'components', 'replayer', 'SidePanels.tsx')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    i = fonte.index('const sourceVariant:')
    fim = fonte.index(';', fonte.index('"engine";', i) if '"engine";' in fonte[i:i + 900]
                      else i + 400)
    cascata = chr(10).join(l.split('//')[0] for l in fonte[i:fim].split(chr(10)))
    assert 'semEquilibrioAqui' in cascata or 'pode_falar_como_gto' in cascata, (
        'a cascata que CHEGA AO CARD não consulta o gate: heurístico volta a ser exibido como '
        '"Solver", com o visual de autoridade máxima')
    # e como PRIMEIRO ramo
    j = cascata.index('semEquilibrioAqui') if 'semEquilibrioAqui' in cascata else 0
    k = cascata.index('multiway_advice', j)
    assert j < k, 'o gate ficou depois de outros ramos e pode ser encoberto'

    # o variant precisa existir com estilo PRÓPRIO — herdar o de `gto` seria manter a autoridade
    card = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src',
                        'components', 'replayer', 'DecisionCard.tsx')
    with open(card, encoding='utf-8') as fh:
        fc = fh.read()
    assert '"motor"' in fc, 'o variant `motor` sumiu do tipo DecisionSourceVariant'
    assert 'motor:' in fc, 'o variant `motor` não tem estilo próprio no SOURCE_VARIANT_CLS'
    print('OK  test_a_ETIQUETA_QUE_CHEGA_AO_CARD_usa_o_gate')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
