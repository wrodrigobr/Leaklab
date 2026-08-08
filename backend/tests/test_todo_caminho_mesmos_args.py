# -*- coding: utf-8 -*-
"""Todo caminho que chama a porta unica preflop passa os argumentos que decidem O NO.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Em 07/08 o `/replay` foi flagrado chamando `analyze_preflop` **sem `facing_to_bb` e sem
`facing_allin`**. Esses dois separam a carta de 3-bet PEQUENO da carta de JAM: sao nos
diferentes. Numa mao heads-up de 15bb efetivos, o jam do vilao era roteado para o no de 3-bet
pequeno — veredito da carta errada, que e exatamente o defeito que o caminho HU existe para matar.

O caminho principal (`/analyze`) ja passava os dois. So o replay ficou para tras, e **nada
acusava**: o teste de paridade que existia comparava `sync x motor` e o replay nao estava na conta.

── Por que a varredura e sobre o CODIGO-FONTE ─────────────────────────────────────────────────

Nao ha como exercitar os tres caminhos num teste de unidade sem montar torneio, banco e request.
O que se pode garantir barato e que **nenhuma chamada esqueca um argumento** — e e disso que o
defeito era feito. Se a assinatura mudar, o teste quebra e alguem le este arquivo.

`n_players` esta na lista pelo mesmo motivo: sem ele, `int(None or 0) == 2` e falso e uma mesa de
DOIS jogadores e gradeada pela carta de mesa cheia.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_APP = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')

# Argumentos que mudam QUAL CARTA e consultada. Faltar qualquer um nao devolve "nao sei":
# devolve veredito de outro no.
_OBRIGATORIOS = ('n_players', 'facing_allin')


def _chamadas_da_porta_unica():
    """Cada chamada de analise, do parentese ate o fechamento equilibrado."""
    src = io.open(_APP, encoding='utf-8').read()
    achadas = []
    for m in re.finditer(r'\b(?:_analyze_preflop|analyze_preflop|_pfs)\s*\(', src):
        i = m.end() - 1
        prof, j = 0, i
        while j < len(src):
            if src[j] == '(':
                prof += 1
            elif src[j] == ')':
                prof -= 1
                if prof == 0:
                    break
            j += 1
        corpo = src[i:j]
        if 'hero_hand_type' not in corpo:
            continue                       # import, alias ou outra funcao de nome parecido
        achadas.append((src[:m.start()].count('\n') + 1, corpo))
    return achadas


def test_a_varredura_encontra_os_caminhos():
    """Controle: se a busca parar de achar chamadas, o teste abaixo passa por vacuidade."""
    achadas = _chamadas_da_porta_unica()
    assert len(achadas) >= 3, f'a varredura achou so {len(achadas)} chamadas — o padrao mudou'


def test_nenhuma_chamada_esquece_o_que_decide_o_no():
    faltando = []
    for linha, corpo in _chamadas_da_porta_unica():
        sem = [a for a in _OBRIGATORIOS if a not in corpo]
        if sem:
            faltando.append(f'app.py:{linha} sem {sem}')
    assert not faltando, 'chamadas da porta unica incompletas: ' + '; '.join(faltando)


def test_o_replay_passa_o_tamanho_em_BB_e_nao_em_FICHAS():
    """`facingSize` vem em FICHAS (212.780 na mao que expos isto) e `facingToBb` em bb. Passar o
    primeiro como tamanho e a unidade errada — o bug mais recorrente deste projeto.

    (Honestidade: no provider atual `facing_size` so e usado como `> 0`, entao a troca nao muda
    veredito hoje. O teste existe para que continue certo quando alguem passar a usar o valor.)
    """
    for linha, corpo in _chamadas_da_porta_unica():
        if 'facing_size' not in corpo:
            continue
        m = re.search(r'facing_size\s*=\s*([^,\n]+)', corpo)
        assert m, (linha, corpo[:120])
        expr = m.group(1)
        assert 'facingSize' not in expr, (
            f"app.py:{linha} passa `facingSize` (fichas) como facing_size; use `facingToBb`")


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
