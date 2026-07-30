# -*- coding: utf-8 -*-
"""
Espinha de medicao do trilho lento — Protocolo de Progressao, Fase 1.

A spec diz: "se isto nao funcionar, nada do resto importa". E o que autoriza o produto a dizer
"voce melhorou NO JOGO REAL", entao cada guarda aqui existe para impedir uma afirmacao que a
evidencia nao sustenta.

── O que este arquivo trava ───────────────────────────────────────────────────────────────────────

1. **Wilson, e nao a normal.** Com n pequeno a aproximacao normal colapsa para largura ZERO quando
   k=0 ou k=n — afirmaria certeza absoluta a partir de 5 observacoes. Wilson nunca faz isso.

2. **O encolhimento do baseline (winner's curse).** O leak entra no Top-3 porque o numero estava
   extremo; comparar contra aquele extremo credita regressao a media como progresso. Sem
   encolhimento, o Top-3 recompensa variancia POR CONSTRUCAO.

3. **"Melhorou" exige o intervalo INTEIRO abaixo do baseline.** Comparar ponto contra ponto
   declararia melhora em metade dos casos por sorteio.

4. **"Indefinido" nao pode virar "nao melhorou".** Sao coisas diferentes: "ainda estou coletando"
   e "voce nao melhorou". Colapsar as duas e mentir para o aluno em silencio.

5. **O erro e HERDADO do veredito (`verdict.is_error`), nao redefinido aqui.** Uma segunda regua de
   "erro" criaria dois numeros discordando na cara do aluno. E, medido, `label` existe nas 9216
   decisoes de producao contra 5780 com `ev_loss_bb` — redefinir por limiar de EV jogaria fora um
   terco da evidencia.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.progressao import (wilson, encolher_taxa, taxa_de_erro, melhorou_de_verdade,
                                progresso_de_coleta, FORCA_DO_PRIOR)


def _dec(label='standard', ev=None, stack=None):
    """Decisao no universo de medicao (com gabarito e com familia)."""
    return {'gto_label': 'covered', 'label': label, 'spot_family_key': 'f',
            'ev_loss_bb': ev, 'stack_bb': stack}


# ── Wilson ─────────────────────────────────────────────────────────────────────────────────────

def test_wilson_nunca_colapsa_para_largura_zero():
    """O motivo de nao usar a aproximacao normal. Com k=0 e n=5 a normal daria (0,0): certeza
    absoluta de zero erros a partir de 5 observacoes."""
    b, a = wilson(0, 5)
    assert b == 0.0 and a > 0.4, (b, a)
    b, a = wilson(5, 5)
    assert a == 1.0 and b < 0.6, (b, a)


def test_wilson_aperta_conforme_a_amostra_cresce():
    larg_20 = wilson(4, 20)[1] - wilson(4, 20)[0]
    larg_200 = wilson(40, 200)[1] - wilson(40, 200)[0]
    assert larg_200 < larg_20 / 2, (larg_20, larg_200)


def test_wilson_sem_amostra_cobre_TUDO_e_nao_devolve_zero():
    """n=0 e "nao sei nada", que e o intervalo inteiro. Devolver (0,0) faria uma familia vazia
    parecer perfeita."""
    assert wilson(0, 0) == (0.0, 1.0)


def test_wilson_fica_dentro_de_zero_e_um():
    for k, n in ((0, 3), (3, 3), (1, 2), (7, 9), (0, 1)):
        b, a = wilson(k, n)
        assert 0.0 <= b <= a <= 1.0, (k, n, b, a)


# ── Encolhimento (winner's curse) ──────────────────────────────────────────────────────────────

def test_amostra_pequena_encolhe_QUASE_TODO_para_a_populacao():
    """4 erros em 4 decisoes nao e 100% de taxa de erro, e um leak que entrou no Top-3 assim entrou
    por sorteio. Com prior de 20, o baseline encolhe para perto da media populacional."""
    t = encolher_taxa(4, 4, taxa_populacional=0.20)
    assert 0.20 < t < 0.40, t


def test_amostra_grande_quase_nao_encolhe():
    t = encolher_taxa(400, 1000, taxa_populacional=0.20)
    assert abs(t - 0.40) < 0.01, t


def test_no_minimo_de_validacao_o_peso_e_meio_a_meio():
    """Com n = FORCA_DO_PRIOR, o encolhido e a media exata entre observado e populacional. E o
    freio deliberado: a familia mediana tem muito menos que isso."""
    n = int(FORCA_DO_PRIOR)
    t = encolher_taxa(n, n, taxa_populacional=0.10)   # observado = 100%
    assert abs(t - 0.55) < 1e-9, t                    # (20 + 20*0.10) / 40


def test_sem_amostra_o_baseline_E_a_populacao():
    assert encolher_taxa(0, 0, taxa_populacional=0.25) == 0.25


# ── Taxa de erro ───────────────────────────────────────────────────────────────────────────────

def test_taxa_de_erro_herda_o_veredito_de_3_niveis():
    """`small_mistake` e `clear_mistake` sao Erro; `standard` e Correto; `marginal` e Aceitavel e
    NAO conta como erro. Redefinir isso aqui criaria dois numeros discordando na cara do aluno."""
    r = taxa_de_erro([_dec('standard')] * 6 + [_dec('marginal')] * 2
                     + [_dec('small_mistake')] + [_dec('clear_mistake')])
    assert r['n'] == 10 and r['n_erros'] == 2, r
    assert r['taxa'] == 0.2


def test_taxa_reporta_o_INTERVALO_e_nao_so_o_ponto():
    r = taxa_de_erro([_dec('small_mistake')] * 2 + [_dec('standard')] * 8)
    assert r['wilson_baixo'] < r['taxa'] < r['wilson_alto']


def test_decisao_sem_gabarito_sai_do_DENOMINADOR_e_e_contada():
    """Sem gabarito nao e acerto. Se entrasse, a taxa de erro pareceria melhor quanto menor fosse
    a cobertura — incentivo exatamente invertido."""
    r = taxa_de_erro([_dec('small_mistake')] * 2 + [_dec('standard')] * 8
                     + [{'gto_label': 'uncovered', 'label': 'standard', 'spot_family_key': 'f'}] * 90)
    assert r['n'] == 10 and r['taxa'] == 0.2, r
    assert r['fora_por_motivo'] == {'sem_gabarito': 90}


def test_cobertura_de_EV_e_reportada_SEPARADA_da_taxa():
    """Sao coberturas diferentes (85,8% contra 62,7% em producao) e misturar num numero so
    esconderia isso. O EV serve a magnitude, a taxa serve a validacao."""
    r = taxa_de_erro([_dec('standard', ev=0.1, stack=40)] * 5 + [_dec('standard')] * 5)
    assert r['n'] == 10 and r['n_com_ev'] == 5
    assert r['cobertura_ev_pct'] == 50.0
    assert r['ev_medio_winsorizado'] == 0.1


def test_EV_absurdo_nao_domina_a_media_da_familia():
    """Um no degenerado (ha 13 em producao, `|ev_diff|` ate 5116) dentro da familia destruiria a
    serie. A winsorizacao capa pelo stack."""
    r = taxa_de_erro([_dec('standard', ev=0.2, stack=40)] * 9 + [_dec('clear_mistake', ev=41604.0, stack=11.7)])
    assert r['ev_medio_winsorizado'] < 1.5, r['ev_medio_winsorizado']


def test_familia_vazia_nao_inventa_taxa():
    r = taxa_de_erro([])
    assert r['n'] == 0 and r['taxa'] is None and r['pode_afirmar'] is False
    assert r['cobertura_ev_pct'] is None and r['ev_medio_winsorizado'] is None


# ── O veredito de melhora ──────────────────────────────────────────────────────────────────────

def test_melhora_REAL_e_reconhecida():
    base = taxa_de_erro([_dec('clear_mistake')] * 30 + [_dec('standard')] * 30)   # 50%
    rec = taxa_de_erro([_dec('clear_mistake')] * 2 + [_dec('standard')] * 58)     # 3,3%
    v, motivo = melhorou_de_verdade(base, rec, taxa_populacional=0.30)
    assert v == 'melhorou', (v, motivo)


def test_melhora_de_SORTEIO_nao_e_creditada():
    """O caso que a spec chama de creditar variancia: baseline extremo em amostra pequena e uma
    janela recente que parece melhor mas cujo intervalo ainda cobre o baseline encolhido."""
    base = taxa_de_erro([_dec('clear_mistake')] * 8 + [_dec('standard')] * 2)     # 80% em n=10
    rec = taxa_de_erro([_dec('clear_mistake')] * 8 + [_dec('standard')] * 12)     # 40% em n=20
    v, motivo = melhorou_de_verdade(base, rec, taxa_populacional=0.30)
    assert v == 'indefinido', (v, motivo)


def test_SEM_ENCOLHIMENTO_o_sorteio_passaria():
    """Falsifica o proprio guarda: comparando contra o baseline CRU (80%) em vez do encolhido, a
    mesma janela recente seria declarada melhora. E a prova de que o encolhimento esta fazendo
    trabalho, e nao so decorando o codigo."""
    rec = taxa_de_erro([_dec('clear_mistake')] * 8 + [_dec('standard')] * 12)
    assert rec['wilson_alto'] < 0.80, 'contra o baseline CRU isto passaria como melhora'
    base_encolhido = encolher_taxa(8, 10, 0.30)
    assert rec['wilson_alto'] >= base_encolhido, 'contra o encolhido, nao passa'


def test_amostra_insuficiente_e_INDEFINIDO_e_nunca_piorou():
    """"Ainda estou coletando" nao e "voce nao melhorou". Colapsar as duas mente em silencio."""
    base = taxa_de_erro([_dec('clear_mistake')] * 30 + [_dec('standard')] * 30)
    rec = taxa_de_erro([_dec('standard')] * 3)
    v, motivo = melhorou_de_verdade(base, rec)
    assert v == 'indefinido' and 'amostra' in motivo, (v, motivo)


def test_piora_tambem_e_detectada():
    """A reabertura de leak depende disto: e o gatilho de "o EV real da familia regrediu"."""
    base = taxa_de_erro([_dec('clear_mistake')] * 3 + [_dec('standard')] * 57)    # 5%
    rec = taxa_de_erro([_dec('clear_mistake')] * 40 + [_dec('standard')] * 20)    # 67%
    v, motivo = melhorou_de_verdade(base, rec, taxa_populacional=0.05)
    assert v == 'piorou', (v, motivo)


def test_sem_baseline_nao_afirma():
    rec = taxa_de_erro([_dec('standard')] * 40)
    assert melhorou_de_verdade(None, rec)[0] == 'indefinido'
    assert melhorou_de_verdade(taxa_de_erro([]), rec)[0] == 'indefinido'


def test_encolhimento_e_OPT_IN_e_sem_ele_o_baseline_nao_muda():
    """Sem `taxa_populacional`, o baseline encolhe em direcao a SI MESMO, ou seja, nao encolhe.

    Isso nao e detalhe de API. O encolhimento corrige winner's curse, e winner's curse so existe
    quando a familia foi SELECIONADA por ser extrema. Medido varrendo as 504 familias dos dois
    usuarios com mais volume em producao, com encolhimento aplicado em TODAS: 12 "piorou" contra
    3 "melhorou". O mecanismo e simetrico — encolher puxa baseline baixo para cima (facilita
    "piorou") e baseline alto para baixo (dificulta "melhorou"). Numa familia nao selecionada por
    extremidade, a correcao vira distorcao.
    """
    base = taxa_de_erro([_dec('clear_mistake')] * 2 + [_dec('standard')] * 38)    # 5% em n=40
    rec = taxa_de_erro([_dec('clear_mistake')] * 8 + [_dec('standard')] * 32)     # 20% em n=40

    # Sem populacional: compara contra os 5% observados.
    sem, _ = melhorou_de_verdade(base, rec)
    # Com populacional alta: o baseline de 5% e puxado PARA CIMA, e a mesma piora fica mais dificil
    # de declarar — a prova de que o parametro muda o veredito e por isso precisa ser deliberado.
    com, _ = melhorou_de_verdade(base, rec, taxa_populacional=0.30)
    assert sem == 'piorou', sem
    assert com == 'indefinido', com


# ── Barra de coleta ────────────────────────────────────────────────────────────────────────────

def test_progresso_mostra_COLETA_e_nao_resultado():
    """Com gate honesto um aluno de 5 torneios/mes veria "validando..." por semanas e o produto
    pareceria morto. O que avanca toda semana e a coleta."""
    p = progresso_de_coleta(14)
    assert p == {'coletadas': 14, 'alvo': 20, 'faltam': 6, 'pct': 70.0, 'completo': False}


def test_progresso_nao_passa_de_100_nem_fica_negativo():
    assert progresso_de_coleta(50)['pct'] == 100.0 and progresso_de_coleta(50)['faltam'] == 0
    assert progresso_de_coleta(-3)['coletadas'] == 0


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
