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
    # A limpeza e explicita porque o SQLite nao aplica FK por padrao (`PRAGMA foreign_keys` vem
    # OFF): apagar o torneio NAO leva a fila embora, e a segunda execucao batia no UNIQUE de
    # (tournament_id, spot_hash) — 10 dos 11 testes morreram com esse erro antes de eu ver.
    conn.execute(_adapt("DELETE FROM gto_tournament_queue WHERE tournament_id=?"), (7301,))
    for t in [dict(x)['id'] for x in conn.execute(_adapt(
            "SELECT id FROM tournaments WHERE user_id=?"), (UID,)).fetchall()]:
        conn.execute(_adapt("DELETE FROM gto_tournament_queue WHERE tournament_id=?"), (t,))
        conn.execute(_adapt("DELETE FROM decisions WHERE tournament_id=?"), (t,))
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
            "best_action, label, score, spot_hash) VALUES (?,?,?,?,?,?,?,?,?)"),
            (7301, str(getattr(m, 'hand_id', '') or ''), 'preflop', 'BTN', 'raise',
             'raise', 'standard', 0.8, 'spot-' + str(getattr(m, 'hand_id', '') or '')))
    conn.commit()
    # A fila do solver: um vinculo (torneio, spot) por decisao. Sem povoar isto, o guarda do
    # re-vinculo passaria por vacuidade — nao havia nada para re-vincular.
    for m in maos:
        conn.execute(_adapt(
            "INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (?,?)"),
            (7301, 'spot-' + str(getattr(m, 'hand_id', '') or '')))
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


def test_o_MESMO_torneio_em_DOIS_registros_faz_MERGE_e_nao_colide():
    """Achado no ENSAIO com a copia do pagante, e ele quebrou o script com UniqueViolation.

    O mesmo `tournament_id` pode estar dentro de dois registros misturados diferentes: no acervo
    do michel, 6 de 239 torneios (t551 e t1177 compartilham o T#4028679584). O planejamento roda
    todo ANTES da primeira escrita, entao nao ve o registro que outro plano vai criar, e o
    segundo INSERT batia no UNIQUE (user_id, tournament_id).

    Luigi e a conta do dono nao expuseram isso, porque neles cada torneio estava num registro so
    — e os dois reparos ja rodaram em producao sem tocar neste caminho. Foi a COPIA que pegou.

    O certo e MERGE: as decisoes do segundo grupo vao para o registro que abriga aquele torneio,
    que e o que o upload faz quando um T# reaparece noutro arquivo.
    """
    import re as _re
    from leaklab.parser import parse_pokerstars_file_from_text
    raw = io.open(os.path.join(_FIX, 'revalidation_mini.txt'), encoding='utf-8').read()
    blocos = [b for b in _re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]

    def com(ids, desloca):
        """Blocos com `Tournament #` reescrito e `hand_id` deslocado (senao o merge deduplica)."""
        saida = []
        for b, t in zip(blocos, ids):
            b = _re.sub(r'Tournament #(\d+)', 'Tournament #' + t, b)
            b = _re.sub(r'PokerStars Hand #(\d+)',
                        lambda m: 'PokerStars Hand #%d' % (int(m.group(1)) + desloca), b)
            saida.append(b)
        return ''.join(saida)

    # DOIS registros, e o torneio 666000002 esta nos dois
    texto_a = com(['666000001', '666000001', '666000002', '666000002', '666000002'], 0)
    texto_b = com(['666000003', '666000003', '666000003', '666000002', '666000002'], 900000)

    conn = get_conn()
    conn.execute(_adapt("DELETE FROM gto_tournament_queue WHERE tournament_id IN (7401,7402)"))
    for t in (7401, 7402):
        conn.execute(_adapt("DELETE FROM decisions WHERE tournament_id=?"), (t,))
    conn.execute(_adapt("DELETE FROM tournaments WHERE user_id=?"), (UID,))
    conn.execute(_adapt("DELETE FROM users WHERE id=?"), (UID,))
    conn.execute(_adapt(
        "INSERT INTO users (id, username, email, password_hash, plan) VALUES (?,?,?,?,?)"),
        (UID, 'dup', 'dup@e.st', 'h', 'pro'))
    for tid, gravado, texto in ((7401, '666000001', texto_a), (7402, '666000003', texto_b)):
        conn.execute(_adapt(
            "INSERT INTO tournaments (id, user_id, tournament_id, site, tournament_name, hero, "
            "played_at, imported_at, hands_count, decisions_count, raw_text) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)"),
            (tid, UID, gravado, 'pokerstars', 'N', 'HeroPlayer', '2026-09-01',
             '2026-09-02 03:04:05', 5, 0, texto))
        for m in parse_pokerstars_file_from_text(texto):
            conn.execute(_adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, action_taken, "
                "best_action, label, score, spot_hash) VALUES (?,?,?,?,?,?,?,?,?)"),
                (tid, str(getattr(m, 'hand_id', '') or ''), 'preflop', 'BTN', 'raise',
                 'raise', 'standard', 0.8, 'sp-' + str(getattr(m, 'hand_id', '') or '')))
    conn.commit(); conn.close()

    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    r = _roda('--user', str(UID), '--apply', '--dump', dump.name)
    assert r.returncode == 0, ('o reparo falhou: %s' % (r.stderr or r.stdout)[-500:])

    conn = get_conn()
    por_tid = {}
    for x in conn.execute(_adapt(
            "SELECT id, tournament_id, hands_count FROM tournaments WHERE user_id=?"),
            (UID,)).fetchall():
        xx = dict(x)
        por_tid.setdefault(str(xx['tournament_id']), []).append(xx['id'])
    # e as decisoes do torneio compartilhado, todas no MESMO registro
    regs_do_compartilhado = {dict(x)['t'] for x in conn.execute(_adapt(
        "SELECT DISTINCT d.tournament_id AS t FROM decisions d JOIN tournaments x "
        "ON x.id=d.tournament_id WHERE x.user_id=? AND x.tournament_id=?"),
        (UID, '666000002')).fetchall()}
    conn.close()

    assert por_tid.get('666000002') and len(por_tid['666000002']) == 1, (
        'o torneio compartilhado gerou %s registro(s); deveria gerar UM' % len(
            por_tid.get('666000002') or []))
    assert len(regs_do_compartilhado) == 1, (
        'as decisoes do torneio compartilhado ficaram espalhadas em %d registros'
        % len(regs_do_compartilhado))
    # nenhuma decisao se perdeu: 10 no cenario (5 + 5)
    conn = get_conn()
    total = value(conn.execute(_adapt(
        "SELECT COUNT(*) AS n FROM decisions d JOIN tournaments t ON t.id=d.tournament_id "
        "WHERE t.user_id=?"), (UID,)).fetchone(), 'n')
    conn.close()
    assert total == 10, ('decisoes no fim: %s, esperado 10' % total)


def test_o_reparo_NAO_MUDA_VEREDITO_de_decisao_nenhuma():
    """A invariante mais importante deste script, e ela nasceu de uma violacao MEDIDA.

    No ensaio com a copia do unico pagante, o reparo mudou **115 decisoes de banda** (67
    small_mistake -> marginal, 48 no inverso) e reescreveu o `score` de todas, com o `gto_label`
    intacto em 100% delas. Causa: ele chamava `reconcile_tournament_labels` para obter os
    agregados, e o reconcile reavalia label e score por LINHA antes de resumir — era a politica
    atual sendo aplicada a linhas antigas (AY-42).

    Separar registros nao pode mudar veredito que o jogador ve. O reparo passou a chamar so
    `recalcula_agregados_do_torneio`.

    Este guarda compara label e score de CADA decisao, antes e depois, e nao os totais: no ensaio
    os totais mostravam 19 de diferenca (2212 -> 2231) enquanto 115 linhas tinham mudado — as
    trocas em sentidos opostos se cancelavam. Total igual nao prova linha igual.
    """
    _monta()
    conn = get_conn()
    antes = {dict(r)['id']: (str(dict(r)['label']), float(dict(r)['score'] or 0))
             for r in conn.execute(_adapt(
                 "SELECT d.id, d.label, d.score FROM decisions d JOIN tournaments t "
                 "ON t.id=d.tournament_id WHERE t.user_id=?"), (UID,)).fetchall()}
    conn.close()
    assert len(antes) == 5, len(antes)

    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0

    conn = get_conn()
    depois = {dict(r)['id']: (str(dict(r)['label']), float(dict(r)['score'] or 0))
              for r in conn.execute(_adapt(
                  "SELECT d.id, d.label, d.score FROM decisions d JOIN tournaments t "
                  "ON t.id=d.tournament_id WHERE t.user_id=?"), (UID,)).fetchall()}
    conn.close()

    assert set(antes) == set(depois), (
        'decisoes apareceram ou desapareceram: %d antes, %d depois' % (len(antes), len(depois)))
    trocaram = [i for i in antes if antes[i] != depois[i]]
    assert trocaram == [], (
        '%d decisao(oes) mudaram de veredito ou score: %s' % (
            len(trocaram), [(i, antes[i], depois[i]) for i in trocaram[:5]]))


def test_os_registros_novos_ganham_agregados_RECALCULADOS():
    """O outro lado da moeda do guarda anterior: nao reconciliar nao pode virar nao resumir.

    Quebrei de proposito removendo a chamada de `recalcula_agregados_do_torneio` e os 17 casos
    passaram verdes — o guarda de fiacao ve a string no import mesmo sem a chamada, e o de
    veredito nao olha agregado. Registro novo sem `avg_score`/`standard_pct` aparece na lista
    com celula vazia, e no cenario deste arquivo todas as decisoes sao `standard` com score 0.8,
    entao os tres registros tem de sair com 100% e 0.8.
    """
    _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    conn = get_conn()
    linhas = [dict(r) for r in conn.execute(_adapt(
        "SELECT tournament_id, avg_score, standard_pct, decisions_count FROM tournaments "
        "WHERE user_id=? ORDER BY id"), (UID,)).fetchall()]
    conn.close()
    assert len(linhas) == 3, len(linhas)
    for l in linhas:
        assert l['avg_score'] is not None, (
            '%s ficou sem avg_score: os agregados nao foram recalculados' % l['tournament_id'])
        assert abs(float(l['avg_score']) - 0.8) < 1e-6, (l['tournament_id'], l['avg_score'])
        assert l['standard_pct'] is not None and abs(float(l['standard_pct']) - 100.0) < 1e-6, (
            l['tournament_id'], l['standard_pct'])


def test_o_reparo_NAO_chama_o_reconcile_de_labels():
    """CONDICAO, porque o teste de comportamento acima nao tem material para distinguir.

    Quebrei de proposito: troquei `recalcula_agregados_do_torneio` de volta por
    `reconcile_tournament_labels` e os 16 casos passaram VERDES. Motivo: as decisoes forjadas no
    cenario nao tem `gto_label`, entao o reconcile nao mexe em nada e a diferenca desaparece. A
    violacao real foi MEDIDA no ensaio com a copia do pagante (115 linhas), nao aqui.

    Entao este guarda olha a CONDICAO: o script recalcula os agregados e nao reconcilia. Guarda
    de fiacao e fraco por natureza, e nao seria suficiente sozinho — ele existe porque o de
    comportamento, neste cenario, e cego.
    """
    src = io.open(_SCRIPT, encoding='utf-8').read()
    codigo = chr(10).join(l.split('#', 1)[0] for l in src.splitlines())
    assert 'recalcula_agregados_do_torneio' in codigo, (
        'o reparo parou de recalcular os agregados: os registros ficam com avg_score e os *_pct '
        'do conjunto antigo')
    assert 'reconcile_tournament_labels' not in codigo, (
        'o reparo voltou a chamar o reconcile inteiro, que REAVALIA label e score por linha — '
        'no ensaio com a copia do pagante isso mudou 115 vereditos')


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


def test_hands_count_usa_a_regua_do_UPLOAD_e_nao_o_texto():
    """`hands_count` conta maos ANALISADAS (com decisao), nao maos do arquivo.

    Medido com upload real das 5 salas contra o Postgres: `hands_count` == maos distintas com
    decisao em 5 de 5. A primeira versao deste script gravava `len(maos)` do grupo, e o registro
    do PartyPoker que ele criou em producao ficou com 9 onde o upload gravaria 7 — os registros
    reparados apareceriam com mais maos que os importados normalmente. Regra 5: a mesma grandeza
    com duas definicoes, e a minha era a que ninguem mais usava.

    O cenario apaga a decisao de UMA mao de proposito: sem isso, toda mao tem decisao e as duas
    reguas dao o mesmo numero — o teste passaria sem distinguir nada.
    """
    _monta()
    from leaklab.parser import parse_pokerstars_file_from_text
    maos = parse_pokerstars_file_from_text(_texto_de_tres_torneios())
    # a 1a mao do grupo 555000002 (indice 2) perde a decisao
    alvo = str(getattr(maos[2], 'hand_id', '') or '')
    conn = get_conn()
    conn.execute(_adapt("DELETE FROM decisions WHERE tournament_id=? AND hand_id=?"),
                 (7301, alvo))
    conn.commit(); conn.close()

    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    conn = get_conn()
    por_tid = {}
    for r in conn.execute(_adapt(
            "SELECT id, tournament_id, hands_count FROM tournaments WHERE user_id=?"),
            (UID,)).fetchall():
        rr = dict(r)
        distintas = value(conn.execute(_adapt(
            "SELECT COUNT(DISTINCT hand_id) AS n FROM decisions WHERE tournament_id=?"),
            (rr['id'],)).fetchone(), 'n')
        por_tid[rr['tournament_id']] = (rr['hands_count'], distintas)
    conn.close()
    # o grupo 555000002 tem 2 maos no texto e agora 1 com decisao
    assert por_tid['555000002'][0] == 1, (
        'hands_count do 555000002 e %s; deveria ser 1 (2 maos no texto, 1 com decisao)'
        % por_tid['555000002'][0])
    for tid, (hc, dist) in por_tid.items():
        assert hc == dist, (
            '%s: hands_count=%s mas %s maos tem decisao — reguas diferentes' % (tid, hc, dist))


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


def test_o_VINCULO_com_a_fila_do_solver_acompanha_as_decisoes():
    """Achado no dry-run do Luigi: 12 linhas de `gto_tournament_queue` em t62, de decisoes que
    iam para outros tres registros.

    Esse vinculo (torneio, spot_hash) e o que faz o gancho reconciliar um torneio quando o solve
    chega. Se ele nao acompanha as decisoes, os registros novos **nunca sao reconciliados** e
    ficam com o veredito velho para sempre — dano que o defeito nao causava, porque com tudo num
    registro so o vinculo estava certo por acidente.
    """
    _monta()
    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    conn = get_conn()
    # para cada torneio, os spots das decisoes que estao nele
    esperado = {}
    for r in conn.execute(_adapt(
            "SELECT d.tournament_id AS t, d.spot_hash AS s FROM decisions d "
            "JOIN tournaments x ON x.id=d.tournament_id WHERE x.user_id=?"), (UID,)).fetchall():
        rr = dict(r)
        esperado.setdefault(rr['t'], set()).add(rr['s'])
    real = {}
    for r in conn.execute(_adapt(
            "SELECT q.tournament_id AS t, q.spot_hash AS s FROM gto_tournament_queue q "
            "JOIN tournaments x ON x.id=q.tournament_id WHERE x.user_id=?"), (UID,)).fetchall():
        rr = dict(r)
        real.setdefault(rr['t'], set()).add(rr['s'])
    conn.close()
    # o cenario tem TRES torneios (555000001/2/3), logo tres registros com decisoes
    assert len(esperado) == 3, ('o cenario nao separou: %s' % list(esperado))
    for t, spots in esperado.items():
        assert real.get(t) == spots, (
            'torneio %s: a fila tem %s, as decisoes dele tem %s' % (t, real.get(t), spots))


def test_played_at_vem_do_TEXTO_de_cada_grupo():
    """A data de JOGO de cada registro novo sai do texto dele, nao e herdada.

    Achado ao reparar a conta do dono: o registro misturado tinha `played_at` NULO, e herdar isso
    deixaria os quatro registros novos fora de todo filtro por data de jogo — que e o eixo de
    tempo do produto (AY-4). O texto de cada grupo tem a data real.

    E o registro que FICA so ganha data se estava vazio: se ja havia uma, ela e dado do jogador
    e nao cabe a este script troca-la.
    """
    _monta()
    conn = get_conn()
    conn.execute(_adapt("UPDATE tournaments SET played_at=NULL WHERE id=?"), (7301,))
    conn.commit(); conn.close()

    dump = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); dump.close()
    assert _roda('--user', str(UID), '--apply', '--dump', dump.name).returncode == 0
    ts, _, _ = _estado()
    conn = get_conn()
    datas = {}
    for r in conn.execute(_adapt(
            "SELECT tournament_id, played_at FROM tournaments WHERE user_id=?"),
            (UID,)).fetchall():
        rr = dict(r)
        datas[rr['tournament_id']] = str(rr['played_at'] or '')[:10]
    conn.close()
    assert len(datas) == 3, list(datas)
    vazias = [k for k, v in datas.items() if not v]
    assert vazias == [], (
        'registro(s) sem data de jogo: %s. Eles ficariam fora de todo filtro por data.' % vazias)
    # e a data tem de vir do TEXTO, nao inventada: o fixture e de 2026
    assert all(v.startswith('20') for v in datas.values()), datas


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


def test_cada_linha_do_dump_vai_para_o_DISCO_na_hora():
    """Registro que fica no buffer e registro que nao existe (regra 6).

    A primeira versao do script escrevia no arquivo e chamava `flush()` so no fim. O processo
    morreu no meio (a conexao ao Neon caiu durante o import do `api.app`) e o arquivo ficou com
    ZERO linhas. Naquele caso nada tinha sido commitado e nao houve dano — mas se tivesse, eu
    estaria com escrita no banco e nenhum registro para reverter.

    O teste le o arquivo por um handle SEPARADO, que e o que um processo de recuperacao faria.
    """
    from scripts.repara_arquivo_multi_torneio import Dump
    tmp = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False); tmp.close()
    d = Dump(tmp.name)
    try:
        d.registra({'tipo': 'teste', 'i': 1})
        # sem close, sem flush manual: o disco ja tem de ter a linha
        lido = io.open(tmp.name, encoding='utf-8').read()
        assert lido.strip(), 'a primeira linha nao chegou ao disco antes da proxima escrita'
        assert json.loads(lido.strip())['i'] == 1, lido
        d.registra({'tipo': 'teste', 'i': 2})
        linhas = [l for l in io.open(tmp.name, encoding='utf-8').read().splitlines() if l.strip()]
        assert len(linhas) == 2, ('o disco tem %d linha(s), deveria ter 2' % len(linhas))
        assert d.n == 2, d.n
    finally:
        d.close()
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


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
