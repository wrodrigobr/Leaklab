"""
Testes do trilho LENTO (leaklab/validation.py) — provar no jogo real que o leak foi corrigido.

Funções puras. O que estes testes travam não é a fórmula: é a HONESTIDADE do veredito. Um
produto que diz "você melhorou" com 6 mãos e um baseline enviesado é pior que um que não diz
nada, porque o jogador para de treinar algo que continua custando fichas.
"""
import sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.validation import (
    wilson, shrink, newcombe_diff, validate_leak, should_reopen,
    V_SEM_AMOSTRA, V_MELHOROU, V_SEM_MUDANCA, V_PIOROU,
    VALIDATION_MIN_N, BASELINE_MIN_N, SHRINK_PSEUDO_N,
)


# ── Wilson ────────────────────────────────────────────────────────────────────

def test_wilson_nunca_sai_do_intervalo_valido():
    """A aproximação normal devolve limites negativos com p perto de 0 — o regime EXATO deste
    produto (poucas mãos por família). Wilson não."""
    for k, n in [(0, 5), (5, 5), (1, 3), (0, 30), (30, 30)]:
        lo, c, hi = wilson(k, n)
        assert 0.0 <= lo <= c <= hi <= 1.0, (k, n, lo, c, hi)
    print("OK  test_wilson_nunca_sai_do_intervalo_valido")


def test_wilson_estreita_com_mais_amostra():
    largo = wilson(3, 10)
    estreito = wilson(30, 100)
    assert (largo[2] - largo[0]) > (estreito[2] - estreito[0])
    print("OK  test_wilson_estreita_com_mais_amostra")


def test_wilson_sem_amostra_nao_afirma_nada():
    lo, _, hi = wilson(0, 0)
    assert lo == 0.0 and hi == 1.0
    print("OK  test_wilson_sem_amostra_nao_afirma_nada")


# ── Shrinkage (winner's curse) ────────────────────────────────────────────────

def test_shrinkage_puxa_o_baseline_para_o_global():
    """O leak entrou no plano por ser o PIOR de uma lista: parte do 'antes' ruim é seleção, não
    hábito. Sem puxar pro global, o jogador 'melhora' sozinho por regressão à média."""
    k, n = shrink(8, 10, p_global=0.30)      # 80% de erro observado, 30% global
    taxa = k / n
    assert 0.30 < taxa < 0.80, taxa
    assert abs(taxa - (8 + SHRINK_PSEUDO_N * 0.30) / 30) < 1e-9
    print(f"OK  test_shrinkage_puxa_o_baseline_para_o_global (80% → {taxa*100:.1f}%)")


def test_shrinkage_pesa_menos_com_amostra_grande():
    """Com 200 mãos o dado fala mais alto que o prior — senão o shrinkage viraria censura."""
    pequena = shrink(8, 10, 0.30);  pequena = pequena[0] / pequena[1]
    grande  = shrink(160, 200, 0.30); grande = grande[0] / grande[1]
    assert abs(grande - 0.80) < abs(pequena - 0.80)
    print("OK  test_shrinkage_pesa_menos_com_amostra_grande")


# ── Diferença ─────────────────────────────────────────────────────────────────

def test_diferenca_cruza_zero_com_amostra_pequena():
    """60% × 40% em 10 mãos cada NÃO é diferença: é ruído. O IC tem que cruzar o zero."""
    lo, hi = newcombe_diff(6, 10, 4, 10)
    assert lo < 0 < hi, (lo, hi)
    print("OK  test_diferenca_cruza_zero_com_amostra_pequena")


def test_diferenca_grande_com_amostra_grande_resiste():
    lo, hi = newcombe_diff(70, 100, 20, 100)
    assert lo > 0, (lo, hi)
    print("OK  test_diferenca_grande_com_amostra_grande_resiste")


# ── Veredito ──────────────────────────────────────────────────────────────────

def test_sem_amostra_no_depois_nao_crava_nada():
    v = validate_leak(erros_antes=10, n_antes=20,
                      erros_depois=1, n_depois=VALIDATION_MIN_N - 1, taxa_global=0.3)
    assert v['veredito'] == V_SEM_AMOSTRA and v['motivo'] == 'depois_curto'
    assert v['faltam'] == 1
    print("OK  test_sem_amostra_no_depois_nao_crava_nada")


def test_sem_baseline_nao_ha_do_que_partir():
    v = validate_leak(5, BASELINE_MIN_N - 1, 2, 40, 0.3)
    assert v['veredito'] == V_SEM_AMOSTRA and v['motivo'] == 'baseline_curto'
    print("OK  test_sem_baseline_nao_ha_do_que_partir")


def test_melhora_pequena_nao_vira_selo():
    """O caso que mais importa: 55% → 45% em ~20 mãos de cada lado parece melhora e não é.
    Selar isso ensinaria o jogador a parar de treinar um leak que continua lá."""
    v = validate_leak(erros_antes=11, n_antes=20, erros_depois=9, n_depois=20, taxa_global=0.30)
    assert v['veredito'] == V_SEM_MUDANCA, v
    print("OK  test_melhora_pequena_nao_vira_selo")


def test_melhora_grande_e_sustentada_sela():
    v = validate_leak(erros_antes=45, n_antes=60, erros_depois=8, n_depois=60, taxa_global=0.30)
    assert v['veredito'] == V_MELHOROU, v
    assert v['ic_diferenca'][0] > 0
    print("OK  test_melhora_grande_e_sustentada_sela")


def test_shrinkage_vira_o_veredito_no_regime_do_winners_curse():
    """O caso que justifica o shrinkage existir: baseline extremo e CURTO (8 erros em 9 mãos)
    contra um depois medíocre (6 em 15). Sem correção o IC da diferença começa em +8,4% e o
    jogador ganharia o selo por regressão à média. Com o baseline puxado pro global, o
    intervalo cruza o zero e a plataforma admite que não sabe."""
    sem_correcao = newcombe_diff(8, 9, 6, 15)
    v = validate_leak(erros_antes=8, n_antes=9, erros_depois=6, n_depois=15, taxa_global=0.30)
    assert sem_correcao[0] > 0, "sem shrinkage selaria — é o viés que queremos matar"
    assert v['veredito'] == V_SEM_MUDANCA, v
    print("OK  test_shrinkage_vira_o_veredito_no_regime_do_winners_curse")


def test_shrinkage_sempre_torna_o_selo_mais_dificil():
    """Propriedade geral, não um caso escolhido a dedo: para qualquer cenário de melhora, o
    limite inferior da diferença COM shrinkage é menor que sem. Se algum dia isso inverter,
    o shrinkage virou enfeite."""
    casos = [(9, 10, 4, 20), (8, 9, 6, 15), (45, 60, 8, 60), (12, 25, 8, 25)]
    for ka, na, kd, nd in casos:
        k_aj, n_aj = shrink(ka, na, 0.30)
        assert newcombe_diff(k_aj, n_aj, kd, nd)[0] < newcombe_diff(ka, na, kd, nd)[0], (ka, na)
    print("OK  test_shrinkage_sempre_torna_o_selo_mais_dificil")


def test_melhora_grande_ainda_sela_apesar_do_shrinkage():
    """O contrapeso: shrinkage não pode tornar o selo inalcançável, senão ninguém nunca prova
    nada e o terceiro estado vira enfeite. 9/10 → 4/20 continua selando (no limite: IC começa
    em +2,6%), porque a queda é grande mesmo contra o baseline ajustado."""
    v = validate_leak(9, 10, 4, 20, 0.30)
    assert v['veredito'] == V_MELHOROU, v
    assert 0 < v['ic_diferenca'][0] < 10, v['ic_diferenca']
    print("OK  test_melhora_grande_ainda_sela_apesar_do_shrinkage")


def test_regressao_real_e_detectada():
    v = validate_leak(erros_antes=12, n_antes=60, erros_depois=40, n_depois=60, taxa_global=0.30)
    assert v['veredito'] == V_PIOROU, v
    print("OK  test_regressao_real_e_detectada")


def test_veredito_mostra_os_numeros_que_o_sustentam():
    """O jogador tem direito de ver por que a plataforma disse o que disse."""
    v = validate_leak(45, 60, 8, 60, 0.30)
    for campo in ('n_antes', 'n_depois', 'taxa_antes', 'taxa_depois', 'taxa_global',
                  'taxa_antes_ajustada', 'ic_diferenca', 'label'):
        assert campo in v, campo
    print("OK  test_veredito_mostra_os_numeros_que_o_sustentam")


# ── Reabertura ────────────────────────────────────────────────────────────────

def test_so_regressao_comprovada_reabre():
    """`sem_mudanca` NÃO reabre: ausência de prova de melhora não é prova de piora. Reabrir por
    isso puniria quem só não jogou o bastante, e o jogador abandonaria o protocolo."""
    assert should_reopen({'veredito': V_PIOROU})
    assert not should_reopen({'veredito': V_SEM_MUDANCA})
    assert not should_reopen({'veredito': V_SEM_AMOSTRA})
    assert not should_reopen({'veredito': V_MELHOROU})
    assert not should_reopen(None)
    print("OK  test_so_regressao_comprovada_reabre")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
    raise SystemExit(1 if failed else 0)
