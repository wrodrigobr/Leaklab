"""
test_academy_variety.py — Testa a taxa de variedade e a correção semântica dos geradores da Academia.

Cobertura:
  1. Variedade: >= 70% de questões únicas em 50 chamadas por gerador.
  2. Validade de street: odds_vs_equity nunca usa preflop ou river (regra 2/4 não se aplica).

Roda sem banco de dados (mock de _fetch_math_decision).
"""
import sys, os, re, random, unittest, unittest.mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.academy as acad

# ── Helper ─────────────────────────────────────────────────────────────────────

def _fingerprint(q: dict) -> str:
    """Identifica uma questão pelo texto e resposta correta."""
    return f"{q['question'][:120]}|{q['correct_index']}"


def _diversity(generator_fn, n: int = 50) -> tuple[int, int, float]:
    """Retorna (únicos, total, taxa)."""
    seen = set()
    for _ in range(n):
        q = generator_fn()
        seen.add(_fingerprint(q))
    rate = len(seen) / n
    return len(seen), n, rate


MIN_DIVERSITY = 0.70   # mínimo 70% únicos em 50 chamadas


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestAcademyVariety(unittest.TestCase):

    def setUp(self):
        # Seed fixa → variedade determinística. Sem isto, o estado global do RNG
        # deixado por testes anteriores na suite completa fazia o gerador mais
        # apertado (3bet_pot, ~80% típico) oscilar abaixo do mínimo de 70% (flaky).
        random.seed(20260530)

    def _assert_diverse(self, name: str, fn, n: int = 50):
        unique, total, rate = _diversity(fn, n)
        self.assertGreaterEqual(
            rate, MIN_DIVERSITY,
            f"{name}: apenas {unique}/{total} únicos ({rate:.0%}) — abaixo do mínimo {MIN_DIVERSITY:.0%}"
        )
        print(f"  ✔ {name}: {unique}/{total} únicos ({rate:.0%})")

    # ── Geradores diretos (sem banco) ──────────────────────────────────────────

    def test_outs_count_variety(self):
        self._assert_diverse("outs_count", acad._outs_count_question)

    def test_equity_estimate_variety(self):
        self._assert_diverse("equity_estimate", acad._equity_estimate_question)

    def test_spr_commitment_variety(self):
        self._assert_diverse("spr_commitment", acad._spr_commitment_question)

    def test_icm_spot_variety(self):
        self._assert_diverse("icm_spot", acad._icm_spot_question)

    def test_3bet_pot_variety(self):
        self._assert_diverse("3bet_pot", acad._3bet_pot_question)

    def test_bubble_defense_structure(self):
        """bubble_defense: espaço pequeno (resposta fixa) → teste estrutural, não de
        variedade. A cobertura do dispatcher fica no test_tournament_variety."""
        q = acad._bubble_defense_question()
        self.assertEqual(q['type'], 'bubble_defense')
        self.assertEqual(len(q['options']), 3)
        self.assertTrue(q['options'][q['correct_index']])
        self.assertIn('MENOS', q['options'][q['correct_index']])   # over-defense = defender menos
        self.assertTrue(q['explanation'] and q['mental_tip'])
        print("  ✔ bubble_defense structure")

    def test_multiway_drill_structure(self):
        """Treino da aula de Multiway: 3 tipos, estrutura válida, resposta certa alinhada
        aos conceitos (blefe→desistir, sizing→menor, meio→apertado)."""
        seen = set()
        for _ in range(30):
            q = acad.generate_multiway_question(user_id=1)
            self.assertIn(q['type'], ('mw_bluff', 'mw_sizing', 'mw_middle'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'mw_bluff', 'mw_sizing', 'mw_middle'})  # os 3 aparecem
        # variedade: o pool parametrizado gera muitos enunciados distintos (dedup no
        # front garante unicidade em sessão; aqui só conferimos que há margem)
        fps = {_fingerprint(acad.generate_multiway_question(1)) for _ in range(120)}
        self.assertGreaterEqual(len(fps), 12, f"pool multiway pequeno: {len(fps)} enunciados")
        # respostas certas por conceito
        import leaklab.academy as A
        self.assertIn('Desistir', A._mw_bluff_question()['options'][A._mw_bluff_question()['correct_index']])
        self.assertEqual(A._mw_sizing_question()['options'][A._mw_sizing_question()['correct_index']], 'Menor')
        self.assertEqual(A._mw_middle_question()['options'][A._mw_middle_question()['correct_index']], 'Jogar apertado')
        print("  ✔ multiway drill structure")

    def test_icm_drill_structure(self):
        """Treino da aula de ICM: reusa icm_spot + bubble_defense (foco em ICM)."""
        seen = set()
        for _ in range(40):
            q = acad.generate_icm_question(user_id=1)
            self.assertIn(q['type'], ('icm_spot', 'bubble_defense'))
            self.assertGreaterEqual(len(q['options']), 2)
            self.assertTrue(0 <= q['correct_index'] < len(q['options']))
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'icm_spot', 'bubble_defense'})  # os dois aparecem
        print("  ✔ icm drill structure")

    def test_postflop_drill_structure(self):
        """Treino da aula de Postflop: cbet_dry, cbet_wet, barrel."""
        seen = set()
        for _ in range(40):
            q = acad.generate_postflop_question(user_id=1)
            self.assertIn(q['type'], ('cbet_dry', 'cbet_wet', 'barrel'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'cbet_dry', 'cbet_wet', 'barrel'})
        import leaklab.academy as A
        self.assertIn('C-bet pequeno', A._cbet_dry_question()['options'][A._cbet_dry_question()['correct_index']])
        print("  ✔ postflop drill structure")

    _SIZING_TIPOS = {'open_size', 'threebet_size', 'spr_size',
                     'price_size', 'cbet_texture', 'range_shape'}

    def test_sizing_drill_structure(self):
        """Treino da aula de Bet Sizing: os 6 tipos aparecem e nenhum sai malformado."""
        seen = set()
        for _ in range(200):
            q = acad.generate_sizing_question(user_id=1)
            self.assertIn(q['type'], self._SIZING_TIPOS)
            self.assertEqual(len(q['options']), 3)
            self.assertEqual(len(set(q['options'])), 3, f"alternativas repetidas: {q['options']}")
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, self._SIZING_TIPOS)
        print("  ✔ sizing drill structure")

    def test_sizing_variety(self):
        """O acervo de bet sizing era 7 enunciados, com 38% dos sorteios numa ÚNICA pergunta
        estática (a do SPR). Foi a queixa do jogador. Este teste é o piso do acervo."""
        self._assert_diverse("sizing", lambda: acad.generate_sizing_question(user_id=1))

    def test_nenhum_tipo_de_sizing_e_pergunta_unica(self):
        """A variedade do TEMA esconde tipo estático: com 6 tipos, um deles congelado num texto
        só ainda deixa o total diverso. Foi assim que a queixa nasceu — o `spr_size` era uma
        pergunta fixa e mesmo assim o tema parecia variado no agregado. Cada tipo responde pelo
        próprio acervo.
        """
        # Usa o MESMO helper dos outros dois temas. Esta versão nasceu antes dele, com o piso 4
        # embutido, e por isso continuava verde com o `range_shape` congelado numa descrição só
        # (1 × 2 formas × 2 ruas = 4). Dois pisos com o mesmo nome e valores diferentes é como o
        # trabalho de hoje seria desfeito sem ninguém ver.
        self._assert_piso_por_tipo('sizing', acad.generate_sizing_question, self._SIZING_TIPOS)

    def test_spr_bate_com_a_conta(self):
        """A pergunta de SPR virou calculada. Se a faixa marcada não bater com o número do
        enunciado, o exercício ensina errado, que é pior do que repetir."""
        import re
        n = 0
        for _ in range(400):
            q = acad.generate_sizing_question(user_id=1)
            if q['type'] != 'spr_size':
                continue
            n += 1
            spr = float(re.search(r'SPR de ~([\d.]+)', q['question']).group(1))
            esperada = next(t for a, b, t in acad._SPR_FAIXAS if a <= spr < b)
            self.assertEqual(q['options'][q['correct_index']], esperada,
                             f"SPR {spr} caiu na faixa errada")
        self.assertGreater(n, 20, "amostra de spr_size pequena demais para concluir")
        print(f"  ✔ spr calculado: {n} casos coerentes")

    def test_preco_bate_com_a_conta(self):
        """equity necessária = aposta / (pote + 2×aposta). Conta fechada, sem margem para opinião."""
        import re
        n = 0
        for _ in range(400):
            q = acad.generate_sizing_question(user_id=1)
            if q['type'] != 'price_size':
                continue
            n += 1
            pote = float(re.search(r'Pote de (\d+) BB', q['question']).group(1))
            aposta = float(re.search(r'\(([\d.]+) BB\)', q['question']).group(1))
            esperado = round(aposta / (pote + 2 * aposta) * 100)
            dito = int(q['options'][q['correct_index']].strip('~%'))
            self.assertLessEqual(abs(dito - esperado), 1,
                                 f"pote {pote}, aposta {aposta}: disse {dito}%, conta dá {esperado}%")
        self.assertGreater(n, 20, "amostra de price_size pequena demais para concluir")
        print(f"  ✔ preço calculado: {n} casos coerentes")

    # ── Acervo por TIPO nos temas que foram expandidos ────────────────────────
    # A variedade do TEMA esconde tipo estático: com 5 tipos, um congelado num texto só ainda
    # deixa o agregado diverso. Foi assim que a queixa do bet sizing nasceu.
    # 10, e não 4: com piso 4 dava para congelar o `range_shape` numa descrição só (1 × 2 formas
    # × 2 ruas = 4) e o teste seguia verde — o piso permitia desfazer o trabalho todo. O menor
    # tipo dos três temas expandidos tem 16, então 10 é folga real e não número escolhido para
    # passar.
    _PISO_POR_TIPO = 10

    def _assert_piso_por_tipo(self, nome, fn, tipos_esperados, n=1500):
        import collections
        por = collections.defaultdict(set)
        for _ in range(n):
            q = fn(user_id=1)
            por[q['type']].add(q['question'][:160])
        self.assertEqual(set(por), set(tipos_esperados), f'{nome}: tipos servidos mudaram')
        magros = {t: len(v) for t, v in por.items() if len(v) < self._PISO_POR_TIPO}
        self.assertEqual(magros, {}, f'{nome}: tipos com acervo pobre demais: {magros}')
        print(f"  ✔ {nome} por tipo: {({t: len(v) for t, v in sorted(por.items())})}")

    def test_open_em_fichas_converte_certo_e_o_distrator_e_errado_de_verdade(self):
        """A conversão BB → fichas, e o distrator que quase entrou errado.

        A primeira versão usava o MIN-RAISE como alternativa errada: 2 BB contra os 2,2 BB
        corretos. Isso não é resposta errada, é a mesma resposta com outro arredondamento (1200
        contra 1300 numa BB de 600), e o exercício marcaria certo como errado. O distrator que
        ficou é o erro que a pergunta existe para corrigir: seguir abrindo o valor do nível
        ANTERIOR depois que o blind subiu.
        """
        import re
        vistos = 0
        for _ in range(2000):
            q = acad.generate_sizing_question(user_id=1)
            if q['type'] != 'open_size' or 'fichas' not in q['question']:
                continue
            vistos += 1
            bb = int(re.search(r'Blinds \d+/(\d+)', q['question']).group(1))
            certa = int(q['options'][q['correct_index']])
            self.assertEqual(certa, round(2.2 * bb / 100) * 100,
                             f'conversão errada com BB={bb}: {q["options"]}')
            nums = sorted(int(o) for o in q['options'])
            menor = min(nums[1] - nums[0], nums[2] - nums[1])
            self.assertGreaterEqual(menor, bb * 0.5,
                                    f'alternativas a menos de meia BB de distância: {q["options"]}')
        self.assertGreater(vistos, 100, 'poucos casos de conversão para concluir')
        print(f"  ✔ open em fichas: {vistos} conversões conferidas")

    def test_open_curto_nao_ensina_open_pequeno(self):
        """A profundidade tem que ENTRAR na resposta, senão a variação é cosmética.

        Era esse o defeito: quatro enunciados que só trocavam o nome da posição, e a posição nem
        aparecia na resposta, sempre "2 a 2,5 BB". O jogador lia quatro textos e decorava uma frase.
        """
        import re
        curtos = fundos = 0
        for _ in range(2000):
            q = acad.generate_sizing_question(user_id=1)
            m = re.search(r'Torneio, (\d+) BB efetivos', q['question'] or '')
            if not m:
                continue
            stack = int(m.group(1))
            certa = q['options'][q['correct_index']]
            if stack <= 10:
                curtos += 1
                self.assertIn('shove ou fold', certa, f'{stack} BB ensinando open pequeno: {certa}')
            else:
                fundos += 1
                self.assertIn('2 a 2,5 BB', certa, f'{stack} BB deveria abrir pequeno: {certa}')
        self.assertGreater(curtos, 30, 'stacks curtos quase não apareceram')
        self.assertGreater(fundos, 100, 'stacks profundos quase não apareceram')
        print(f"  ✔ open por profundidade: {curtos} curtos, {fundos} fundos, respostas distintas")

    def test_nenhum_tipo_de_blocker_e_pergunta_unica(self):
        """Blockers tinha 5 enunciados no total, DOIS deles estáticos."""
        self._assert_piso_por_tipo('blockers', acad.generate_blocker_question, acad._BLOCKER_TIPOS)

    def test_nenhum_tipo_de_mdf_e_pergunta_unica(self):
        """MDF tinha 6 enunciados FIXOS sobre três tamanhos de aposta."""
        self._assert_piso_por_tipo('mdf', acad.generate_mdf_question, acad._MDF_TIPOS)

    def test_mdf_bate_com_as_contas(self):
        """MDF + alpha = 100% para qualquer tamanho, e as duas saem dos NÚMEROS do enunciado.

        Calcular pela fração que gerou os números, e não pelos números mostrados, marcaria como
        certa uma resposta que não fecha com o enunciado que o jogador está lendo — o arredondamento
        da aposta para BB inteiro move a fração.
        """
        import re
        vistos = set()
        for _ in range(1500):
            q = acad.generate_mdf_question(user_id=1)
            dito = q['options'][q['correct_index']]
            if q['type'] in ('mdf', 'alpha', 'bluff_ratio'):
                pote = int(re.search(r'pote (?:tem|de) (\d+) BB', q['question']).group(1))
                ap = int(re.search(r'aposta(?:ndo)? (\d+) BB', q['question']).group(1))
                esperado = {'mdf':         round(pote / (pote + ap) * 100),
                            'alpha':       round(ap / (pote + ap) * 100),
                            'bluff_ratio': round(ap / (pote + 2 * ap) * 100)}[q['type']]
                self.assertEqual(dito, f'~{esperado}%', f'{q["type"]}: {q["question"]}')
                vistos.add(q['type'])
        self.assertEqual(vistos, {'mdf', 'alpha', 'bluff_ratio'}, 'nem todos os tipos foram conferidos')
        for _, fr in acad._TAMANHOS_MDF:
            self.assertEqual(acad._pct_mdf(fr) + acad._pct_alpha(fr), 100,
                             f'MDF + alpha deixou de fechar em 100% para fração {fr}')
        print("  ✔ mdf/alpha/bluff_ratio: conta fecha com os números do enunciado")

    def test_alternativas_numericas_nao_ficam_coladas(self):
        """Alternativa indistinguível não mede conhecimento, só frustra.

        A primeira versão pegava os valores mais PRÓXIMOS como distratores e produziu
        `['~69%', '~73%', '~74%']`. MDF é aproximação: ninguém separa 73 de 74, e o exercício
        vira sorteio.
        """
        import re
        conferidos = 0
        for fn in (acad.generate_mdf_question, acad.generate_sizing_question):
            for _ in range(1200):
                q = fn(user_id=1)
                nums = [int(m.group(1)) for m in
                        (re.fullmatch(r'~?(\d+)%', o.strip()) for o in q['options']) if m]
                if len(nums) != 3:
                    continue
                conferidos += 1
                nums.sort()
                menor = min(nums[1] - nums[0], nums[2] - nums[1])
                # LITERAL, não `acad._SEPARACAO_MIN_PCT`: ler a constante que se está testando é o
                # mesmo vício do teste da janela — baixar a constante para 0 deixava este teste
                # verde com as alternativas coladas na tela.
                self.assertGreaterEqual(menor, 4,
                                        f'{q["type"]}: alternativas coladas {q["options"]}')
        self.assertGreater(conferidos, 300, 'amostra pequena demais para concluir')
        self.assertGreaterEqual(acad._SEPARACAO_MIN_PCT, 4,
                                'a constante de separação foi afrouxada abaixo do que este teste cobra')
        print(f"  ✔ separação das alternativas: {conferidos} perguntas conferidas")

    def test_board_de_blocker_e_sempre_jogavel(self):
        """O board é sorteado, e um board ilegal ou de textura errada faz a resposta CERTA deixar
        de ser certa. Quatro coisas travadas, cada uma com o motivo:

        - carta repetida: board impossível;
        - board pareado: abre full house, e a cor deixa de ser o máximo;
        - três cartas do naipe dentro de uma janela de 5 ranks: abre straight flush, e o Ás do
          naipe deixa de bloquear o máximo;
        - quatro cartas seguidas: passa a existir mais de uma ponta bloqueadora.
        """
        import collections
        ordem = '23456789TJQKA'
        vistos = 0
        for _ in range(3000):
            q = acad.generate_blocker_question(user_id=1)
            board = (q.get('context') or {}).get('board')
            if not board:
                continue
            vistos += 1
            cartas = board.split()
            self.assertEqual(len(set(cartas)), 4, f'carta repetida: {board}')
            ranks = [c[0] for c in cartas]
            self.assertEqual(len(set(ranks)), 4, f'board pareado: {board}')
            naipes = collections.Counter(c[1] for c in cartas)
            if 'cor máxima' in q['explanation']:
                self.assertEqual(max(naipes.values()), 3, f'sem 3 do naipe: {board}')
                s = [n for n, c in naipes.items() if c == 3][0]
                idx = sorted(ordem.index(c[0]) for c in cartas if c[1] == s)
                self.assertGreaterEqual(idx[-1] - idx[0], 5, f'straight flush possível: {board}')
            else:
                self.assertLessEqual(max(naipes.values()), 2, f'3 do mesmo naipe: {board}')
                i = sorted(ordem.index(r) for r in ranks)
                corrida = melhor = 1
                for a, b in zip(i, i[1:]):
                    corrida = corrida + 1 if b == a + 1 else 1
                    melhor = max(melhor, corrida)
                self.assertLessEqual(melhor, 3, f'4 cartas seguidas: {board}')
        self.assertGreater(vistos, 500, 'poucos boards para concluir')
        print(f"  ✔ boards de blocker: {vistos} conferidos, todos jogáveis")

    def test_mao_errada_do_blocker_nao_carrega_o_bloqueador(self):
        """Se a mão 'ruim' sortear o rank bloqueador, a alternativa ERRADA fica tão boa quanto a
        certa — e o exercício marca certo como errado. Aconteceu: o sorteio dela incluía o rank
        da ponta da sequência."""
        import re
        vistos = 0
        for _ in range(3000):
            q = acad.generate_blocker_question(user_id=1)
            if q['type'] != 'blocker_bluff':
                continue
            vistos += 1
            m = re.search(r'segura (\S+) e bloqueia', q['explanation'])
            self.assertIsNotNone(m, f'não achei a carta-chave na explicação: {q["explanation"]}')
            chave = m.group(1)[0]
            board = set(q['context']['board'].split())
            maos = [o for o in q['options'] if re.fullmatch(r'[2-9TJQKA].\s[2-9TJQKA].', o.strip())]
            self.assertEqual(len(maos), 2, f'esperava 2 mãos nas alternativas: {q["options"]}')
            com_chave = [h for h in maos if any(c[0] == chave for c in h.split())]
            self.assertEqual(len(com_chave), 1,
                             f'o bloqueador {chave} aparece em {len(com_chave)} mãos: {q["options"]}')
            for h in maos:
                self.assertFalse(board & set(h.split()), f'mão usa carta do board: {h} / {board}')
        self.assertGreater(vistos, 300, 'poucos casos de blocker_bluff para concluir')
        print(f"  ✔ blocker_bluff: {vistos} casos, só uma mão carrega o bloqueador")

    def test_mdf_drill_structure(self):
        """Treino da aula de MDF & Alpha: os 4 tipos aparecem e nenhum sai malformado."""
        seen = set()
        for _ in range(200):
            q = acad.generate_mdf_question(user_id=1)
            self.assertIn(q['type'], tuple(acad._MDF_TIPOS))
            self.assertEqual(len(q['options']), 3)
            self.assertEqual(len(set(q['options'])), 3, f"alternativas repetidas: {q['options']}")
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, set(acad._MDF_TIPOS))
        print("  ✔ mdf drill structure")

    def test_combos_drill_structure(self):
        """Treino da aula de Combinatória: pair(6), unpaired(16), split, blocker(3)."""
        seen = set()
        for _ in range(50):
            q = acad.generate_combo_question(user_id=1)
            self.assertIn(q['type'], ('combo_pair', 'combo_unpaired', 'combo_split', 'combo_blocker'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'combo_pair', 'combo_unpaired', 'combo_split', 'combo_blocker'})
        import leaklab.academy as A
        self.assertEqual(A._combo_pair_question()['options'][A._combo_pair_question()['correct_index']], '6')
        self.assertEqual(A._combo_blocker_question()['options'][A._combo_blocker_question()['correct_index']], '3')
        print("  ✔ combos drill structure")

    def test_blockers_drill_structure(self):
        """Treino da aula de Blockers: os 5 tipos aparecem e nenhum sai malformado."""
        seen = set()
        for _ in range(200):
            q = acad.generate_blocker_question(user_id=1)
            self.assertIn(q['type'], tuple(acad._BLOCKER_TIPOS))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, set(acad._BLOCKER_TIPOS))
        print("  ✔ blockers drill structure")

    def test_position_drill_structure(self):
        """Treino da aula de Posição, incluindo os exercícios de LARGURA de range.

        150 sorteios, e não 40: com 10 tipos no rodízio, 40 dá ~14% de chance de algum não sair
        e o teste piscar sem nada estar quebrado. Teste que falha sozinho ensina a ignorar falha.
        """
        seen = set()
        for _ in range(150):
            q = acad.generate_position_question(user_id=1)
            self.assertIn(q['type'], ('pos_order', 'pos_best', 'pos_range', 'pos_realization', 'pos_realization_gap', 'pos_coldcall', 'pos_steal_target', 'pos_oop_bluff',
                                    'range_width', 'range_width_compare', 'range_width_conceito'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'pos_order', 'pos_best', 'pos_range', 'pos_realization',
                                'pos_realization_gap', 'pos_coldcall', 'pos_steal_target',
                                'pos_oop_bluff', 'range_width', 'range_width_compare'})
        print("  ✔ position drill structure")

    def test_showdown_drill_structure(self):
        """Treino da aula de Showdown Value: action, why, catch."""
        seen = set()
        for _ in range(40):
            q = acad.generate_sdv_question(user_id=1)
            self.assertIn(q['type'], ('sdv_action', 'sdv_why', 'sdv_catch', 'sdv_bluff_pick', 'sdv_thin_value', 'sdv_bluffcatch', 'sdv_protect'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'sdv_action', 'sdv_why', 'sdv_catch', 'sdv_bluff_pick', 'sdv_thin_value', 'sdv_bluffcatch', 'sdv_protect'})
        print("  ✔ showdown drill structure")

    def test_exploits_drill_structure(self):
        """Treino da aula de Exploits: station, nit, lag."""
        seen = set()
        for _ in range(40):
            q = acad.generate_exploit_question(user_id=1)
            self.assertIn(q['type'], ('exploit_station', 'exploit_nit', 'exploit_lag', 'exploit_sample', 'exploit_overfolder', 'exploit_cost', 'exploit_limper'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'exploit_station', 'exploit_nit', 'exploit_lag', 'exploit_sample', 'exploit_overfolder', 'exploit_cost', 'exploit_limper'})
        print("  ✔ exploits drill structure")

    def test_pko_drill_structure(self):
        """Treino da aula de PKO: cover, power, stage."""
        seen = set()
        for _ in range(40):
            q = acad.generate_pko_question(user_id=1)
            self.assertIn(q['type'], ('pko_cover', 'pko_power', 'pko_stage', 'pko_call_gap', 'pko_bounty_size', 'pko_target', 'pko_late'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'pko_cover', 'pko_power', 'pko_stage', 'pko_call_gap', 'pko_bounty_size', 'pko_target', 'pko_late'})
        print("  ✔ pko drill structure")

    def test_imbalances_drill_structure(self):
        """Treino da aula dos 5 desequilíbrios: polarity, elasticity, board."""
        seen = set()
        for _ in range(40):
            q = acad.generate_imbalance_question(user_id=1)
            self.assertIn(q['type'], ('imb_polarity', 'imb_elasticity', 'imb_board', 'imb_capped', 'imb_overbet', 'imb_bluff_ratio', 'imb_check_range'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'imb_polarity', 'imb_elasticity', 'imb_board', 'imb_capped', 'imb_overbet', 'imb_bluff_ratio', 'imb_check_range'})
        print("  ✔ imbalances drill structure")

    def test_pushfold_drill_structure(self):
        """Treino da aula de push/fold: action, position, call."""
        seen = set()
        for _ in range(40):
            q = acad.generate_pushfold_question(user_id=1)
            self.assertIn(q['type'], ('pf_action', 'pf_position', 'pf_call', 'pf_odds', 'pf_gap', 'pf_ante', 'pf_behind', 'pf_reshove', 'pf_icm_gap'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'pf_action', 'pf_position', 'pf_call', 'pf_odds', 'pf_gap', 'pf_ante', 'pf_behind', 'pf_reshove', 'pf_icm_gap'})
        print("  ✔ pushfold drill structure")

    def test_draws_drill_structure(self):
        """Treino da aula de projetos/semi-blefe: why, when, combo."""
        seen = set()
        for _ in range(40):
            q = acad.generate_draws_question(user_id=1)
            self.assertIn(q['type'], ('draw_why', 'draw_when', 'draw_combo', 'draw_odds', 'draw_implied_fake', 'draw_which_bluff', 'draw_multiway'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'draw_why', 'draw_when', 'draw_combo', 'draw_odds', 'draw_implied_fake', 'draw_which_bluff', 'draw_multiway'})
        print("  ✔ draws drill structure")

    def test_3bet_drill_structure(self):
        """Treino da aula de 3-bet: purpose, polar, blocker."""
        seen = set()
        for _ in range(40):
            q = acad.generate_3bet_question(user_id=1)
            self.assertIn(q['type'], ('tb_purpose', 'tb_polar', 'tb_blocker', 'tb_size', 'tb_flat', 'tb_squeeze', 'tb_vs4bet'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'tb_purpose', 'tb_polar', 'tb_blocker', 'tb_size', 'tb_flat', 'tb_squeeze', 'tb_vs4bet'})
        print("  ✔ 3bet drill structure")

    def test_barrels_drill_structure(self):
        """Treino da aula de turn & river / barrels: turn, giveup, river."""
        seen = set()
        for _ in range(40):
            q = acad.generate_barrel_question(user_id=1)
            self.assertIn(q['type'], ('tr_turn', 'tr_giveup', 'tr_river', 'tr_card_choice', 'tr_giveup_choice', 'tr_sizing_polar', 'tr_range_advantage'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'tr_turn', 'tr_giveup', 'tr_river', 'tr_card_choice', 'tr_giveup_choice', 'tr_sizing_polar', 'tr_range_advantage'})
        print("  ✔ barrels drill structure")

    def test_terms_drill_structure(self):
        """Treino de vocabulário: street, draw, ip."""
        seen = set()
        for _ in range(40):
            q = acad.generate_terms_question(user_id=1)
            self.assertIn(q['type'], ('tm_street', 'tm_draw', 'tm_ip', 'tm_spr_apply', 'tm_mdf_apply', 'tm_range_thinking', 'tm_ev_apply'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'tm_street', 'tm_draw', 'tm_ip', 'tm_spr_apply', 'tm_mdf_apply', 'tm_range_thinking', 'tm_ev_apply'})
        print("  ✔ terms drill structure")

    def test_bankroll_drill_structure(self):
        """Treino da aula de banca & variância: buyins, sample, judge."""
        seen = set()
        for _ in range(40):
            q = acad.generate_bankroll_question(user_id=1)
            self.assertIn(q['type'], ('bk_buyins', 'bk_sample', 'bk_judge', 'bk_downswing', 'bk_roi_sample', 'bk_shot', 'bk_variance_stakes'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'bk_buyins', 'bk_sample', 'bk_judge', 'bk_downswing', 'bk_roi_sample', 'bk_shot', 'bk_variance_stakes'})
        print("  ✔ bankroll drill structure")

    def test_bvb_drill_structure(self):
        """Treino da aula de blind vs blind: bb, sb, position."""
        seen = set()
        for _ in range(40):
            q = acad.generate_bvb_question(user_id=1)
            self.assertIn(q['type'], ('bvb_bb', 'bvb_sb', 'bvb_position', 'bvb_postflop_position', 'bvb_defense_price', 'bvb_limp', 'bvb_3bet'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(q['options'][q['correct_index']])
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'bvb_bb', 'bvb_sb', 'bvb_position', 'bvb_postflop_position', 'bvb_defense_price', 'bvb_limp', 'bvb_3bet'})
        print("  ✔ bvb drill structure")

    def test_leak_to_academy_mapping(self):
        """Matcher leak→aula: casa o card com o módulo certo, sem falso positivo, máx 2."""
        from leaklab.academy_catalog import modules_for_card, attach_academy_modules
        def ids(card):
            return [m['id'] for m in modules_for_card(card)]
        # bolha/ICM: 'preflop/fold' NÃO pode puxar postflop ('flop' dentro de 'preflop').
        icm = ids({'titulo': 'Defesa fraca na bolha',
                   'diagnostico': 'Sob pressao de ICM voce folda demais perto do pay jump',
                   'conceitos': ['ICM'], 'spot': 'preflop/fold'})
        self.assertEqual(icm[0], 'icm')
        self.assertNotIn('postflop', icm)
        # stack curto → pushfold em 1º
        self.assertEqual(ids({'titulo': 'Shove curto errado',
                              'diagnostico': 'Com stack raso da min-raise em vez de shove',
                              'conceitos': ['push/fold'], 'spot': 'preflop/raise'})[0], 'pushfold')
        # multiway
        self.assertIn('multiway', ids({'titulo': 'Pote multiway', 'diagnostico': 'varios jogadores no pote',
                                       'conceitos': ['multiway'], 'spot': 'flop/call'}))
        # no máx 2 módulos, cada um com id+path
        many = modules_for_card({'titulo': 'c-bet no flop com pot odds e posicao',
                                 'diagnostico': 'bet sizing ruim, textura de board, equity',
                                 'conceitos': ['pot odds', 'posicao'], 'spot': 'flop/bet'})
        self.assertLessEqual(len(many), 2)
        for m in many:
            self.assertIn('id', m); self.assertIn('path', m)
        # attach muta os cards do plano
        plan = {'cards': [{'titulo': 'ICM na bolha', 'diagnostico': 'icm', 'conceitos': [], 'spot': 'preflop/fold'}]}
        attach_academy_modules(plan)
        self.assertEqual(plan['cards'][0]['academy_modules'][0]['id'], 'icm')
        # card sem sinal → lista vazia (sem link)
        self.assertEqual(modules_for_card({'titulo': '', 'diagnostico': '', 'conceitos': [], 'spot': ''}), [])
        print("  ✔ leak→academy mapping")

    # ── Geradores via dispatcher (mock: sem banco) ─────────────────────────────

    def test_math_beginner_variety(self):
        """generate_math_question(beginner) — mock sem histórico do usuário."""
        with unittest.mock.patch.object(acad, '_fetch_math_decision', return_value=None):
            fn = lambda: acad.generate_math_question(user_id=1, level='beginner')
            self._assert_diverse("generate_math_question[beginner]", fn)

    def test_math_intermediate_variety(self):
        """generate_math_question(intermediate) — mock sem histórico."""
        with unittest.mock.patch.object(acad, '_fetch_math_decision', return_value=None):
            fn = lambda: acad.generate_math_question(user_id=1, level='intermediate')
            self._assert_diverse("generate_math_question[intermediate]", fn)

    def test_tournament_variety(self):
        """generate_tournament_question — só usa geradores internos, sem banco."""
        fn = lambda: acad.generate_tournament_question(user_id=1)
        self._assert_diverse("generate_tournament_question", fn)

    # ── Teste de repetição com histórico PEQUENO (simula usuário com poucas mãos) ──

    def test_math_beginner_small_history(self):
        """
        Simula usuário com apenas 3 decisões distintas no banco.
        Mesmo com pool pequena, a variedade deve ser >= 70%.
        """
        small_pool = [
            {'pot_size': 10.0, 'facing_bet': 5.0,  'stack_bb': 25, 'm_ratio': 8,
             'label': 'standard', 'action_taken': 'call', 'best_action': 'call',
             'street': 'flop', 'position': 'IP', 'score': 0.8},
            {'pot_size': 20.0, 'facing_bet': 10.0, 'stack_bb': 40, 'm_ratio': 12,
             'label': 'small_mistake', 'action_taken': 'call', 'best_action': 'fold',
             'street': 'turn', 'position': 'OOP', 'score': 0.3},
            {'pot_size': 8.0,  'facing_bet': 8.0,  'stack_bb': 15, 'm_ratio': 4,
             'label': 'clear_mistake', 'action_taken': 'fold', 'best_action': 'call',
             'street': 'river', 'position': 'IP', 'score': 0.1},
        ]

        import itertools
        pool_cycle = itertools.cycle(small_pool)

        with unittest.mock.patch.object(acad, '_fetch_math_decision',
                                        side_effect=lambda uid: next(pool_cycle)):
            fn = lambda: acad.generate_math_question(user_id=1, level='beginner')
            self._assert_diverse("generate_math_question[beginner, small history=3]", fn)


    # ── Street validity tests ──────────────────────────────────────────────────

    def test_odds_vs_equity_rejects_preflop(self):
        """Rule of 2/4 never appears with preflop context."""
        ctx = {'street': 'preflop', 'label': 'standard',
               'action_taken': 'call', 'best_action': 'call', 'position': 'IP'}
        for _ in range(30):
            q = acad._odds_vs_equity_question(10.0, 5.0, ctx)
            m = re.search(r'No \*\*(\w+)\*\*', q['question'])
            street = m.group(1) if m else 'unknown'
            self.assertIn(street, ('flop', 'turn'),
                          f"preflop leaked: {q['question'][:80]}")

    def test_odds_vs_equity_rejects_river(self):
        """Rule of 2/4 never appears with river context (no cards to come)."""
        ctx = {'street': 'river', 'label': 'standard',
               'action_taken': 'call', 'best_action': 'call', 'position': 'IP'}
        for _ in range(30):
            q = acad._odds_vs_equity_question(10.0, 5.0, ctx)
            m = re.search(r'No \*\*(\w+)\*\*', q['question'])
            street = m.group(1) if m else 'unknown'
            self.assertIn(street, ('flop', 'turn'),
                          f"river leaked: {q['question'][:80]}")

    def test_generate_math_intermediate_preflop_history_safe(self):
        """generate_math[intermediate] with preflop history never produces invalid street."""
        bad_ctx = {'street': 'preflop', 'label': 'standard',
                   'action_taken': 'call', 'best_action': 'call', 'position': 'IP'}
        with unittest.mock.patch.object(acad, '_fetch_math_decision', return_value=bad_ctx):
            for _ in range(50):
                q = acad.generate_math_question(user_id=1, level='intermediate')
                if q['type'] == 'odds_vs_equity':
                    m = re.search(r'No \*\*(\w+)\*\*', q['question'])
                    street = m.group(1) if m else 'unknown'
                    self.assertIn(street, ('flop', 'turn'),
                                  f"preflop leaked via dispatcher: {q['question'][:80]}")


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_tests():
    loader  = unittest.TestLoader()
    # Carrega o MÓDULO, não uma classe fixa: com `loadTestsFromTestCase(TestAcademyVariety)`
    # qualquer classe nova neste arquivo era ignorada em silêncio, e um teste que não roda é pior
    # que teste nenhum, porque conta como cobertura.
    suite   = loader.loadTestsFromModule(sys.modules[__name__])
    runner  = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
    result  = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    failed = len(result.failures) + len(result.errors)

    print(f"\n{'='*60}")
    if result.failures or result.errors:
        for label, tb in result.failures + result.errors:
            print(f"FAIL  {label.id().split('.')[-1]}")
            # Print the assertion message only
            lines = tb.strip().split('\n')
            for l in lines[-3:]:
                print(f"      {l}")
        print()
    print(f"Total: {result.testsRun} | Passed: {passed} | Failed: {failed}")



class TestAlternativasEmbaralhadas(unittest.TestCase):
    """A resposta certa não pode morar sempre na mesma posição.

    BUG QUE ESTE TESTE SUBSTITUI: 54 das 59 perguntas escritas à mão tinham `correct_index: 0`, a
    UI não embaralhava, e o quiz inteiro da Academia era vencível clicando na primeira opção sem
    ler o enunciado. XP e acurácia não mediam nada.

    E o teste antigo ERA O GUARDIÃO do bug: ele afirmava `assertEqual(q['correct_index'], 0)`, com
    o comentário "a opção certa é sempre a 1ª". Um contrato que congelava o defeito, e por isso
    ninguém percebeu por tanto tempo.
    """

    AULAS = ['bvb', 'position', '3bet', 'barrel', 'draws', 'exploit', 'imbalance',
             'pko', 'sdv', 'bankroll', 'terms', 'pushfold', 'blocker', 'combo', 'multiway']

    def test_resposta_certa_nao_fica_sempre_na_mesma_posicao(self):
        for aula in self.AULAS:
            gen = getattr(acad, f'generate_{aula}_question', None)
            if gen is None:
                continue
            posicoes = {gen(user_id=1)['correct_index'] for _ in range(120)}
            self.assertGreater(
                len(posicoes), 1,
                f'{aula}: a resposta certa saiu sempre na posição {posicoes} em 120 sorteios. '
                f'O quiz volta a ser vencível sem ler o enunciado.')
        print("  ✔ alternativas embaralhadas em todas as aulas")

    def test_embaralhar_preserva_a_resposta(self):
        """Embaralhar sem remapear o índice seria pior que o viés: passaria a ensinar errado."""
        for aula in self.AULAS:
            gen = getattr(acad, f'generate_{aula}_question', None)
            if gen is None:
                continue
            for _ in range(60):
                q = gen(user_id=1)
                self.assertTrue(
                    q['options'][q['correct_index']],
                    f'{aula}: correct_index aponta para opção vazia')
                self.assertEqual(len(set(q['options'])), len(q['options']),
                                 f'{aula}: alternativas duplicadas tornam o gabarito ambíguo')
        print("  ✔ embaralhamento preserva o gabarito")



# ── Largura de range: a pergunta não pode ensinar número errado ───────────────────────────────
#
# Estes exercícios afirmam um NÚMERO ao jogador ("UTG abre cerca de 20%"). Diferente de uma
# pergunta conceitual, aqui existe uma fonte de verdade — as ranges capturadas — e o exercício
# tem que concordar com ela. Número inventado num exercício é pior que exercício nenhum: ele é
# memorizado com confiança e depois aplicado na mesa.

class TestLarguraDeRange(unittest.TestCase):

    def _larguras(self):
        from leaklab.academy_questions import _larguras_por_posicao
        return _larguras_por_posicao(30.0)

    def test_a_resposta_certa_bate_com_a_range_real(self):
        """A alternativa correta tem que ser a largura REAL da posição citada na pergunta."""
        from leaklab.academy_questions import range_width_question, _faixa
        larguras = self._larguras()
        if len(larguras) < 4:
            self.skipTest('ranges capturadas indisponíveis neste ambiente')
        for _ in range(40):
            q = range_width_question()
            if q['type'] != 'range_width':
                continue
            pos = next((p for p in larguras if q['question'].startswith(p + ' ')), None)
            self.assertIsNotNone(pos, f'pergunta não cita posição conhecida: {q["question"][:60]}')
            esperado = _faixa(larguras[pos])
            self.assertEqual(q['options'][q['correct_index']], esperado,
                             f'{pos}: exercício diz {q["options"][q["correct_index"]]}, '
                             f'range real é {esperado}')

    def test_alternativas_nao_colidem(self):
        """Duas opções que arredondam para o mesmo valor tornam a pergunta impossível."""
        from leaklab.academy_questions import range_width_question
        if len(self._larguras()) < 4:
            self.skipTest('ranges capturadas indisponíveis')
        for _ in range(40):
            q = range_width_question()
            if q['type'] != 'range_width':
                continue
            self.assertEqual(len(set(q['options'])), len(q['options']),
                             f'opções repetidas: {q["options"]}')

    def test_comparacao_aponta_a_posicao_mais_larga(self):
        from leaklab.academy_questions import range_width_compare_question
        larguras = self._larguras()
        if len(larguras) < 2:
            self.skipTest('ranges capturadas indisponíveis')
        for _ in range(40):
            q = range_width_compare_question()
            if q['type'] != 'range_width_compare':
                continue
            certa = q['options'][q['correct_index']]
            a, b = q['question'].split('Quem abre MAIS mãos: ')[1].rstrip('?').split(' ou ')
            mais_larga = a if larguras.get(a, 0) >= larguras.get(b, 0) else b
            self.assertTrue(certa.startswith(mais_larga),
                            f'{a} ({larguras.get(a)}) vs {b} ({larguras.get(b)}): '
                            f'resposta certa diz "{certa[:30]}"')

    def test_contagem_de_combos(self):
        """Par = 6, suited = 4, offsuit = 12. Errar isso desloca todas as larguras."""
        from leaklab.academy_questions import _combos_da_notacao
        self.assertEqual(_combos_da_notacao('AA'), 6)
        self.assertEqual(_combos_da_notacao('AKs'), 4)
        self.assertEqual(_combos_da_notacao('AKo'), 12)
        self.assertEqual(_combos_da_notacao('AA,AKs,AKo'), 22)
        self.assertEqual(_combos_da_notacao(''), 0)
        # 13 pares + 78 suited + 78 offsuit = 1326, o baralho inteiro
        todas = ','.join(['AA'] * 13 + ['AKs'] * 78 + ['AKo'] * 78)
        self.assertEqual(_combos_da_notacao(todas), 1326)


class TestGuardaDeRepeticao(unittest.TestCase):
    """O jogador reportou repetição em /academy/bet-sizing. Medido: o sorteio é uniforme, o
    acervo é que era pequeno (7 enunciados, 38% num só). Acervo cresceu; este guarda é o teto.

    Ele NÃO é janela de N recentes: com acervo de 5 e janela de 4, o gerador precisa acertar o
    único item livre, e medido assim o blockers ainda repetia 5 vezes em 12 exercícios. É
    aritmética, não azar. O que roda é uma RODADA, que zera quando o acervo esgota.
    """

    def setUp(self):
        acad._recentes.clear()

    @staticmethod
    def _gerador_de_acervo(n: int):
        """Gerador falso de acervo conhecido — é a única forma de afirmar algo sobre a rodada
        sem depender do tamanho real de um acervo que muda."""
        def fn(user_id=None):
            i = random.randrange(n)
            return {'question': f'pergunta {i}', 'options': ['a', 'b', 'c'], 'correct_index': 0}
        fn.__name__ = f'gerador_falso_{n}'
        return fn

    @staticmethod
    def _largura_vigente(chave: tuple) -> int:
        """A largura que o guarda vai usar NESTA chamada, lida do estado ANTES dela.

        A janela cresce junto com o acervo observado. Medir a sequência inteira contra a largura
        FINAL julga os primeiros sorteios por uma régua que ainda não existia quando eles saíram
        — foi o que me fez ler violação onde não havia.
        """
        st = acad._recentes.get(chave) or {'acervo': set()}
        return min(acad._JANELA_MAX, max(1, len(st['acervo']) // 2))

    def test_nao_repete_dentro_da_janela(self):
        """A promessa que o guarda cumpre: o enunciado não volta enquanto estiver na janela.

        Já tentei prometer "nada repete até esgotar o acervo". É impossível com sorteio
        aleatório: fechar a rodada é o problema do colecionador de figurinhas e o último item
        quase nunca sai. Medido na época: acervo de 20 dava 572 repetições indevidas em 300
        sessões, mesmo com 20 re-sorteios. Esta é a garantia que a distribuição permite.
        """
        for acervo in (2, 3, 5, 7, 12, 20, 50):
            chave = (1, f'gerador_falso_{acervo}')
            violacoes = 0
            for seed in range(40):
                random.seed(seed)
                acad._recentes.clear()
                fn = acad._sem_repetir(self._gerador_de_acervo(acervo))
                seq = []
                for _ in range(acervo * 4 + 12):
                    larg = self._largura_vigente(chave)
                    q = fn(user_id=1)['question']
                    if q in seq[-larg:]:
                        violacoes += 1
                    seq.append(q)
            self.assertEqual(violacoes, 0, f'acervo {acervo}: {violacoes} repetições na janela')
        print("  ✔ guarda: zero repetições dentro da janela, de acervo 2 a 50")

    def test_a_janela_se_abre_conforme_o_acervo_aparece(self):
        """Se a janela não crescesse, um acervo grande seria protegido como se fosse pequeno e o
        jogador voltaria a ver repetição perto. Ela é aprendida, não declarada.

        Mede a DISTÂNCIA observada entre duas aparições do mesmo enunciado, e não a fórmula:
        a primeira versão deste teste recalculava `min(_JANELA_MAX, len(acervo)//2)` por conta
        própria e continuava verde com a janela do código travada em 1. Não podia falhar.
        """
        distancias = {}
        for acervo in (2, 6, 20):
            random.seed(1)
            acad._recentes.clear()
            fn = acad._sem_repetir(self._gerador_de_acervo(acervo))
            seq = [fn(user_id=1)['question'] for _ in range(acervo * 10)]
            seq = seq[acervo * 3:]              # descarta o aquecimento: a janela ainda crescia
            ultimo, menor = {}, 10 ** 6
            for i, q in enumerate(seq):
                if q in ultimo:
                    menor = min(menor, i - ultimo[q])
                ultimo[q] = i
            distancias[acervo] = menor
        self.assertLess(distancias[2], distancias[6],
                        f'acervo maior não afastou as repetições: {distancias}')
        self.assertLess(distancias[6], distancias[20],
                        f'acervo maior não afastou as repetições: {distancias}')
        print(f"  ✔ guarda: distância entre repetições cresce com o acervo {distancias}")

    def test_acervo_de_um_item_nao_trava_nem_falha(self):
        """Fail-open. Um gerador de resposta única existe e não pode derrubar o treino nem entrar
        em laço: com um item só, repetir é a ÚNICA saída honesta."""
        acad._recentes.clear()
        fn = acad._sem_repetir(self._gerador_de_acervo(1))
        for _ in range(10):
            self.assertEqual(fn(user_id=1)['question'], 'pergunta 0')
        print("  ✔ guarda: acervo de 1 item serve sempre, sem travar")

    def test_jogadores_diferentes_nao_disputam_a_mesma_rodada(self):
        """A rodada é por (jogador, tema). Se fosse global, um jogador esconderia exercícios do
        outro — e em produção isso escala com o número de gente online."""
        random.seed(4)
        acad._recentes.clear()
        fn = acad._sem_repetir(self._gerador_de_acervo(3))
        for _ in range(3):
            fn(user_id=1)
        vistos_b = {fn(user_id=2)['question'] for _ in range(3)}
        self.assertEqual(len(vistos_b), 3,
                         'o jogador 2 recebeu menos que o acervo inteiro: a rodada vazou entre users')
        print("  ✔ guarda: rodada é por jogador")

    def test_a_memoria_do_guarda_nao_cresce_sem_limite(self):
        """Estado em memória de processo, em produção com muitos usuários. Sem teto vira
        vazamento lento, que é o tipo de falha que só aparece semanas depois."""
        acad._recentes.clear()
        fn = acad._sem_repetir(self._gerador_de_acervo(3))
        for uid in range(acad._TETO_MEMORIA + 500):
            fn(user_id=uid)
        self.assertLessEqual(len(acad._recentes), acad._TETO_MEMORIA)
        print(f"  ✔ guarda: memória travada em {len(acad._recentes)} chaves")

    def test_todo_gerador_publico_passa_pelo_guarda(self):
        """Mesma razão do embaralhamento: são 22 geradores e um esquecido mantém o defeito
        justamente onde ninguém olha. A varredura cobra o N+1."""
        faltando = []
        for nome, fn in vars(acad).items():
            if nome.startswith('generate_') and nome.endswith('_question') and callable(fn):
                alvo, marcado = fn, False
                while alvo is not None:              # percorre a cadeia de wrappers
                    marcado = marcado or getattr(alvo, '_guarda_repeticao', False)
                    alvo = getattr(alvo, '__wrapped__', None)
                if not marcado:
                    faltando.append(nome)
        self.assertEqual(faltando, [], f'geradores fora do guarda de repetição: {faltando}')
        self.assertGreater(sum(1 for n in vars(acad) if n.startswith('generate_')
                               and n.endswith('_question')), 15,
                           'a varredura não encontrou geradores — o teste passaria vazio')
        print("  ✔ guarda: todos os geradores públicos embrulhados")



if __name__ == '__main__':
    print("Academia LeakLab — Teste de Variedade de Exercícios")
    print("="*60)
    run_tests()
