# -*- coding: utf-8 -*-
"""O guarda da propria suite: teste escrito e nunca rodado nao e cobertura.

── O que originou (05/09) ────────────────────────────────────────────────────────────────

Ao registrar dois arquivos novos, descobri que o `run_all_tests.py` tem lista FIXA e que
**30 dos 269 arquivos de teste nao estavam em lista nenhuma**. Nunca rodavam. A suite
anunciava "2719 ok, zero regressoes" com 11% dos arquivos de fora, e eu mesmo tinha acabado
de escrever 9 testes de rebaixamento de plano que nunca entraram na contagem.

Medidos um a um: **24 estavam VERDES** — cobertura pronta, parada ha meses. Quatro tinham
falhas (11 testes), que e outro problema: guarda vermelho que ninguem ve nao protege nada.

Isto e o padrao que a memoria ja registrava em [[reference_suite_filtrada_nao_basta]]: "o
pior caso foi um guarda que JA EXISTIA, em outra suite". A diferenca aqui e que nao havia
outra suite — havia o vazio.

── O contrato ───────────────────────────────────────────────────────────────────────────

Todo `tests/test_*.py` tem de estar numa suite de `SUITES` **ou** declarado em
`FORA_DA_SUITE` com motivo. Sem terceira opcao. Esquecer passa a custar um teste vermelho na
hora, em vez de meses de silencio.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_DIR = os.path.dirname(os.path.abspath(__file__))


def _carrega_runner():
    """Le SUITES e FORA_DA_SUITE do runner sem importa-lo (importar dispara os testes)."""
    texto = io.open(os.path.join(_DIR, 'run_all_tests.py'), encoding='utf-8').read()
    ns: dict = {}
    # Sao dois literais no topo do arquivo; exec so deles evita rodar o runner inteiro.
    for nome in ('SUITES', 'FORA_DA_SUITE'):
        m = re.search(r'^%s\s*=\s*(\{.*?^\})' % nome, texto, re.M | re.S)
        assert m, 'nao achei %s em run_all_tests.py' % nome
        ns[nome] = eval(m.group(1))                                  # noqa: S307
    return ns['SUITES'], ns['FORA_DA_SUITE']


def _arquivos_de_teste():
    return sorted(f for f in os.listdir(_DIR)
                  if f.startswith('test_') and f.endswith('.py'))


def test_todo_arquivo_de_teste_esta_declarado():
    """O guarda principal. Falha nomeando os esquecidos, para o conserto ser obvio."""
    suites, fora = _carrega_runner()
    registrados = {f for lista in suites.values() for f in lista}
    esquecidos = [f for f in _arquivos_de_teste()
                  if f not in registrados and f not in fora]
    assert not esquecidos, (
        '%d arquivo(s) de teste nao rodam em lugar nenhum: %s. Registre em SUITES ou '
        'declare em FORA_DA_SUITE com o motivo.' % (len(esquecidos), ', '.join(esquecidos)))


def test_o_guarda_ACHA_um_arquivo_esquecido():
    """Contraprova (regra 1): sem ela, o teste acima passaria com a varredura quebrada."""
    suites, fora = _carrega_runner()
    registrados = {f for lista in suites.values() for f in lista}
    forjado = 'test_arquivo_que_ninguem_registrou.py'
    assert forjado not in registrados and forjado not in fora
    esquecidos = [f for f in _arquivos_de_teste() + [forjado]
                  if f not in registrados and f not in fora]
    assert forjado in esquecidos, 'a varredura nao acha um arquivo fora das duas listas'


def test_declaracao_de_fora_carrega_motivo():
    """`FORA_DA_SUITE` sem motivo vira lista de exclusao silenciosa, que e o problema de novo."""
    _, fora = _carrega_runner()
    sem_motivo = [f for f, m in fora.items() if not (m or '').strip()]
    assert not sem_motivo, 'declarado fora da suite sem motivo: %s' % ', '.join(sem_motivo)


def test_nada_declarado_fora_que_nao_exista():
    """Arquivo apagado que fica na lista esconde o proximo esquecido atras de ruido."""
    _, fora = _carrega_runner()
    existentes = set(_arquivos_de_teste())
    fantasmas = [f for f in fora if f not in existentes]
    assert not fantasmas, 'declarado fora da suite mas nao existe: %s' % ', '.join(fantasmas)


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
