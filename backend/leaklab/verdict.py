"""
verdict.py — fonte ÚNICA do veredito de DISPLAY em 3 níveis: Correto / Aceitável / Erro.

A plataforma mantém INTERNAMENTE 4 níveis de SEVERIDADE (`label`: standard / marginal /
small_mistake / clear_mistake) + a FREQUÊNCIA (`gto_label`) — necessários para ELO, ranking
de leaks, study plan e análises cognitivas. Mas o que o USUÁRIO vê colapsa em 3, dirigido
pela SEVERIDADE (custo de EV), encerrando a dualidade frequência×severidade (raiz dos bugs
card≠badge e do "Desvio Crítico" num desvio barato). A frequência vira CONTEXTO (barras de
estratégia), não veredito.

Mapa:  standard → Correto · marginal → Aceitável · small/clear_mistake → Erro.
"""

# Os 3 níveis canônicos de display.
CORRECT    = 'correct'
ACCEPTABLE = 'acceptable'
ERROR      = 'error'

# Severidade (label) → nível de display. Ausente/desconhecido → None (sem veredito).
_SEVERITY_TO_LEVEL = {
    'standard':      CORRECT,
    'marginal':      ACCEPTABLE,
    'small_mistake': ERROR,
    'clear_mistake': ERROR,
}


def verdict3(label):
    """Severidade (`label`) → nível de display de 3 níveis. None quando não há label
    classificável (ex.: spot sem cobertura)."""
    return _SEVERITY_TO_LEVEL.get((label or '').strip().lower())


def is_error(label) -> bool:
    """Atalho: a jogada é um ERRO no display de 3 níveis? (mesma régua da aderência)."""
    return verdict3(label) == ERROR


# Ações que INVESTEM fichas (continuar), em contraste com fold. Cobre variantes de all-in.
_ICM_CONTINUE_ACTIONS = frozenset({'call', 'raise', 'bet', 'allin', 'jam', 'shove'})


def icm_zone_softens_fold(icm_pressure, active_players, played_action, best_action) -> bool:
    """Gate zona-ICM (SÓ folds): o grading é ChipEV e não modela ICM. Sob ICM real,
    tight-is-right — foldar uma mão que o ChipEV manda CONTINUAR (call/raise/shove) não
    é erro, é uma APROXIMAÇÃO (o modelo não enxerga o risk premium). Este gate diz quando
    NÃO marcar esse aperto como "Erro".

    Escopo deliberadamente estreito (decisão de produto):
    - Só quando o hero FOLDOU. NUNCA abranda call/shove loose (aí o ChipEV segue mandando;
      um call -$EV sob ICM é ainda pior, não queremos aprová-lo).
    - Só em zona-ICM: `icm_pressure == 'high'` E mesa curta (`active_players <= 6`). A mesa
      curta aproxima "fundo no torneio" sem depender do tamanho do field (que o HH não traz).
      Um short stack full-ring no early/mid NÃO é zona-ICM: lá acumular +cEV importa, e um
      aperto ali é leak de verdade que deve continuar sendo marcado.
    """
    if (icm_pressure or '').strip().lower() != 'high':
        return False
    try:
        if active_players is not None and int(active_players) > 6:
            return False
    except (TypeError, ValueError):
        pass
    if (played_action or '').strip().lower() != 'fold':
        return False
    return (best_action or '').strip().lower() in _ICM_CONTINUE_ACTIONS


# ── Piso por DIREÇÃO ───────────────────────────────────────────────────────────────────────────
#
# Ações em que o hero PÕE fichas por iniciativa própria.
_ACOES_AGRESSIVAS = {'raise', 'bet', 'jam', 'shove', 'allin', 'all-in', '3bet', '4bet', 'reraise'}

# Rótulos de frequência em que a agressão pode ser CO-ÓTIMA. Num nó misto onde o solver
# raisa 45% e folda 55%, raisar não é erro de direção — é o outro lado do mix.
_MIX_LEGITIMO = ('gto_mixed', 'gto_correct')

_SEV = {'standard': 0, 'marginal': 1, 'small_mistake': 2, 'clear_mistake': 3, 'critical': 4}


def is_verdict_error_signal(gto_action, action_taken, played_freq=None, in_range=None) -> bool:
    """Sinal CANÔNICO de erro de DIREÇÃO. True ⇒ a mão nunca pode ser 'correta'/'aceitável',
    independente de ev_loss baixo.

    Captura: o GTO folda a mão (fora do range de continuação) mas o hero AGREDIU; ou a ação
    tomada tem frequência GTO ~0 / está fora do range.

    NÃO olha `gto_label` — é só o sinal. Quem decide se ele vira piso é `piso_por_direcao`.
    """
    ga = (gto_action or '').lower().strip()
    at = (action_taken or '').lower().strip()
    if at not in _ACOES_AGRESSIVAS:
        return False
    if ga == 'fold':                                     # GTO descarta a mão; hero agrediu
        return True
    if played_freq is not None and played_freq < 0.05:   # ação com freq ~0 (fora do mix)
        return True
    if in_range is False:                                # fora do range (agressão preflop)
        return True
    return False


def piso_por_direcao(label, gto_label, gto_action, action_taken,
                     played_freq=None, in_range=None) -> str:
    """Aplica o piso de erro por direção, RESPEITANDO o mix legítimo. Fonte única da regra.

    ── Por que isto virou função ──────────────────────────────────────────────────────────────
    A regra vivia em dois lugares. O reconcile (`_reconcile_label`) excluía `gto_correct` e
    `gto_mixed`; o motor tinha a MESMA regra escrita à mão, sem a exclusão, e com um comentário
    dizendo "espelha o is_verdict_error_signal do reconcile" — que não espelhava.

    O resultado medido em produção em 11/08: 12 decisões com o selo `GTO Correto` e o veredito
    `small_mistake` no mesmo card, todas com score exatamente 0,19 (o piso da banda de
    small_mistake). Eram nós MISTOS: o solver raisava entre 30% e 49% do tempo, o hero raisou, e
    o produto chamou de erro. Um relabel completo levaria isso de 12 para 19.

    Comentário não é evidência (CLAUDE.md, item 8) e regra em N lugares vira função (item 5).

    ── DELIBERADO em 14/08 (família 2 da revisão com o coach): o piso NÃO cede a EV ínfimo ──
    Quatro opens fora do range (K9o, K7o, J3o, K3o) com EV confiável de 0,10-0,22bb foram
    gradados como veniais pelo coach humano, e a proposta de rebaixar o piso para 'marginal'
    quando o custo confiável é < 0,25bb foi colocada ao dono do produto — que decidiu MANTER:
    o leak é ENTRAR na mão; custa pouco por instância e é reincidente no agregado, e apontá-lo
    como Erro é a função do produto. 30 decisões no acervo nessa janela ficam como estão.
    Se um dia isto reabrir, a mudança exige as TRÊS camadas juntas (este piso, o reconcile e o
    clamp RC-D do frontend) + goldens + relabel — mudar só uma recria o card contraditório.
    """
    if gto_label in _MIX_LEGITIMO:
        return label
    if not is_verdict_error_signal(gto_action, action_taken, played_freq, in_range):
        return label
    return label if _SEV.get(label, 0) >= _SEV['small_mistake'] else 'small_mistake'


# ── PROCEDÊNCIA DO VEREDITO ─────────────────────────────────────────────────────────────────
#
# Nasceu da pergunta do dono em 24/08: "o que precisamos para garantir que o veredito seja
# confiável?". Medido no acervo: **1.503 decisões (14,8%) não conseguem dizer de onde veio o
# veredito** — não estão erradas, estão MUDAS, porque o campo nunca existiu. Sem ele, "confiável"
# não é verificável nem por teste nem por auditoria: não dá para separar "o solver disse" de "o
# motor achou" olhando o dado gravado.
#
# O dano concreto da ausência: 189 de 495 acusações em que a carta reprova a jogada (38%) saem
# sem um bb de custo, e mesmo assim usam a linguagem de GTO na tela. Um juiz de poker leu o
# sintoma sem ver o código: "quanto menos o motor sabe do custo, mais duro ele acusa".
#
# Vocabulário PEQUENO de propósito — três valores, mutuamente exclusivos, em ordem de força:

SOLVER = 'solver'   # nó do solver postflop para ESTE spot (a resposta mais forte que existe)
CARTA  = 'carta'    # range preflop (GW/chart) — estratégia de equilíbrio, sem EV do nó
MOTOR  = 'motor'    # heurístico do produto: equity, pot odds, posição. NÃO é GTO.

_ORDEM = (SOLVER, CARTA, MOTOR)

# Fontes de EV que valem como QUANTIDADE (espelha `_EV_RELIABLE_SOURCES` do engine; a lista vive
# lá porque é ela que gradua severidade — aqui só se pergunta se existe custo confiável).
_FONTES_COM_CUSTO = ('gw_har', 'solver_hand', 'gto_tree', 'hand_aware')


# Fontes de EV por ORIGEM do gabarito. A distinção não é cosmética: `gw_har` é captura do GTO
# Wizard (uma CARTA de range), enquanto `solver_hand`/`hand_aware`/`gto_tree` são nós resolvidos
# para aquele spot. Uma primeira versão desta função olhava só `gto.available` e classificava
# **378 decisões preflop como `solver`** — porque no preflop o motor também preenche `gto`, com
# `ev_loss_source: 'gw_har'`. Foi a medição por street que pegou; o campo estava preenchido e
# errado, que é pior que vazio.
_FONTES_DE_SOLVER = ('solver_hand', 'hand_aware', 'gto_tree')
_FONTES_DE_CARTA = ('gw_har',)


def procedencia(gto=None, preflop_gto=None, street=None) -> str:
    """De ONDE veio este veredito: SOLVER, CARTA ou MOTOR. Nunca None.

    `motor` não é um estado de erro — é a resposta honesta para o spot que o produto não cobre.
    O que a procedência habilita é a regra que faltava: **só quem tem procedência `solver` pode
    falar a linguagem de GTO na tela**; `motor` diz que é leitura do motor.

    A classificação segue a FONTE do gabarito, não o `available`: os dois dicts ficam disponíveis
    no preflop e só `ev_loss_source` separa carta de nó resolvido. Sem fonte declarada, decide a
    street — preflop é território de carta, postflop é de solver.
    """
    if isinstance(gto, dict) and gto.get('available'):
        fonte = (gto.get('ev_loss_source') or '').lower()
        if fonte in _FONTES_DE_SOLVER:
            return SOLVER
        if fonte in _FONTES_DE_CARTA:
            return CARTA
        return CARTA if (street or '').lower() == 'preflop' else SOLVER
    if isinstance(preflop_gto, dict) and preflop_gto.get('available'):
        return CARTA
    return MOTOR


def tem_custo_medido(gto=None, preflop_gto=None) -> bool:
    """Existe EV em bb, de fonte que vale como quantidade?

    Separado da procedência de propósito: um nó do solver PODE não trazer EV utilizável (spot
    fora da calibração, nó degenerado). Juntar as duas coisas num campo só foi o que permitiu
    `major_leak` sem custo — a acusação herdava a autoridade do solver sem herdar o número.
    """
    for d in (gto, preflop_gto):
        if not isinstance(d, dict) or not d.get('available'):
            continue
        if d.get('ev_loss_bb') is None:
            continue
        if (d.get('ev_loss_source') or '') in _FONTES_COM_CUSTO:
            return True
    return False


def pode_falar_como_gto(procedencia_valor: str, custo_medido: bool) -> bool:
    """A tela pode usar a linguagem de GTO ("leak", "erro contra o equilíbrio") nesta decisão?

    Vale para SOLVER e para CARTA — a carta do GTO Wizard É estratégia de equilíbrio, e `gw_har`
    consta das fontes de EV confiáveis do engine. A primeira versão exigia SOLVER e teria calado
    358 decisões preflop legítimas do torneio de teste; a distinção solver/carta serve para
    EXIBIR a origem, não para censurar a carta.

    O que a regra barra é `motor`: heurístico de equity e pot odds não é equilíbrio, e chamar seu
    desvio de "leak" é a falsa confiança que a procedência existe para eliminar.

    Exige custo medido junto porque é o "quanto custou" que sustenta a palavra. Medido em 24/08:
    189 de 495 acusações com a carta reprovando saíam sem um bb de custo.
    """
    return procedencia_valor in (SOLVER, CARTA) and bool(custo_medido)

# Piso de custo para ACUSAR. Abaixo disto o desvio e ruido de mesa: nao vira erro.
#
# Medido no acervo em 25/08: 45 acusacoes com `ev_loss` abaixo de 0,10bb. Um juiz de poker pegou
# duas na amostra -- 0,05bb e 0,06bb -- e as duas traziam, na MESMA linha, o proprio motor
# dizendo `is_leak: false, justified: true`.
PISO_CUSTO_PARA_ACUSAR_BB = 0.10


def custo_irrelevante_para_acusar(ev_loss_bb) -> bool:
    """O custo medido e pequeno demais para sustentar uma acusacao?

    So responde True quando HA custo medido: sem numero nao ha o que julgar aqui, e a ausencia
    de custo e tratada por outra regra (a da linguagem de GTO, em `pode_falar_como_gto`).
    """
    if ev_loss_bb is None:
        return False
    try:
        return abs(float(ev_loss_bb)) < PISO_CUSTO_PARA_ACUSAR_BB
    except (TypeError, ValueError):
        return False


# ── Severidade sem custo ───────────────────────────────────────────────────────────────────
#
# `pode_falar_como_gto` resolveu a LINGUAGEM: sem custo medido a tela nao chama o desvio de leak.
# Faltava a MAGNITUDE, e ela vazava por dois caminhos, medidos no acervo em 26/08:
#
#   * **47 `clear_mistake` com `ev_loss_bb` NULL nos 47.** O veredito mais duro do produto, sem um
#     bb atras dele.
#   * **score ate 0,900 sem custo**, com a mesma mediana de quem tem custo (0,270 x 0,267). A
#     origem e `opp_cost = top_freq - played_freq` multiplicado por 0,90 em `decision_engine_v11`:
#     um gap de FREQUENCIA com nome de custo. E a familia de [[project_severidade_por_ev]]
#     ("o motor sabia com que frequencia e nao sabia quanto custa") viva noutro caminho. Como
#     `priority_score = COUNT(*) * AVG(score)` ordena o plano de estudo, a magnitude inventada
#     decidia o que o aluno estuda primeiro.
#
# A linha e: **frequencia e medida, custo nao.** Jogada que a carta faz 0% das vezes sustenta
# "isto esta fora da estrategia"; nao sustenta "isto custou caro". Entao a acusacao permanece e o
# que cai e a afirmacao de tamanho.
TETO_DE_SEVERIDADE_SEM_CUSTO = 'small_mistake'


def severidade_sem_custo(label, custo_medido) -> str:
    """Rebaixa o veredito quando nao ha custo medido para sustentar a magnitude.

    So mexe no topo da escala: `clear_mistake` -> `small_mistake`. NAO absolve — `small_mistake`
    continua sendo acusacao, porque a frequencia zero da carta e evidencia de verdade. Com custo
    medido, nada muda.
    """
    if custo_medido:
        return label
    return TETO_DE_SEVERIDADE_SEM_CUSTO if label == 'clear_mistake' else label

# NAO existe uma funcao separada para o SCORE, e isso e deliberado. A primeira versao capava o
# score no piso da banda quando nao havia custo -- e DOIS guardas antigos acusaram, com razao:
# `_align_score_to_label` nao pode mexer em score que ja esta dentro da banda, senao 59 de 77
# acusacoes voltam a valer exatamente 0,19 e o plano de estudo volta a ordenar so pela contagem
# (a lesao de 24/08). O teto do ROTULO ja resolve sozinho: com `clear_mistake` virando
# `small_mistake`, a banda passa a ser [0,19; 0,35] e o 0,900 e clampado pelo `hi` que sempre
# existiu. Menos codigo, e o mesmo efeito onde o dano estava medido.


# ── Procedencia de quem teve a ULTIMA palavra ──────────────────────────────────────────────
#
# O `/replay` recomputa o veredito numa cadeia de camadas (`card_verdict.LAYERS`) e a camada viva
# costuma ser mais severa que a gravada. Mas `verdict_source` e `verdict_has_cost` continuavam
# saindo da LINHA DO BANCO -- dois fatos, duas fontes, o defeito mais recorrente deste projeto.
#
# Medido em 26/08 no torneio 72: tres decisoes exibiam `gto_label: gto_critical` ao lado de
# `verdict_source: motor`. O banco guardava `marginal` 0,13 com `gto_label` NULO; o card mostrava
# `small_mistake` 0,19 com rotulo de solver. O objeto se contradizia -- dizia "isto veio do
# heuristico" e "o solver classificou como desvio critico" na mesma linha. Um juiz de coerencia
# pegou as tres.
_PROCEDENCIA_DA_CAMADA = {
    'live':     SOLVER,     # estrategia viva do solver
    'preflop':  CARTA,      # ranges estaticas
}


def procedencia_da_camada(camada, procedencia_gravada: str) -> str:
    """Quem responde pelo veredito EXIBIDO, dado quem teve a ultima palavra na cadeia.

    `stored` e as camadas de multiway devolvem a procedencia gravada -- as de multiway nao trocam
    a FONTE do veredito, elas suprimem ou suavizam o que a fonte disse. Camada desconhecida
    tambem cai na gravada: na duvida, nao promover autoridade que ninguem provou.

    NAO mexe no custo. A camada viva traz rotulo, nao traz EV -- entao `pode_falar_como_gto`
    continua False para estes casos, que e o certo: procedencia sem custo nao autoriza a palavra.
    """
    return _PROCEDENCIA_DA_CAMADA.get(camada) or procedencia_gravada or MOTOR


# ── A camada viva nao PROMOVE ──────────────────────────────────────────────────────────────
#
# O `/replay` recomputa o veredito numa cadeia de camadas e, quando a cadeia dizia "erro" e o
# rotulo gravado nao era acusacao, a tela exibia `small_mistake`. Isso e uma SEGUNDA politica de
# veredito rodando por cima da do motor -- e mais simples que ela.
#
# Medido em 26/08 no torneio 72: **24 divergencias entre a lista e o card em 486 decisoes**, e a
# direcao e o que denuncia: **22 do card acusando mais, 0 do card absolvendo**. O aluno abre a
# lista, le "Correto", e o card da mesma decisao diz "Erro".
#
# A pergunta decisiva foi: quem esta certo? Duas medicoes responderam:
#   * o regrade completo do acervo devolveu `MUDAM: 0` -- banco e motor CONCORDAM;
#   * das 24, em **22 o motor USOU o no do solver** (so 2 sao recusa declarada). Ou seja, nao e
#     falta de cobertura: e o motor tendo aplicado suas regras (piso por direcao, teto de EV,
#     suavizacao de ICM, piso de custo) e a cadeia viva ignorando todas.
#
# Entao quem destoa e a cadeia viva. Ela continua util para o que so ela sabe -- frequencia da
# mao, recomendacao viva, DEMOCAO -- mas nao pode transformar em acusacao o que o motor julgou
# que nao era.
def label_exibido_da_camada_viva(label_gravado, erro_ao_vivo):
    """(label, is_error) para a tela, quando a cadeia viva discorda do motor.

    A cadeia viva pode manter e pode rebaixar; NAO pode promover. Se o motor nao acusou, a tela
    nao acusa -- e `is_error` acompanha, senao sobra `is_error: True` ao lado de um rotulo que
    nao e erro, que e a contradicao seguinte.
    """
    if label_gravado in ('small_mistake', 'clear_mistake'):
        return label_gravado, True
    return label_gravado, False


# ── Equity vs mao ALEATORIA nao condena um FOLD ────────────────────────────────────────────
#
# Ja existiam DOIS guardas de `equitySource == 'vs_random'`, os dois PREFLOP e os dois na direcao
# do CALL -- tirar a absolvicao de quem pagou. Faltava o simetrico, que e onde nasce acusacao
# falsa: postflop, na direcao do FOLD.
#
# A direcao e o argumento inteiro, e ja estava escrita em [[project_sem_gabarito_nao_e_erro]]:
#
#     equity inflada CONDENA quem folda   e   ABSOLVE quem paga
#
# Contra o range que apostou, a equity vs aleatoria e inflada por construcao. Um juiz de poker leu
# o sintoma na tela: o produto manda PAGAR com nove-alto porque "32% > 27,7% exigidos" -- e os 32%
# sao contra mao aleatoria; contra quem aposta 57% do pote a mao tem uns 10%.
#
# MEDIDO em 26/08, com ablacao (mesmo input, so a equity mexida):
#   * 77 acusacoes de fold postflop no acervo; 74 usam equity vs_random;
#   * 55 tem custo medido, **22 nao**;
#   * nessas 22, derrubar a equity para 0,01 faz a acusacao SUMIR em **22 de 22**. Ou seja: a
#     equity vs aleatoria e a UNICA evidencia sustentando a acusacao.
#
# A regra `sem gabarito nao e erro` ja capava o fold, mas so quando NAO havia cobertura nenhuma.
# As 22 tem no de solver -- entao passavam por ela e eram acusadas por um numero medido contra
# outra coisa.
#
# O conserto NAO absolve: baixa para `marginal`, que diz "nao temos base para chamar de erro".
# Mesma escolha dos dois guardas preflop -- anda no sentido de tirar a culpa, nunca no de criar.
def equity_vs_random_nao_condena_fold(label, street, equity_source, acao_do_hero,
                                      custo_medido) -> str:
    """Rebaixa a acusacao de um FOLD postflop sustentada so por equity vs mao aleatoria.

    Com CUSTO medido nada muda: ai existe um numero de verdade por tras, e ele nao veio do
    estimador. Com equity `vs_range` tambem nada muda -- a conta esta contra quem apostou.
    """
    if custo_medido:
        return label
    if label not in ('small_mistake', 'clear_mistake'):
        return label
    if (street or '').lower() == 'preflop':
        return label
    if (equity_source or '') != 'vs_random':
        return label
    if (acao_do_hero or '').lower() != 'fold':
        return label
    return 'marginal'


def estimador_infla_a_equity(hero_cards, board, street) -> bool:
    """O estimador esta no regime em que SUPERVALORIZA a mao do hero?

    A direcao do erro do estimador depende da CLASSE DA MAO, e e isso que decide se uma acusacao
    de fold pode ou nao se apoiar nele:

        `air` (nada feito)  -> o estimador INFLA  -> acusar o fold e falso
        par+ / value        -> o estimador SUBvaloriza -> a acusacao pode ser boa

    A armadilha esta escrita no lugar de origem e viaja com a funcao: `made_hand_category(None,
    None)` devolve `'air'`. **Sem cartas ou sem board nao da para AFIRMAR que o hero nao tem nada**,
    e a regra inteira se apoia nisso -- aplicar ali seria ler ausencia de dado como o caso que me
    convem. Por isso os dois `bool(...)` antes da classificacao.

    Preflop nao tem board e nao tem classe de mao feita: o regime e outro, e a resposta e True
    (era o comportamento inline de origem).

    Virou funcao quando o segundo consumidor apareceu (26/08, o guarda de `vs_random` no fold
    postflop). Regra 5 do CLAUDE.md: regra em N lugares vira funcao, com teste que varre os N+1.
    """
    if (street or '').lower() == 'preflop':
        return True
    if not hero_cards or not board:
        return False
    try:
        from leaklab.bet_intent import made_hand_category
        return made_hand_category(hero_cards, board) not in ('value', 'middle')
    except Exception:                                                     # noqa: BLE001
        return False
