# -*- coding: utf-8 -*-
"""O reparo separa os registros misturados SEM perder o que aponta nas decisoes (13/09).

── O que o reparo conserta ────────────────────────────────────────────────────────────────────

42 registros do acervo guardavam maos de 224 torneios, e 179 desses torneios nao existiam em
lugar nenhum: estavam dentro de um registro com o nome de outro. O deploy de 56c7623c parou de
criar casos novos; `scripts/repara_arquivo_multi_torneio.py` conserta o que ficou.

── O que este arquivo defende, e por que cada coisa ───────────────────────────────────────────

1. **Mover, nunca reimportar.** 187 drill_sessions e 1.320 vereditos_por_semelhanca apontam para
   `decisions.id` nos 42 registros. Apagar e reimportar levaria tudo por CASCADE — dano que o
   defeito nao causava (regra 7). O teste central forja um drill e um veredito sobre uma decisao
   que MUDA de torneio e exige que os dois continuem la depois.
2. **Cada decisao vai para o torneio da PROPRIA mao.** E o erro que o defeito produzia, e seria
   facil reproduzi-lo movendo por posicao em vez de por `hand_id`.
3. **`imported_at` herdado**, porque o torneio nao foi importado hoje e o eixo de tempo depende
   disso; e a cota (`tournaments_this_month`) nao pode se mexer, senao o reparo cobraria do
   jogador uma importacao que ele nao fez.
4. **O dry-run nao escreve NADA.** Provado comparando o estado do banco antes e depois.
5. **`--apply` sem `--dump` nao roda.** Escrita sem registro para desfazer e o que transforma um
   conserto em acidente.
6. **O reverter volta ao estado anterior**, conferido campo a campo.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                                  # noqa: E402
from database.repositories import _adapt                                       # noqa: E402
from database.rowutil import value                                             # noqa: E402

init_db()

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')
_SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'scripts',
                       'repara_arquivo_multi_torneio.py')
UID = 7301


def _texto_de_tres_torneios():
    """O fixture real, com as maos redistribuidas em 3 Tournament # diferentes.

    Do fixture e nao inventado: mao forjada a mao nao passa pelo parser, e um cenario que nao
    passa pelo parser nao prova que o reparo funciona no dialeto de verdade.
    """
    import re
    raw = io.open(os.path.join(_FIX, 'revalidation_mini.txt'), encoding='utf-8').read()
    blocos = [b for b in re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]
    assert len(blocos) == 5, len(blocos)
    novos = ['555000001', '555000001', '555000002', '555000002', '555000003']
    return ''.join(re.sub(r'Tournament #(\d+)', 'Tournament #' + n, b)
                   for b, n in zip(blocos, novos))


def _monta():
    """Um registro misturado, com decisoes reais e um drill e um veredito pendurados.

    Tudo dentro de try/finally: o script roda em SUBPROCESSO, e uma conexao aberta aqui deixa o
    SQLite travado — a primeira versao deste arquivo falhou num insert e as outras 8 morreram
    todas com "database is locked", escondendo o erro de verdade.
    """
    from leaklab.parser import parse_pokerstars_file_from_text
    texto = _texto_de_tres_torneios()
    maos = parse_pokerstars_file_from_text(texto)
    conn = get_conn()
    try:
        return _monta_com(conn, maos, texto)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _monta_com(conn, maos, texto):
    conn.execute(_adapt("DELETE FROM tournaments WHERE user_id=?"), (UID,))
    conn.execute(_adapt("DELETE FROM users WHERE id=?"), (UID,))
    conn.execute(_adapt(
        "INSERT INTO users (id, username, email, password_hash, plan, tournaments_this_month) "
        "VALUES (?,?,?,?,?,?)"), (UID, 'rep', 'rep@e.st', 'h', 'pro', 7))
    conn.execute(_adapt(
        "INSERT INTO tournaments (id, user_id, tournament_id, site, tournament_name, hero, "
        "played_at, imported_at, hands_count, decisions_count, raw_text, place, prize) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"),
        (7301, UID, '555000001', 'pokerstars', 'Noite', 'HeroPlayer',
         '2026-09-01', '2026-09-02 03:04:05', 5, 0, texto, 12, 3.5))
    # uma decisao por mao, com o hand_id real
    for m in maos:
        conn.execute(_adapt(
            "INSERT INTO decisions (tournament_id, hand_id, street, position, action_taken, "
            "best_action, label, score) VALUES (?,?,?,?,?,?,?,?)"),
            (7301, str(getattr(m, 'hand_id', '') or ''), 'preflop', 'BTN', 'raise',
             'raise', 'standard', 0.8))
    conn.commit()
    # a decisao da ULTIMA mao vai mudar de torneio (ela e do 555000003)
    alvo_hand = str(getattr(maos[-1], 'hand_id', '') or '')
    dec_id = value(conn.execute(_adapt(
        "SELECT id FROM decisions WHERE tournament_id=? AND hand_id=?"),
        (7301, alvo_hand)).fetchone(), 'id')
    conn.execute(_adapt(
        "INSERT INTO drill_sessions (user_id, decision_id, new_action, new_score, "
        "original_score, delta, correct) VALUES (?,?,?,?,?,?,?)"),
        (UID, dec_id, 'raise', 0.9, 0.8, 0.1, 1))
    # `vereditos_por_semelhanca` guarda decision_id E tournament_id: a segunda coluna tem de
    # acompanhar a decisao quando ela muda de torneio, senao a linha aponta para o torneio de
    # onde a decisao SAIU. Achado varrendo as 8 tabelas com `tournament_id`, nao por teste.
    conn.execute(_adapt(
        "INSERT INTO vereditos_por_semelhanca (decision_id, tournament_id, assinatura, "
        "vizinhos, acao, freq_jogada, rotulo) VALUES (?,?,?,?,?,?,?)"),
        (dec_id, 7301, 'ass-x', 4, 'raise', 0.7, 'standard'))
    conn.commit()
    return dec_id, alvo_hand


def _roda(*args):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['LEAKLAB_DB'] = _TMPDB.name
    env.pop('DATABASE_URL', None)
    r = subprocess.run([sys.executable, _SCRIPT] + list(args),
                       capture_output=True, text=True, env=env,
                       cwd=os.path.join(os.path.dirname(__file__), '..'),
                       encoding='utf-8', errors='replace')
    return r


def _estado():
    conn = get_conn()
    ts = [dict(x) for x in conn.execute(_adapt(
        "SELECT id, tournament_id, hands_count, decisions_count, place, prize, imported_at "
        "FROM tournaments WHERE user_id=? ORDER BY id"), (UID,)).fetchall()]
    ds = [dict(x) for x in conn.execute(_adapt(
        "SELECT d.id, d.hand_id, d.tournament_id FROM decisions d "
        "JOIN tournaments t ON t.id=d.tournament_id WHERE t.user_id=? ORDER BY d.id"),
        (UID,)).fetchall()]
    cota = value(conn.execute(_adapt(
        "SELECT tournaments_this_month AS n FROM users WHERE id=?"), (UID,)).fetchone(), 'n')
    conn.close()
    return ts, ds, cota


def test_o_dry_run_NAO_escreve_nada():
    """CONTROLE que vale por todos os outros: se o dry-run escrevesse, cada teste abaixo estaria
    medindo um banco ja mexido."""
    _monta()
    antes = _estado()
    r = _roda('--user', str(UID))
    assert r.returncode == 0, r.stderr[-600:]
    assert 'dry-run' in r.stdout, r.stdout[-400:]
    assert _estado() == antes, 'o dry-run mexeu no banco'


def test_o_dry_run_ACHA_os_tres_torneios():
    _monta()
    r = _roda('--user', str(UID))
    assert '555000002' in r.stdout and '555000003' in r.stdout, r.stdout[-600:]
    # o que FICA e o gravado, mesmo sendo empatado em maos
    assert 'FICA no registro: 555000001' in r.stdout, r.stdout[-600:]
    assert 'registros novos a criar: 2' in r.stdout, r.stdout[-400:]


def test_apply_SEM_dump_nao_roda():
    """Escrita sem registro para desfazer e o que transforma conserto em acidente."""
    _monta()
    antes = _estado()
    r = _roda('--user', str(UID), '--apply')
    assert r.returncode != 0, 'rodou sem dump'
    assert '--dump' in (r.stdout + r.stderr)
    assert _estado() == antes, 'escreveu mesmo recusando'


def test_o_reparo_SEPARA_e_cada_decisao_vai_para_a_MAO_dela():
    _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    r = _roda('--user', str(UID), '--apply', '--dump', dump.name)
    assert r.returncode == 0, r.stderr[-800:]
    ts, ds, _ = _estado()
    assert len(ts) == 3, ('deveriam existir 3 registros', [t['tournament_id'] for t in ts])
    por_tid = {t['tournament_id']: t for t in ts}
    assert set(por_tid) == {'555000001', '555000002', '555000003'}, list(por_tid)
    assert por_tid['555000001']['hands_count'] == 2, por_tid['555000001']
    assert por_tid['555000002']['hands_count'] == 2, por_tid['555000002']
    assert por_tid['555000003']['hands_count'] == 1, por_tid['555000003']
    # nenhuma decisao se perdeu, e cada uma esta no torneio da PROPRIA mao
    assert len(ds) == 5, len(ds)
    from leaklab.parser import parse_pokerstars_file_from_text
    maos = parse_pokerstars_file_from_text(_texto_de_tres_torneios())
    esperado = {str(getattr(m, 'hand_id', '')): str(getattr(m, 'tournament_id', ''))
                for m in maos}
    id_para_tid = {t['id']: t['tournament_id'] for t in ts}
    for d in ds:
        assert id_para_tid[d['tournament_id']] == esperado[str(d['hand_id'])], (
            'decisao da mao %s foi para o torneio errado' % d['hand_id'])


def test_o_que_APONTA_na_decisao_sobrevive():
    """A razao de mover em vez de reimportar. 187 drills e 1.320 vereditos estao em jogo no
    acervo real; reimportar levaria todos por CASCADE."""
    dec_id, _ = _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    r = _roda('--user', str(UID), '--apply', '--dump', dump.name)
    assert r.returncode == 0, r.stderr[-800:]
    conn = get_conn()
    n_drill = value(conn.execute(_adapt(
        "SELECT COUNT(*) AS n FROM drill_sessions WHERE decision_id=?"), (dec_id,)).fetchone(), 'n')
    n_ver = value(conn.execute(_adapt(
        "SELECT COUNT(*) AS n FROM vereditos_por_semelhanca WHERE decision_id=?"),
        (dec_id,)).fetchone(), 'n')
    # e a decisao REALMENTE mudou de torneio (senao o teste passa sem provar nada)
    novo_t = value(conn.execute(_adapt(
        "SELECT tournament_id AS t FROM decisions WHERE id=?"), (dec_id,)).fetchone(), 't')
    conn.close()
    assert novo_t != 7301, 'a decisao nao mudou de torneio: o teste nao prova sobrevivencia'
    assert n_drill == 1, 'o drill_session foi perdido (CASCADE?)'
    assert n_ver == 1, 'o veredito por semelhanca foi perdido (CASCADE?)'


def test_quem_guarda_os_DOIS_campos_acompanha_a_decisao():
    """`vereditos_por_semelhanca` e `coach_hand_annotations` tem decision_id E tournament_id.

    Mover a decisao sem atualizar a segunda coluna deixa a linha apontando para o torneio de onde
    a decisao SAIU. O defeito original nao criava essa inconsistencia — ela seria do conserto
    (regra 7). Achei varrendo as 8 tabelas com coluna `tournament_id`, nao por teste; por isso o
    guarda existe.
    """
    dec_id, _ = _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    conn = get_conn()
    t_dec = value(conn.execute(_adapt(
        "SELECT tournament_id AS t FROM decisions WHERE id=?"), (dec_id,)).fetchone(), 't')
    t_ver = value(conn.execute(_adapt(
        "SELECT tournament_id AS t FROM vereditos_por_semelhanca WHERE decision_id=?"),
        (dec_id,)).fetchone(), 't')
    conn.close()
    assert t_dec != 7301, 'a decisao nao mudou de torneio: o teste nao prova nada'
    assert t_ver == t_dec, (
        'o veredito por semelhanca ficou no torneio antigo (%s) enquanto a decisao foi para %s'
        % (t_ver, t_dec))


def test_imported_at_herdado_e_cota_intacta():
    _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    ts, _, cota = _estado()
    datas = {str(t['imported_at'])[:19] for t in ts}
    assert datas == {'2026-09-02 03:04:05'}, (
        'os registros novos nao herdaram o imported_at do original: %s' % datas)
    assert cota == 7, ('a cota se mexeu: o reparo cobrou uma importacao que o jogador nao fez '
                       '(%s)' % cota)


def test_o_resultado_vai_para_o_torneio_de_QUEM_TERMINOU_ali():
    """O place/prize do registro misturado e de UM dos torneios. Re-extrair por grupo e o unico
    jeito de ele parar no certo — no acervo real, 21 de 24 estao hoje no torneio errado."""
    _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    ts, _, _ = _estado()
    # o fixture nao declara resultado para nenhum dos tres, entao NINGUEM pode herdar o place=12
    # que estava gravado no registro misturado. Herdar seria propagar o dado errado para 3.
    com_place = [t['tournament_id'] for t in ts if t['place']]
    assert com_place == [], (
        'place do registro misturado foi propagado para %s; ele era de um torneio so e o texto '
        'nao diz qual' % com_place)


def test_o_reverter_volta_ao_estado_anterior():
    _monta()
    antes = _estado()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    assert _estado() != antes, 'o apply nao mudou nada: o reverter nao prova nada'
    r = _roda('--reverter', dump.name)
    assert r.returncode == 0, r.stderr[-600:]
    depois = _estado()
    ts_a, ds_a, _ = antes
    ts_d, ds_d, _ = depois
    assert len(ts_d) == 1, ('sobrou registro criado: %s' % [t['tournament_id'] for t in ts_d])
    assert ts_d[0]['hands_count'] == ts_a[0]['hands_count'], (ts_d[0], ts_a[0])
    assert ts_d[0]['place'] == ts_a[0]['place'], (ts_d[0]['place'], ts_a[0]['place'])
    assert {d['id']: d['tournament_id'] for d in ds_d} == \
           {d['id']: d['tournament_id'] for d in ds_a}, 'decisoes nao voltaram ao torneio de origem'


def test_o_dump_registra_TODA_decisao_movida():
    """Registro para desfazer que nao cobre uma escrita e pior que registro nenhum, porque
    parece completo."""
    _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    linhas = [json.loads(l) for l in io.open(dump.name, encoding='utf-8') if l.strip()]
    movidas = [l for l in linhas if l['tipo'] == 'decision_movida']
    criados = [l for l in linhas if l['tipo'] == 'tournament_criado']
    antes = [l for l in linhas if l['tipo'] == 'tournament_antes']
    assert len(criados) == 2, len(criados)
    assert len(antes) == 1, len(antes)
    # 3 decisoes mudaram de torneio (2 do 555000002 + 1 do 555000003)
    assert len(movidas) == 3, ('o dump registrou %d movimentacoes, esperado 3' % len(movidas))
    assert all(l.get('de') and l.get('para') for l in movidas), movidas[:2]


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
