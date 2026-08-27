# -*- coding: utf-8 -*-
"""A contradição "major leak" x "não é erro" é suprimida no FRONT, e a regra tem que estar lá.

── Por que este guarda existe, e por que mora aqui ────────────────────────────────────────

O payload carrega os dois fatos legitimamente: `actionQuality` pode dizer `major_leak` enquanto
o veredito diz que não é erro, porque são medidas de coisas diferentes. Quem impede a
contradição de chegar à tela é `cardLogic.mostraQualidadeEstatica`. Medir o payload acusaria 20
casos que o aluno nunca vê — foi o que a 1ª versão da checagem fez.

Ela nasceu como porta do `portao_de_aceite.py` e mudou de casa em 27/08: rodando dentro do
container do backend, `frontend/` não existe, a porta devolvia denominador 0 e o portão inteiro
saía INCONCLUSIVO em **todo** deploy. Alarme que bloqueia sempre ensina a ignorar bloqueio.

Aqui o repositório inteiro está na mão, então dá para conferir o que importa de verdade: que a
regra existe E que os dois consumidores continuam chamando (regra 5 do CLAUDE.md — a que já me
pegou com o gate vivo no motor e morto no `/replay`).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_FRONT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       '..', '..', 'frontend', 'src'))


def _ler(*rel):
    caminho = os.path.join(_FRONT, *rel)
    assert os.path.exists(caminho), 'arquivo sumiu do front: %s' % caminho
    with open(caminho, encoding='utf-8') as fh:
        return fh.read()


def test_a_regra_existe_em_cardLogic():
    fonte = _ler('lib', 'cardLogic.ts')
    assert 'mostraQualidadeEstatica' in fonte, (
        'a função que suprime a contradição sumiu: o card volta a exibir "major leak" ao lado '
        'de "não é erro"')
    assert 'isError === false' in fonte, (
        'a condição da supressão mudou — ela precisa olhar o veredito, não só a qualidade')
    print('OK  test_a_regra_existe_em_cardLogic')


def test_os_DOIS_consumidores_chamam_a_regra():
    """Regra que existe e não é chamada é o defeito mais recorrente deste projeto. São dois
    painéis, e já aconteceu de um receber o conserto e o outro não."""
    faltando = [arq for arq in ('RangePanel.tsx', 'SidePanels.tsx')
                if 'mostraQualidadeEstatica' not in _ler('components', 'replayer', arq)]
    assert not faltando, (
        'painel(éis) do card pararam de chamar a supressão: %s' % ', '.join(faltando))
    print('OK  test_os_DOIS_consumidores_chamam_a_regra')


def test_o_teste_unitario_do_front_continua_existindo():
    """Este guarda é de presença; os CASOS da regra são cobertos em `cardLogic.test.ts`, que foi
    quebrado de propósito quando a regra nasceu. Se o arquivo sumir, esta cobertura vira fumaça."""
    fonte = _ler('lib', 'cardLogic.test.ts')
    assert 'mostraQualidadeEstatica' in fonte, (
        'o teste unitário da regra sumiu do front — este arquivo só confere presença, não casos')
    print('OK  test_o_teste_unitario_do_front_continua_existindo')


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
