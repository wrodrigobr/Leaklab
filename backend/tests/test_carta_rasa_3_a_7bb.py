# -*- coding: utf-8 -*-
"""A carta rasa (3-7bb) existe, é consultada, e NÃO mexeu em quem já funcionava.

── O caso que originou (26/08) ────────────────────────────────────────────────────────────

`_stack_bucket` saturava na ponta rasa: o balde `10bb` cobria `[0, 12)`, e o caminho principal do
motor lê esse balde SEM passar por `_balde_da_carta`. Medido no acervo: **117 das 128 decisões de
RFI entre 2,5 e 7,5bb eram julgadas pela carta de 10bb** — 2 a 4 vezes mais funda que o stack
real. É a mesma saturação que já produziu duas acusações falsas medidas (3,9bb e 5,2bb) no
caminho da range de jam, e a razão de `_profundidade_compativel` existir.

A faixa 3-7bb de uma carta externa (conferida em 94,0% contra a nossa nas células sobrepostas)
foi importada e os baldes entraram no roteamento.

── Por que o teste tem DUAS metades ───────────────────────────────────────────────────────

A primeira metade prova que a faixa nova funciona. A segunda prova que as duas pontas vizinhas
**não se mexeram** — porque o risco real de mexer numa lista de baldes não é a faixa nova falhar,
é ela roubar stacks das faixas vizinhas em silêncio (regra 7 do CLAUDE.md: o conserto não pode
causar dano que o bug não causava).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_RASOS = ('3bb', '4bb', '5bb', '6bb', '7bb')
_POSICOES = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')


def test_a_faixa_rasa_tem_carta():
    from leaklab.preflop_gto_ranges import _load
    ranges = _load()['ranges']
    for b in _RASOS:
        assert b in ranges, 'balde %s sumiu da base de ranges' % b
        rfi = (ranges[b] or {}).get('RFI') or {}
        faltam = [p for p in _POSICOES if p not in rfi]
        assert not faltam, 'balde %s sem as posições %s' % (b, faltam)
    print('OK  test_a_faixa_rasa_tem_carta')


def test_o_stack_raso_LE_A_CARTA_da_propria_profundidade():
    """`balde_rfi` é a porta. Ancora na CONDIÇÃO (qual balde é escolhido), não no efeito, porque
    guarda que olha só o valor final passa verde com o `if` trocado por False."""
    from leaklab.preflop_gto_ranges import balde_rfi
    esperado = {2.6: '3bb', 3.4: '3bb', 4.0: '4bb', 5.2: '5bb', 6.4: '6bb', 7.4: '7bb'}
    for stack, balde in esperado.items():
        assert balde_rfi(stack) == balde, (
            '%.1fbb lê a RFI de %s, não de %s — a carta rasa deixou de ser consultada'
            % (stack, balde_rfi(stack), balde))
    for stack in (0.5, 2.0, 2.4, 7.6, 9.0, 11.9):
        assert balde_rfi(stack) == '10bb', (
            '%.1fbb passou a ler a RFI de %s. Fora de [2,5; 7,5) não importamos carta (a de '
            'origem limpa QQ/JJ no SB a 2bb), então tem que continuar onde estava'
            % (stack, balde_rfi(stack)))
    print('OK  test_o_stack_raso_LE_A_CARTA_da_propria_profundidade')


def test_o_roteamento_GERAL_nao_se_mexeu():
    """A metade que protege quem já funcionava, e a razão de `balde_rfi` existir separado.

    A carta rasa cobre **só RFI**. Se ela entrasse em `_DEFAULT_BUCKETS`, `vs_RFI`/`vs_3bet` a 4bb
    apontariam para um balde sem essas seções — e, pior, `_balde_da_carta(3,9)` passaria a ACEITAR
    o balde, deixando dado de 10bb atravessar o guarda escrito para barrá-lo. Foi um teste de
    controle que mostrou isso (`test_carta_do_no_certo.py`), não raciocínio: a primeira tentativa
    colocou os baldes no roteamento geral e ficou vermelha."""
    from leaklab.preflop_gto_ranges import _stack_bucket, _balde_da_carta, _DEFAULT_BUCKETS
    rasos = [b for b, _, _ in _DEFAULT_BUCKETS if b in _RASOS]
    assert not rasos, (
        'a faixa rasa entrou no roteamento GERAL (%s): as seções que ela não cobre passam a '
        'apontar para um balde vazio, e `_balde_da_carta` passa a aceitar o que hoje recusa'
        % rasos)
    for stack in (0.5, 2.6, 3.9, 5.2, 7.4, 7.6, 11.9):
        assert _stack_bucket(stack) == '10bb', (
            '%.1fbb mudou de balde no roteamento geral (%s)' % (stack, _stack_bucket(stack)))
    for stack in (2.6, 3.9, 5.2, 7.4):
        assert _balde_da_carta(stack) is None, (
            '%.1fbb passou a ser aceito por `_balde_da_carta`: as seções fora de RFI voltariam a '
            'ser respondidas por carta de outra profundidade' % stack)
    assert _stack_bucket(13.0) == '14bb', 'o resto da escada de baldes se deslocou'
    assert _stack_bucket(100.0) == '100bb', 'o resto da escada de baldes se deslocou'
    print('OK  test_o_roteamento_GERAL_nao_se_mexeu')


def test_todo_leitor_da_secao_RFI_passa_pela_porta():
    """Regra 5 do CLAUDE.md: a escolha do balde de RFI vive em N lugares, então virou função e
    este guarda varre os N+1. Leitor novo que resolva o balde sozinho volta a saturar em silêncio
    na faixa rasa — que é exatamente como o defeito nasceu.

    Exceção só vale DECLARADA no lugar, com o marcador `balde_rfi nao se aplica:` e o motivo ao
    lado. Lista de exceções morando aqui no teste envelhece calada; declaração no ponto de uso
    aparece para quem mexe naquela linha.
    """
    import re
    raiz = os.path.join(os.path.dirname(__file__), '..')
    alvos = ['leaklab/preflop_gto_ranges.py', 'leaklab/sizing_advisor.py',
             'leaklab/gto_solver.py', 'api/app.py']
    padrao = re.compile(r"""\.get\(['"]RFI['"]|\[['"]RFI['"]\]""")
    achados = []
    for rel in alvos:
        with open(os.path.join(raiz, *rel.split('/')), encoding='utf-8') as fh:
            linhas = fh.read().split(chr(10))
        funcao = ''
        for i, bruta in enumerate(linhas):
            if bruta.startswith('def ') or bruta.startswith('    def '):
                funcao = bruta.strip().split('(')[0][4:]
            linha = bruta.split('#')[0]
            if not padrao.search(linha):
                continue
            if funcao in ('balde_rfi', 'balde_rfi_ou_none'):     # a própria porta
                continue
            viz = chr(10).join(linhas[max(0, i - 10):i + 1])
            # `balde_rfi(` e nao `balde_rfi`: a primeira versao deste guarda aceitava a MENCAO do
            # nome, e o import no topo da funcao ja bastava. Removi a chamada em
            # `sizing_advisor` de proposito e o guarda passou verde -- ancorado no efeito
            # (o nome aparece) em vez da condicao (a funcao e chamada). Ver
            # [[reference_teste_ancora_no_efeito_nao_na_condicao]].
            if ('balde_rfi(' in viz or 'balde_rfi nao se aplica' in viz
                    or '_pko' in viz or '_evs' in viz):
                continue
            achados.append('%s:%d (em %s)' % (rel, i + 1, funcao or '<modulo>'))
    assert not achados, (
        'leitor(es) da seção RFI sem passar por `balde_rfi` nem declarar exceção: %s — na faixa '
        '3-7bb eles voltam a ler a carta de 10bb' % ', '.join(achados))
    print('OK  test_todo_leitor_da_secao_RFI_passa_pela_porta')


def test_a_celula_rasa_cobre_as_169_maos():
    """Célula que cobre menos de 169 mãos tem buraco mudo: a mão que falta vira fold 100% sem
    ninguém dizer que ela não estava na carta."""
    from leaklab.preflop_gto_ranges import _load
    ranges = _load()['ranges']
    for b in _RASOS:
        for pos in _POSICOES:
            cel = ranges[b]['RFI'][pos]
            todas = set()
            for chave in ('raise_hands', 'allin_hands', 'call_hands', 'fold_hands'):
                todas.update(h for h in (cel.get(chave) or '').split(',') if h)
            assert len(todas) == 169, (
                '%s %s cobre %d mãos, não 169' % (b, pos, len(todas)))
    print('OK  test_a_celula_rasa_cobre_as_169_maos')


def test_a_carta_rasa_DECLARA_que_e_de_fonte_externa():
    """Regra 8 do CLAUDE.md ao contrário: comentário no código não sobrevive, mas a procedência
    dentro do DADO viaja com ele. Sem isso, daqui a três meses estes baldes parecem GW."""
    from leaklab.preflop_gto_ranges import _load
    dados = _load()
    for b in _RASOS:
        fonte = (dados['ranges'][b] or {}).get('_fonte')
        assert isinstance(fonte, dict) and fonte.get('origem'), (
            'balde %s perdeu a declaração de procedência — passa a parecer captura do GW' % b)
        assert 'RFI' in (fonte.get('secoes') or ''), (
            'balde %s não declara mais que só tem RFI' % b)
    print('OK  test_a_carta_rasa_DECLARA_que_e_de_fonte_externa')


def test_o_jam_abre_conforme_a_mesa_encurta_e_a_posicao_melhora():
    """Sanidade de poker do dado importado: a range de jam tem que ABRIR quando o stack encurta e
    quando a posição melhora. Uma importação que embaralha posição ou profundidade quebra aqui —
    e é o único guarda que olha o CONTEÚDO, não o formato."""
    from leaklab.preflop_gto_ranges import _load
    ranges = _load()['ranges']
    for b in _RASOS:
        pcts = [ranges[b]['RFI'][p]['open_pct'] for p in ('UTG', 'CO', 'BTN', 'SB')]
        assert pcts == sorted(pcts), (
            '%s: a range não abre da posição pior para a melhor (%s)' % (b, pcts))
    for pos in ('UTG', 'CO', 'BTN'):
        rasos = [ranges[b]['RFI'][pos]['open_pct'] for b in _RASOS]
        assert rasos == sorted(rasos, reverse=True), (
            '%s: a range não abre conforme o stack encurta (3->7bb: %s)' % (pos, rasos))
    print('OK  test_o_jam_abre_conforme_a_mesa_encurta_e_a_posicao_melhora')


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
