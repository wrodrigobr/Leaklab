# -*- coding: utf-8 -*-
"""Auditoria dirigida por MODO DE FALHA (AY-9): detectores, nao leitura.

── Por que existe ────────────────────────────────────────────────────────────────────────

Em 04-05/09, seis dos oito defeitos da sprint nasceram de perguntas do dono olhando a tela.
Nenhum apareceu num diff. O que os une e serem AUSENCIAS ou DIVERGENCIAS entre dois lugares —
nao ha linha errada para ler, entao revisao de codigo nao acha.

Cada padrao abaixo vira um detector que VARRE o codigo. Dois contratos:

1. **O detector prova que acha o caso conhecido** (regra 1). Cada padrao tem um teste que
   forja ou aponta a instancia que o originou e exige que o detector a encontre. Detector que
   nao acha o caso conhecido esta quebrado, e "zero achados" seria o pior resultado possivel.
2. **Achado aceito e DECLARADO com motivo.** As allowlists sao a memoria do que foi visto e
   decidido; sem motivo, nao entra. O teste falha em achado NOVO — e assim a auditoria vira
   guarda permanente em vez de valer uma vez.

Padrao sem detector confiavel SAI da lista (P6 ficou so a versao estreita). Nao vira tarefa
de inspecao manual: isso e o que ja nao funcionava.

── O que os prototipos acharam em 05/09, antes de virar teste ────────────────────────────

  P1  `d.label IN ('small_mistake','clear_mistake')` em 8 funcoes — a mesma forma do
      `founder` fora do MRR: `critical` existe na escada de severidade e nao esta em nenhuma.
  P2  a guarda de `apply_stripe_subscription` (conhecida; hoje protegida pela 2a trava).
  P3  DOIS mapas de posicao alem dos ja conhecidos (`get_player_dna` e `pos_bucket`), e o
      `pos_bucket` poe MP1 em "MP" e LJ em "EP" — o MESMO assento em baldes diferentes.
  P4  `preflop_autocapture` (conhecido; AY-8).
  P5  `study_plan_current` (conhecido; hoje com drift por banda). `cmp_`/`causal_v4_` eram
      PREFIXOS — falso positivo que ensinou o detector a exigir literal inteiro.
  P6  `_preview` com SELECT proprio em 2 scripts — a forma exata do `expire_subscriptions`.
  P7  `posProfile.tooltip` descrevendo faixa verde e ponto REMOVIDOS na vespera — quarta vez
      a legenda desse card, e a primeira em que um detector pegou antes do dono.
"""
import io
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.pop('DATABASE_URL', None)

_B = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_RAIZ = os.path.abspath(os.path.join(_B, '..'))
_F = os.path.join(_RAIZ, 'frontend', 'src')


def _ler(rel):
    return io.open(os.path.join(_B, rel), encoding='utf-8', errors='ignore').read()


def _spans(texto):
    """[(nome, corpo)] por funcao de nivel de modulo."""
    pos = [m.start() for m in re.finditer(r'^def (\w+)\(', texto, re.M)]
    out = []
    for i, p in enumerate(pos):
        fim = pos[i + 1] if i + 1 < len(pos) else len(texto)
        out.append((re.match(r'^def (\w+)\(', texto[p:], re.M).group(1), texto[p:fim]))
    return out


# ═══════════════════════════════════════════════════════════════════════════════════════
# P1 — A MESMA REGRA ESCRITA N VEZES (fragmento de WHERE identico em >= 3 funcoes)
# ═══════════════════════════════════════════════════════════════════════════════════════

_P1_ACEITOS = {
    "d.label IN ('small_mistake','clear_mistake')":
        'ACHADO 05/09, aberto (AY-12): "o que conta como erro" copiado em 8 funcoes. `critical` '
        'existe em `verdict._SEV` e nao esta em nenhuma — latente (0 em prod), mas e a forma '
        'exata do `founder` fora do MRR. Virar `_SQL_ACUSADO` com varredura N+1.',
}


def _p1_fragmentos(texto):
    frag = defaultdict(set)
    for nome, corpo in _spans(texto):
        for w in re.findall(r"(?:AND|WHERE)\s+([\w.]+\s*(?:NOT\s+)?IN\s*\([^)]{8,80}\))", corpo):
            frag[re.sub(r'\s+', ' ', w)].add(nome)
    return {w: fs for w, fs in frag.items() if len(fs) >= 3}


def test_p1_o_detector_acha_regra_copiada():
    # A 1a versao forjava `IN ('a','b')`: 7 caracteres, abaixo do minimo de 8 do regex, e a
    # prova falhava — o fixture estava mais curto que qualquer regra real.
    forjado = "\n".join("def f%d():\n    q = \"WHERE x.k IN ('alpha','beta')\"\n" % i for i in range(3))
    assert "x.k IN ('alpha','beta')" in _p1_fragmentos(forjado)


def test_p1_regra_copiada_em_3_ou_mais_funcoes_esta_declarada():
    achados = _p1_fragmentos(_ler('database/repositories.py'))
    novos = {w: fs for w, fs in achados.items() if w not in _P1_ACEITOS}
    assert not novos, 'fragmento de WHERE copiado sem declaracao: ' + '; '.join(
        '%s em %d funcoes (%s)' % (w, len(fs), ', '.join(sorted(fs))[:80]) for w, fs in novos.items())


# ═══════════════════════════════════════════════════════════════════════════════════════
# P2 — GUARDA QUE SE DESARMA (a guarda le uma coluna que a propria funcao poe em NULL)
# ═══════════════════════════════════════════════════════════════════════════════════════

_P2_ACEITOS = {
    'apply_stripe_subscription':
        'o caso que originou (05/09). A guarda por `mp_subscription_id` continua, e o downgrade '
        'ainda apaga o campo — mas a 2a trava, por PROCEDENCIA (`plan_source`), nao se apaga. '
        'Ver test_rebaixamento_de_plano.',
}


def _p2_guardas_que_se_desarmam(texto):
    out = []
    for nome, corpo in _spans(texto):
        guardas = re.findall(r"if\s+(_?\w+)\s+and\b[^\n]*:\s*\n(?:[^\n]*\n){0,4}?\s*return", corpo)
        nulos = set(re.findall(r"(\w+)\s*=\s*NULL", corpo))
        for g in guardas:
            m = re.search(r"%s\s*=.*?\.get\('(\w+)'\)" % re.escape(g), corpo)
            if m and m.group(1) in nulos:
                out.append((nome, g, m.group(1)))
    return out


def test_p2_o_detector_acha_a_guarda_do_stripe():
    achados = _p2_guardas_que_se_desarmam(_ler('database/repositories.py'))
    assert any(n == 'apply_stripe_subscription' and c == 'mp_subscription_id' for n, _, c in achados), achados


def test_p2_guarda_que_se_desarma_esta_declarada():
    achados = _p2_guardas_que_se_desarmam(_ler('database/repositories.py'))
    novos = [(n, g, c) for n, g, c in achados if n not in _P2_ACEITOS]
    assert not novos, 'guarda cuja falha apaga a propria pre-condicao: %s' % novos


# ═══════════════════════════════════════════════════════════════════════════════════════
# P3 — LITERAL CRU ONDE EXISTE HELPER CANONICO
# ═══════════════════════════════════════════════════════════════════════════════════════

#: (helper, regex do literal cru, regex que ISENTA a linha por ja usar o canonico)
_P3_PARES = (
    ('_ACOES_ALLIN / _norm_gto_action', r"IN\s*\([^)]*'(?:shove|jam|allin)'[^)]*\)",
     r'_SQL_ALLIN|_SQL_RAISE_OU_JAM|_SQL_VOLUNTARIO|_SQL_AGRESSIVO|_ACOES_ALLIN'),
    ('normalize_position / rotulos_do_assento', r"'MP1'", r'_POSITION_NORM|rotulos_do_assento|normalize_position'),
    ('_build_tournament_filter', r"imported_at\s*>=\s*\?", r'COALESCE'),
)
_P3_ARQUIVOS = ('database/repositories.py', 'api/app.py', 'leaklab/decision_engine_v11.py')

_P3_ACEITOS = {
    # (AY-13 fechado em 06/09: `get_player_dna` e `pos_bucket` passaram a usar `grupo_posicional`.)
    ('_build_tournament_filter', 'database/repositories.py', 'get_evolution_metrics'):
        'PRESENCA de dados (ver test_eixo_de_tempo): o ramo default e o check do plano de estudos.',
}


def _p3_achados():
    out = []
    for helper, cru, isenta in _P3_PARES:
        for arq in _P3_ARQUIVOS:
            texto = _ler(arq)
            for nome, corpo in _spans(texto):
                for m in re.finditer(cru, corpo):
                    linha = corpo[corpo.rfind('\n', 0, m.start()) + 1: corpo.find('\n', m.end())]
                    if re.search(isenta, linha) or linha.strip().startswith('#'):
                        continue
                    out.append((helper, arq, nome))
    return sorted(set(out))


def test_p3_o_detector_acha_literal_cru():
    """Forjado. A 1a versao apontava para o `'MP1'` do DNA — e o AY-13 o removeu no dia
    seguinte, derrubando a prova. Mesma licao do P7: prova que depende de um caso que um commit
    conserta nao e prova."""
    forjado = "def f():\n    ep = {'UTG', 'MP1', 'HJ'}\n    q = \"WHERE t.imported_at >= ?\"\n"
    _, cru_pos, isenta_pos = _P3_PARES[1]
    _, cru_eixo, isenta_eixo = _P3_PARES[2]
    assert re.search(cru_pos, forjado) and not re.search(isenta_pos, forjado)
    assert re.search(cru_eixo, forjado) and not re.search(isenta_eixo, forjado)
    assert _p3_achados(), 'a varredura nao acha nada: o detector morreu'


def test_p3_literal_cru_esta_declarado():
    novos = [a for a in _p3_achados() if a not in _P3_ACEITOS]
    assert not novos, 'literal cru onde existe helper canonico: %s' % novos


# ═══════════════════════════════════════════════════════════════════════════════════════
# P4 — ARQUIVO VERSIONADO ESCRITO EM RUNTIME
# ═══════════════════════════════════════════════════════════════════════════════════════

_P4_ACEITOS = {
    'leaklab/preflop_autocapture.py':
        'ACHADO 05/09, aberto (AY-8): `_persist_ranges` reescreve `docs/leaklab_gto_ranges.json`, '
        'que e rastreado pelo git. Em prod se perde no deploy e um worker apaga a captura do '
        'outro. Conserto: captura vai para tabela; o JSON fica so como base.',
}


def _p4_escritas_em_arquivo_do_repo():
    out = set()
    for raiz, _, arqs in os.walk(_B):
        if any(x in raiz for x in ('tests', '__pycache__', 'scripts', 'venv')):
            continue
        for a in arqs:
            if not a.endswith('.py'):
                continue
            p = os.path.join(raiz, a)
            src = io.open(p, encoding='utf-8', errors='ignore').read()
            for m in re.finditer(r"(os\.replace\(|json\.dump\(|open\([^)]*['\"]w['\"])", src):
                ctx = src[max(0, m.start() - 300):m.start() + 120]
                if re.search(r"docs/[\w./-]+|_RANGES_FILE|_PKO_RANGES_FILE", ctx):
                    out.add(os.path.relpath(p, _B).replace('\\', '/'))
    return sorted(out)


def test_p4_o_detector_acha_o_autocapture():
    assert 'leaklab/preflop_autocapture.py' in _p4_escritas_em_arquivo_do_repo()


def test_p4_escrita_em_arquivo_do_repo_esta_declarada():
    novos = [a for a in _p4_escritas_em_arquivo_do_repo() if a not in _P4_ACEITOS]
    assert not novos, 'codigo de aplicacao escrevendo em arquivo versionado: %s' % novos


# ═══════════════════════════════════════════════════════════════════════════════════════
# P5 — CHAVE DE CACHE CONSTANTE (literal inteiro; prefixo concatenado nao conta)
# ═══════════════════════════════════════════════════════════════════════════════════════

_P5_ACEITOS = {
    'study_plan_current':
        'chave canonica do plano por aluno, DE PROPOSITO (um plano vivo por pessoa). A invalidacao '
        'vem do `drift_sig`, que desde 05/09 inclui a BANDA de cada stat do HUD alem dos leaks. '
        'Ver test_drift_do_plano_por_banda.',
}


def _p5_chaves_constantes():
    out = set()
    for arq in ('leaklab/llm_explainer.py', 'api/app.py', 'database/repositories.py'):
        for m in re.finditer(r"(?:db_key|cache_key)\s*=\s*['\"]([\w:._-]+)['\"]\s*(?:#|\n)", _ler(arq)):
            out.add(m.group(1))
    return sorted(out)


def test_p5_o_detector_acha_a_chave_do_plano_e_ignora_prefixos():
    achados = _p5_chaves_constantes()
    assert 'study_plan_current' in achados, achados
    assert 'cmp_' not in achados and 'causal_v4_' not in achados, 'prefixo concatenado nao e chave constante'


def test_p5_chave_constante_esta_declarada():
    novos = [k for k in _p5_chaves_constantes() if k not in _P5_ACEITOS]
    assert not novos, 'chave de cache constante sem declaracao (o conteudo depende de entradas que nao estao na chave?): %s' % novos


# ═══════════════════════════════════════════════════════════════════════════════════════
# P6 — DUAS POLITICAS (so a forma detectavel: `_preview`/`dry` de script com SELECT proprio)
# ═══════════════════════════════════════════════════════════════════════════════════════

_P6_ACEITOS = {
    'backfill_coach_trials.py':
        'ACHADO 05/09, aberto (AY-14): `_preview` com SELECT proprio. Conferir se o filtro do '
        'preview e o MESMO da execucao — foi assim que o `expire_subscriptions` mentia.',
    'expire_coach_trials.py':
        'ACHADO 05/09, aberto (AY-14): idem.',
}


def _p6_previews_com_select():
    out = []
    pasta = os.path.join(_B, 'scripts')
    for a in sorted(os.listdir(pasta)):
        if not a.endswith('.py'):
            continue
        s = io.open(os.path.join(pasta, a), encoding='utf-8', errors='ignore').read()
        if 'dry-run' not in s and 'dry_run' not in s:
            continue
        for nome, corpo in _spans(s):
            if re.search(r'preview|dry|previa|simula', nome, re.I) and re.search(r'\bSELECT\b', corpo):
                out.append(a)
    return sorted(set(out))


def test_p6_o_detector_acha_preview_com_select():
    forjado = "def main():\n    pass\ndef _preview():\n    q = 'SELECT 1'\n"
    assert any(re.search(r'preview', n) and 'SELECT' in c for n, c in _spans(forjado))
    assert _p6_previews_com_select(), 'a varredura nao achou nenhum: o detector morreu'


def test_p6_preview_com_politica_propria_esta_declarado():
    novos = [a for a in _p6_previews_com_select() if a not in _P6_ACEITOS]
    assert not novos, ('script com preview de SQL proprio (dry-run pode descrever outra operacao): %s. '
                       'O certo e o dry-run chamar a MESMA funcao com dry_run=True.' % novos)


# ═══════════════════════════════════════════════════════════════════════════════════════
# P7 — COPY QUE DESCREVE DESENHO (lista de revisao: chave com palavra de desenho + consumidor)
# ═══════════════════════════════════════════════════════════════════════════════════════

_DESENHO = re.compile(r'\b(faixa|banda|trilho|tracinho|ponto|marcador|verde|vermelh[oa]|amarel[oa]|'
                      r'barra|seta|círculo|circulo|anel|badge|selo)\b', re.I)

#: Chaves que citam desenho e foram CONFERIDAS contra o componente. Se o texto mudar, a chave
#: cai daqui (o valor e o hash do texto) e volta a exigir conferencia.
_P7_CONFERIDAS = {
    'ghost.tooltip':          'vermelho = cor do erro no card de drill, existe',
    'streets.tooltip':        'vermelho = street com mais erro, existe',
    'form.tooltip':           'verde/amarelo/vermelho = semaforo da forma recente, existe',
    'v2.posHint':             'verde/vermelho = alinhamento GTO por posicao, existe no V2PositionCard',
    'v2.causalConclusion':    '"ponto" e figurado (ponto de partida), nao desenho',
    'sessionContext.footnote':'barra = barra de progresso da sessao, existe',
    'perfil.faixaBuyin':      'faixa = faixa de buy-in (intervalo), nao desenho',
    'heatmap.ajuda':          'verde/vermelho = celulas do heatmap, existe',
    'posProfile.tooltip':     'REESCRITO 05/09: descrevia faixa verde e ponto removidos na vespera (4a vez a legenda desse card). Agora descreve so numero, amostra e Total.',
    # 06/09 (AY-15): a faixa verde VOLTOU, so na celula do RFI (`Regua` em V2PositionProfileCard, `data-testid=regua-rfi`).
    'posProfile.legend':      'faixa verde = a regua do RFI, existe (Regua, so onde ha `ref`)',
    'posProfile.tolerance':   'faixa = a mesma faixa verde do RFI, existe; "folga" e a FOLGA_DA_REFERENCIA_PP do backend',
    'posProfile.stackHands':  'faixa = faixa de STACK (intervalo em bb), nao desenho',
    'posProfile.detail.note': 'faixa = a faixa verde da regua no painel contra quem (Detalhe em V2PositionProfileCard), existe',
}


def _p7_chaves_de_desenho():
    loc = json.load(io.open(os.path.join(_F, 'i18n', 'locales', 'pt-BR', 'dashboard.json'), encoding='utf-8'))
    def flat(d, pref=''):
        for k, v in d.items():
            kk = pref + k
            if isinstance(v, dict):
                yield from flat(v, kk + '.')
            elif isinstance(v, str):
                yield kk, v
            elif isinstance(v, list):
                for s in v:
                    if isinstance(s, str):
                        yield kk, s
    return sorted({k for k, v in flat(loc) if _DESENHO.search(v)})


def test_p7_o_detector_acha_copy_de_desenho():
    """Forjado, e nao apontado para `posProfile.tooltip`: este mesmo commit reescreveu o tooltip
    sem as palavras de desenho, entao a prova apontada para ele passou a falhar — prova que
    depende de um caso que o proprio commit conserta nao e prova."""
    assert _DESENHO.search('A faixa verde e a referencia; o ponto e voce.')
    assert not _DESENHO.search('Seu numero em cada assento, com a amostra ao lado.')
    assert _p7_chaves_de_desenho(), 'a varredura nao achou nenhuma chave: o detector morreu'
    assert 'v2.posHint' in _p7_chaves_de_desenho()          # caso real, conferido e declarado


def test_p7_copy_com_palavra_de_desenho_foi_conferida():
    novos = [k for k in _p7_chaves_de_desenho() if k not in _P7_CONFERIDAS]
    assert not novos, ('copy cita elemento de desenho e ninguem conferiu se o componente ainda o tem: %s. '
                       'Abra o componente que consome a chave; se o elemento existe, declare; se nao, reescreva.' % novos)


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, str(e)[:400]))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
