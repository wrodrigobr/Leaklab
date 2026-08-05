# -*- coding: utf-8 -*-
"""O pote limpado tem que SOBREVIVER ao banco, e o BB nao tem range de abertura.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Sobraram 46 decisoes preflop com null MUDO no acervo de producao (sem `available` e sem
`coverage_reason`). Todas sao a MESMA coisa: BB, `facing_bet = 0`, zero raises, agredindo —
26 raise e 19 shove, mais 1 fold. Isso e iso-raise sobre limpers.

Duas causas empilhadas, e a de cima escondia a de baixo:

1. **O `facing_limp` morria no banco.** O pipeline calcula na hora do parse e o `/analyze` passa
   pro provider, mas nao havia coluna. O `sync_gto_labels_from_ranges`, que reconstroi o veredito
   a partir da LINHA depois de todo DELETE+INSERT do `save_decisions`, nao tinha como saber.
   Sem isso, 46 de 46 mudas.

2. **O atalho `limp_dead_money` mandava o BB procurar range de RFI.** A stacks <=12bb o codigo
   trata jam/fold sobre limp como a mesma decisao de abrir ("o limp e dead money"). Para o BB
   isso e falso duas vezes: ele nunca e first-in (conferido: os 9 buckets tem UTG..SB, nenhum BB)
   e ele ja tem 1bb dentro FECHANDO a acao — nao e abertura, e defesa da propria big blind. O
   lookup nao achava nada e a funcao escorria ate o fim sem `coverage_reason`. Eram 11 das 46.

Medido: com `facing_limp` chegando, 35 das 46 passam a ser nomeadas; com a guarda do BB, as 11
restantes tambem. **Nenhuma ganha gabarito** — pote limpado esta fora da arvore raise-first em
qualquer fonte, e fabricar um veredito aqui seria pior que o null.

── Por que `facing_bet = 0` nao substitui a coluna ────────────────────────────────────────────

Para o BB da pra deduzir (se todos tivessem foldado, a mao acabava sem decisao dele). Fora do BB
nao: `facing_bet = 0` no CO tanto vale para "limparam na minha frente" quanto para "foldaram
todos", e o segundo e RFI, com gabarito. Deduzir cobriria o caso de hoje e mentiria no de amanha.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop, _load


def _bb(acao, eff=10.0, limp=True, mao='A5o'):
    return analyze_preflop(position='BB', hero_hand_type=mao, stack_bb=eff, action_taken=acao,
                           facing_size=0.0, vs_position='', is_3bet_pot=False, facing_raises=0,
                           hero_was_aggressor=False, facing_to_bb=0.0, facing_limp=limp)


def test_bb_nao_tem_range_de_abertura_em_bucket_nenhum():
    """O fato que sustenta a guarda. Se um dia o BB ganhar RFI, este teste avisa que a guarda
    virou obsoleta em vez de deixar ela silenciosamente errada."""
    d = _load().get('ranges', {})
    assert d, 'ranges nao carregaram'
    for bk, dados in d.items():
        assert 'BB' not in (dados.get('RFI') or {}), (
            f'bucket {bk} passou a ter RFI de BB — a guarda do atalho limp_dead_money precisa '
            f'ser revista, nao apagada sem pensar')


def test_bb_agredindo_sobre_limp_nao_volta_mudo():
    """As 46. Nenhuma ganha gabarito, todas ganham motivo."""
    for acao, eff in (('raise', 25.0), ('raise', 8.0), ('shove', 10.0), ('shove', 30.0),
                      ('jam', 6.0), ('fold', 9.0)):
        r = _bb(acao, eff)
        assert r.get('available') is False, f'BB {acao} @{eff}bb sobre limp nao pode ter gabarito'
        assert r.get('coverage_reason') == 'limped_pot', (
            f'BB {acao} @{eff}bb voltou MUDO (motivo={r.get("coverage_reason")!r})')


def test_o_atalho_de_stack_curto_segue_valendo_fora_do_BB():
    """Controle negativo: a guarda e do BB, nao de todo mundo. Se ela vazar, o SB perde a
    aproximacao de push/fold que o projeto decidiu manter."""
    r = analyze_preflop(position='SB', hero_hand_type='A9o', stack_bb=9.0, action_taken='shove',
                        facing_size=0.0, vs_position='', is_3bet_pot=False, facing_raises=0,
                        hero_was_aggressor=False, facing_to_bb=0.0, facing_limp=True)
    assert r.get('available') is True, 'SB perdeu a aproximacao push/fold sobre limp'
    assert r.get('limp_dead_money') is True


def test_facing_limp_sobrevive_ao_banco():
    """A causa nº1, e a unica que um teste de funcao pura NAO pegaria: o dado existia em memoria
    e morria na gravacao. Grava com `facingLimp` e le de volta da coluna."""
    import tempfile
    import database.schema as sch
    import database.repositories as repo

    # Banco proprio: `save_decisions` faz DELETE+INSERT por torneio e nao pode encostar no
    # banco de dev de quem roda o teste.
    sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    get_conn, save_decisions = sch.get_conn, repo.save_decisions
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (id, username, email, password_hash) "
                 "VALUES (1, 'u_limp', 'limp@t.st', 'x')")
    conn.execute("INSERT OR IGNORE INTO tournaments (id, user_id, tournament_id, hero) "
                 "VALUES (901, 1, 'T-LIMP', 'Hero')")
    conn.commit()
    conn.close()

    def _dec(hand_id, limp):
        return {
            'handId': hand_id, 'street': 'preflop', 'hero_cards': 'AsKs', 'board': '',
            'action_taken': 'raise', 'evaluation': {'label': 'standard', 'score': 5.0,
                                                    'bestAction': 'raise'},
            'spot': {'position': 'BB', 'facingLimp': limp, 'heroStackBb': 20.0},
        }

    save_decisions(901, [_dec('H-LIMP', True), _dec('H-SEM', False)])

    conn = get_conn()
    lidas = {dict(r)['h']: dict(r)['fl'] for r in conn.execute(
        "SELECT hand_id AS h, facing_limp AS fl FROM decisions WHERE tournament_id = 901"
    ).fetchall()}
    conn.close()

    assert lidas.get('H-LIMP') in (1, True), (
        f'o pote limpado NAO sobreviveu a gravacao: {lidas!r} — e exatamente aqui que o dado '
        f'morria, e nenhum teste de funcao pura pega isso')
    assert lidas.get('H-SEM') in (0, False), f'pote nao-limpado gravado como limpado: {lidas!r}'


def test_o_sync_le_e_repassa_a_coluna():
    """Guarda de FIAÇÃO: ter a coluna nao adianta se quem reconstroi o veredito nao a consulta.

    Ja aconteceu nesta base — `spot_hash` era gravado pelo backfill e nunca pelo caminho vivo.
    """
    caminho = os.path.join(os.path.dirname(__file__), '..', 'scripts',
                           'sync_gto_labels_from_ranges.py')
    src = open(caminho, encoding='utf-8').read()
    assert 'facing_limp=bool(r.get("facing_limp"))' in src, (
        'o sync voltou a chamar o provider sem facing_limp — os nulls voltam a ser MUDOS')
    assert src.count('facing_limp FROM decisions') + src.count('effective_stack_bb, facing_limp') >= 2, (
        'algum dos SELECTs do sync parou de trazer a coluna; o argumento acima viraria sempre False')


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
