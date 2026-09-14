# -*- coding: utf-8 -*-
"""Separa os registros que guardam maos de VARIOS torneios, sem perder nada do que aponta neles.

── O defeito, medido em producao em 13/09 ─────────────────────────────────────────────────────

Ate o deploy de 56c7623c o `/analyze` lia `hands[0].tournament_id` e gravava o arquivo inteiro
sob esse id. Varredura completa do acervo (868 registros com hand history, controle fechando em
868): **42 registros continham 224 torneios reais**, em 3 contas.

    michel (58, Pro)  40 registros -> 215 torneios   22.323 decisoes = 89,6% do perfil dele
    Luigi  (26, free)  1 registro  ->   4 torneios      412 decisoes = 100% do perfil dele
    wrodrigo (3, Pro)  1 registro  ->   5 torneios      295 decisoes =  4,2%

Dos 224, **179 nao existem em lugar nenhum** — estao escondidos dentro de um registro com o nome
de outro torneio. O torneio que da o NOME ao registro representa, na mediana, 21% das maos dele;
no pior caso 0,5% (5 maos de 991). E dos 24 registros com resultado, **21 tem place/prize de
OUTRO torneio** do mesmo arquivo.

O deploy parou de criar casos novos. Este script conserta o que ficou.

── Porque MOVER e nao reimportar ──────────────────────────────────────────────────────────────

Cinco tabelas apontam para `decisions`, quatro com CASCADE. Medido nos 42 registros: 0
anotacoes de coach, **187 drill_sessions** e **1.320 vereditos_por_semelhanca**. Apagar e
reimportar destruiria tudo isso — dano que o defeito nao causava (regra 7). Mover preserva,
porque esses ponteiros sao para `decisions.id`, que nao muda.

Nada aponta para `tournaments.id` desses 42 alem das proprias decisions (`session_goals` e
`tournament_finishes` deram zero).

── Decisoes de desenho, e o motivo de cada uma ────────────────────────────────────────────────

1. **O torneio GRAVADO fica no registro atual**, mesmo quando e o minoritario. Renomear o
   registro para o majoritario moveria menos decisoes, mas trocaria o nome de um registro que o
   jogador ja viu na tela — e a identidade e exatamente o que estava errado. Encolher um registro
   conhecido e mais legivel do que ve-lo virar outro torneio.
2. **`imported_at` e herdado do original.** O torneio nao foi importado hoje, e o eixo de tempo
   do produto depende disso (AY-4). De quebra, a cota nao e afetada: ela e um CONTADOR
   (`users.tournaments_this_month`) que so sobe no upload, e este script nao o toca.
3. **`place`/`prize`/`buy_in` sao re-extraidos do texto DE CADA GRUPO**, pelo mesmo
   `_extract_financials` do produto. E o unico jeito de o resultado parar no torneio certo.
4. **Os agregados sao recalculados por `recalcula_agregados_do_torneio`**, a funcao do produto,
   e NAO pelo reconcile inteiro. Medido no ensaio com a copia do unico pagante: chamar o
   reconcile mudou **115 decisoes de banda** (67 small_mistake -> marginal, 48 no inverso) e
   reescreveu o `score` de todas, com o `gto_label` intacto em 100% — era a politica atual
   sendo aplicada a linhas antigas (AY-42). Separar registros NAO MUDA VEREDITO. A regra dos
   buckets continua vivendo num lugar so (regra 5).
5. **Dump ANTES de qualquer escrita, sempre.** `--apply` sem dump gravavel aborta.

── Uso ────────────────────────────────────────────────────────────────────────────────────────

    python -m scripts.repara_arquivo_multi_torneio --user 26              # dry-run (padrao)
    python -m scripts.repara_arquivo_multi_torneio --user 26 --apply --dump /tmp/luigi.jsonl
    python -m scripts.repara_arquivo_multi_torneio --reverter /tmp/luigi.jsonl
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.schema import get_conn                                           # noqa: E402
from database.repositories import _adapt                                       # noqa: E402
from database.rowutil import value                                             # noqa: E402
from leaklab.parser import parse_pokerstars_file_from_text, extract_session_times  # noqa: E402


# As tabelas que guardam decision_id E tournament_id ao mesmo tempo. Quando a decisao muda de
# torneio, elas tem de mudar junto. Varredura das 8 tabelas com coluna `tournament_id` em 13/09;
# as outras 6 referenciam torneio sem passar por decisao (`opponent_profiles`, as duas filas do
# solver, `session_goals`, `tournament_finishes`, e a propria `decisions`).
TABELAS_COM_OS_DOIS = ('coach_hand_annotations', 'vereditos_por_semelhanca')


class Dump:
    """O registro para desfazer, com garantia de estar EM DISCO antes de o banco mudar.

    A primeira versao usava o arquivo direto e chamava `flush()` so no fim. Isso e um registro
    que nao existe: o processo morreu no meio (a conexao ao Neon caiu) e o arquivo ficou com 0
    linhas. Ali nada tinha sido commitado e nao houve dano, mas se tivesse, eu estaria com
    escrita no banco e nenhum registro para reverter — exatamente a falha silenciosa que a
    regra 6 descreve.

    Cada linha vai para o disco na hora (`flush` + `fsync`). E mais lento e e o ponto.
    """

    def __init__(self, caminho):
        self.f = io.open(caminho, 'w', encoding='utf-8')
        self.n = 0

    def registra(self, obj):
        self.f.write(json.dumps(obj, ensure_ascii=False) + chr(10))
        self.f.flush()
        os.fsync(self.f.fileno())
        self.n += 1

    def close(self):
        try:
            self.f.flush()
            os.fsync(self.f.fileno())
        finally:
            self.f.close()


def _grupos(raw_text):
    """As maos por torneio, na ordem em que aparecem. `None` se o parser nao leu o texto."""
    try:
        maos = parse_pokerstars_file_from_text(raw_text or '')
    except Exception:
        return None
    if not maos:
        return None
    g = {}
    for m in maos:
        tid = str(getattr(m, 'tournament_id', '') or '')
        g.setdefault(tid, []).append(m)
    return g


def _texto(maos):
    return '\n'.join((getattr(m, 'raw_text', '') or '') for m in maos)


def _hand_ids(maos):
    return [str(getattr(m, 'hand_id', '') or '') for m in maos
            if str(getattr(m, 'hand_id', '') or '')]


def _planeja(conn, registro):
    """O que fazer com UM registro. Nao escreve nada.

    Devolve `{'id', 'fica', 'novos': [...], 'recusa': motivo|None}`.
    """
    d = dict(registro)
    g = _grupos(d.get('raw_text'))
    if g is None:
        return {'id': d['id'], 'recusa': 'o parser nao leu o raw_text'}
    if len(g) <= 1:
        return {'id': d['id'], 'recusa': 'um torneio so (nada a separar)'}
    if '' in g:
        # Mesma recusa que a divisao do upload faz: decidir onde ficam as maos sem torneio
        # (cash) e decisao de produto. Zero casos no acervo em 13/09.
        return {'id': d['id'], 'recusa': 'mistura cash (id vazio) e torneio'}

    # Registro sem decisao nenhuma: dividir cria N linhas de ZERO maos na tela, que e pior que
    # a linha unica de hoje. Um caso no acervo inteiro (t262: 2,43 MB, 1.500 maos, 0 decisoes),
    # e ele precisa de investigacao propria — por que perdeu a analise — nao de separacao.
    if not _tem_decisao(conn, d['id']):
        return {'id': d['id'], 'recusa': 'sem decisao nenhuma (dividir criaria linhas vazias)'}

    gravado = str(d['tournament_id'])
    if gravado not in g:
        # Nunca aconteceu no acervo (0 de 42), mas se acontecer o registro perderia a identidade
        # e a escolha de quem fica seria minha, nao do dado.
        return {'id': d['id'], 'recusa': 'o torneio gravado nao esta no proprio raw_text'}

    novos, colisoes = [], []
    for tid, maos in g.items():
        if tid == gravado:
            continue
        ja = conn.execute(_adapt(
            "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
            (d['user_id'], tid)).fetchone()
        item = {'tournament_id': tid, 'maos': maos, 'n_maos': len(maos),
                'hand_ids': _hand_ids(maos)}
        if ja:
            # O torneio JA tem registro proprio: as maos vao para LA, nao para um registro
            # novo. E o mesmo merge que o upload faz quando o T# reaparece noutro arquivo.
            item['destino'] = value(ja, 'id')
            colisoes.append((tid, item['destino'], len(maos)))
        novos.append(item)
    return {'id': d['id'], 'user_id': d['user_id'], 'gravado': gravado,
            'fica': {'tournament_id': gravado, 'maos': g[gravado],
                     'n_maos': len(g[gravado]), 'hand_ids': _hand_ids(g[gravado])},
            'novos': novos, 'colisoes': colisoes, 'recusa': None}


def _maos_contadas(hand_ids, por_hand):
    """`hands_count` na MESMA regua do upload: maos DISTINTAS que geraram decisao.

    Nao e o numero de maos do arquivo. Medido em 13/09 com upload real das cinco salas contra o
    Postgres do homolog: `hands_count` == maos distintas com decisao em 5 de 5 (o valor vem de
    `metrics['total_hands']`, que conta o que foi ANALISADO, e mao sem decisao nao entra).

    A primeira versao deste script gravava `len(maos)` do grupo, e o registro do PartyPoker que
    ele criou ficou com 9 onde o upload gravaria 7 — os registros reparados apareceriam na tela
    com mais maos que os importados normalmente, pela regua errada. Regra 5: a mesma grandeza
    tinha duas definicoes, e a minha era a que ninguem mais usava.
    """
    return sum(1 for h in hand_ids if por_hand.get(h))


def _refaz_perfis(conn, tournament_db_id, maos, site, hero, dump):
    """Recalcula `opponent_profiles` do registro a partir das maos DELE.

    `opponent_profiles` e por TORNEIO e nao tem `hand_id`, entao nao acompanha a decisao como as
    outras tabelas: sem refazer, os registros novos nascem SEM HUD de oponente no replayer, e o
    que fica mantem um perfil somado de doze torneios. Medido na conta do pagante: 5.438 perfis
    em 70 registros, com `hands_seen` de ate 164 num vilao — amostra de doze torneios exibida
    como de um, e o HUD tem gate por amostra (3.452 perfis passam com 10+ maos).

    A regra de QUAIS perfis existem vem de `perfis_do_torneio`, a mesma que o `/analyze` usa: se
    ela vivesse aqui tambem, o HUD passaria a mostrar read que o upload recusa (regra 5).

    Apaga antes de gravar: o upsert e por (torneio, jogador), entao um vilao que nao esta mais
    naquele grupo sobreviveria com o perfil velho.
    """
    from leaklab.opponent_stats import perfis_do_torneio
    antigos = [dict(r) for r in conn.execute(_adapt(
        "SELECT * FROM opponent_profiles WHERE tournament_id=?"),
        (tournament_db_id,)).fetchall()]
    for a in antigos:
        dump.registra({'tipo': 'perfil_apagado',
                       'linha': {k: (str(v) if hasattr(v, 'isoformat') else v)
                                 for k, v in a.items()}})
    conn.execute(_adapt("DELETE FROM opponent_profiles WHERE tournament_id=?"),
                 (tournament_db_id,))
    perfis = perfis_do_torneio(maos, site or '', hero or '')
    if perfis:
        from database.repositories import upsert_opponent_profiles
        # a conexao do reparo, nao uma nova: ele esta no meio de uma transacao
        upsert_opponent_profiles(tournament_db_id, perfis, conn=conn)
    return len(antigos), len(perfis)


def _maos_do_registro(conn, tournament_db_id):
    """As maos que o `raw_text` do registro declara, na ordem cronologica por hand_id."""
    raw = dict(conn.execute(_adapt(
        "SELECT raw_text FROM tournaments WHERE id=?"), (tournament_db_id,)).fetchone())
    try:
        return parse_pokerstars_file_from_text(raw.get('raw_text') or '')
    except Exception:
        return []


def _ordena_maos(maos):
    """Uniao ORDENADA por hand_id, a mesma regra do merge do `/analyze`: o # global do
    PokerStars e monotonico no tempo, e sem isso a sequencia segue a ordem de IMPORT."""
    def chave(h):
        hid = str(getattr(h, 'hand_id', '') or '')
        return (0, int(hid)) if hid.isdigit() else (1, hid)
    return sorted(maos, key=chave)


def _tem_decisao(conn, tournament_db_id):
    return bool(value(conn.execute(_adapt(
        "SELECT COUNT(*) AS n FROM decisions WHERE tournament_id=?"),
        (tournament_db_id,)).fetchone(), 'n'))


def _fila_do_torneio(conn, tournament_db_id):
    """Os `spot_hash` que a fila do solver ainda associa a este registro.

    `gto_tournament_queue` e um vinculo (tournament_id, spot_hash): "este torneio depende deste
    spot". Quando o solve chega, o gancho reconcilia os torneios ligados ao spot. Se as decisoes
    mudam de torneio e o vinculo nao vai com elas, os registros novos **nunca sao reconciliados**
    — ficam com o veredito velho para sempre. Achado no dry-run do Luigi: 12 linhas apontando
    para t62, de decisoes que iam para outros tres registros.
    """
    return {str(dict(r)['spot_hash']) for r in conn.execute(_adapt(
        "SELECT spot_hash FROM gto_tournament_queue WHERE tournament_id=?"),
        (tournament_db_id,)).fetchall()}


def _spots_por_decisao(conn, tournament_db_id):
    """{decision_id: spot_hash} do registro. `spot_hash` esta preenchido em 100% das decisoes."""
    return {dict(r)['id']: str(dict(r)['spot_hash'] or '')
            for r in conn.execute(_adapt(
                "SELECT id, spot_hash FROM decisions WHERE tournament_id=?"),
                (tournament_db_id,)).fetchall()}


def _decisoes_por_hand(conn, tournament_db_id):
    """{hand_id: [decision_id, ...]} do registro. Base para mover sem depender do texto."""
    out = {}
    for r in conn.execute(_adapt(
            "SELECT id, hand_id FROM decisions WHERE tournament_id=? ORDER BY id"),
            (tournament_db_id,)).fetchall():
        rr = dict(r)
        out.setdefault(str(rr['hand_id']), []).append(rr['id'])
    return out


def _relatorio(conn, planos, por_hand_cache):
    print('=' * 92)
    print('PLANO DE SEPARACAO (dry-run: nada foi escrito)')
    print('=' * 92)
    # Torneios que aparecem em MAIS DE UM registro: o primeiro cria, os outros fazem MERGE.
    # O relatorio tem de declarar isso — o dono aprova o reparo lendo daqui, e um merge que nao
    # aparece no plano e uma escrita que ele nao aprovou. No acervo do pagante sao 6 casos.
    _vezes = {}
    for _p in planos:
        if _p.get('recusa'):
            continue
        for _i in _p['novos']:
            _vezes.setdefault(_i['tournament_id'], []).append(_p['id'])
    repetidos = {t: v for t, v in _vezes.items() if len(v) > 1}
    total_novos = total_movidas = 0
    for p in planos:
        if p.get('recusa'):
            print('  t%-6s RECUSADO: %s' % (p['id'], p['recusa']))
            continue
        por_hand = por_hand_cache[p['id']]
        fica_decs = sum(len(por_hand.get(h, [])) for h in p['fica']['hand_ids'])
        print()
        print('  t%-6s user=%-4s  %d torneios dentro' % (
            p['id'], p['user_id'], 1 + len(p['novos']) + len(p['colisoes'])))
        print('     FICA no registro: %-14s %4d maos (%d no texto), %4d decisoes' % (
            p['fica']['tournament_id'], _maos_contadas(p['fica']['hand_ids'], por_hand),
            p['fica']['n_maos'], fica_decs))
        for n in p['novos']:
            ndecs = sum(len(por_hand.get(h, [])) for h in n['hand_ids'])
            tid_n = n['tournament_id']
            # DUAS razoes para ser merge, e a primeira version deste relatorio olhava so a
            # segunda: (a) o torneio JA tem registro proprio (`destino`, vindo do plano) — foi o
            # caso dos 29 torneios que o jogador subiu de madrugada, ja separados; (b) o torneio
            # aparece em mais de um registro misturado, e o primeiro deles e quem cria.
            # Sem olhar (a), o MESMO torneio saia como "registro NOVO" numa linha e "MERGE" na
            # outra, e o total de novos vinha inflado — numero que o dono usa para aprovar.
            destino_rel = n.get('destino')
            if not destino_rel and tid_n in repetidos and repetidos[tid_n][0] != p['id']:
                destino_rel = repetidos[tid_n][0]
            if destino_rel:
                print('     MERGE em t%-6s %-14s %4d maos (%d no texto), %4d decisoes a mover' % (
                    destino_rel, tid_n, _maos_contadas(n['hand_ids'], por_hand),
                    n['n_maos'], ndecs))
                total_movidas += ndecs
                continue
            total_novos += 1
            total_movidas += ndecs
            print('     registro NOVO:   %-14s %4d maos (%d no texto), %4d decisoes a mover' % (
                n['tournament_id'], _maos_contadas(n['hand_ids'], por_hand), n['n_maos'],
                ndecs))
        for tid, outro_id, nm in p['colisoes']:
            # MERGE, e nao "pulado": a mensagem antiga dizia que as maos ficavam onde estao, e o
            # dono aprova o reparo lendo ESTE relatorio. Desde o conserto do UniqueViolation o
            # comportamento e mover as decisoes para o registro que ja abriga o torneio.
            ndecs_m = sum(len(por_hand.get(h, []))
                          for item in p['novos'] if item['tournament_id'] == tid
                          for h in item['hand_ids'])
            print('     MERGE em t%-6s %-14s %4d maos (%d no texto), %4d decisoes a mover' % (
                outro_id, tid, _maos_contadas(
                    [h for item in p['novos'] if item['tournament_id'] == tid
                     for h in item['hand_ids']], por_hand), nm, ndecs_m))
        # decisoes que nao casaram com nenhum grupo: nao podem existir, e se existirem eu quero
        # saber ANTES de mover — seriam decisoes orfas do proprio registro.
        todos_hids = set(p['fica']['hand_ids'])
        for n in p['novos']:
            todos_hids |= set(n['hand_ids'])
        orfas = [h for h in por_hand if h not in todos_hids]
        if orfas:
            n_orf = sum(len(por_hand[h]) for h in orfas)
            print('     ATENCAO: %d decisoes em %d maos que o texto NAO explica (ficam onde estao)'
                  % (n_orf, len(orfas)))
    # O que referencia o TORNEIO direto (sem passar por decisao) fica onde esta, e o dono
    # precisa saber: `opponent_profiles` de um registro misturado foi calculado sobre maos de
    # varios torneios, entao ja esta errado HOJE. Separar nao conserta isso, e recalcular e
    # frente propria. Reportar e o minimo honesto.
    ids_reg = [p['id'] for p in planos if not p.get('recusa')]
    if ids_reg:
        marcas = ','.join(['?'] * len(ids_reg))
        print()
        print('  o que referencia o TORNEIO direto nestes registros (NAO e movido):')
        for tab in ('opponent_profiles', 'gto_hand_requests', 'gto_tournament_queue',
                    'session_goals', 'tournament_finishes'):
            try:
                n = value(conn.execute(_adapt(
                    "SELECT COUNT(*) AS n FROM %s WHERE tournament_id IN (%s)" % (tab, marcas)),
                    tuple(ids_reg)).fetchone(), 'n')
            except Exception:
                n = '?'
            print('     %-24s %s linha(s)%s' % (
                tab, n,
                '  <== o vinculo com a fila ACOMPANHA as decisoes'
                if tab == 'gto_tournament_queue' and n else ''))
    print()
    print('  ' + '-' * 88)
    print('  registros novos a criar: %d   |   decisoes a mover: %d' % (total_novos, total_movidas))
    n_merge_existente = sum(1 for _p in planos if not _p.get('recusa')
                            for _i in _p['novos'] if _i.get('destino'))
    if n_merge_existente:
        print('  desses, %d torneio(s) JA tem registro proprio: as maos vao para la (MERGE)' %
              n_merge_existente)
    if repetidos:
        print('  e %d torneio(s) aparecem em mais de um registro misturado (o 1o cria, os outros '
              'fazem MERGE)' % len(repetidos))
    print('  (mover preserva drill_sessions e vereditos_por_semelhanca: os ponteiros sao para')
    print('   decisions.id, que nao muda)')


def _aplica(planos, por_hand_cache, dump):
    """Executa. O dump ja foi aberto e validado pelo chamador.

    A conexao e ABERTA AQUI, depois dos imports, e nao recebida do planejamento. Motivo medido:
    `from api.app import ...` carrega o app inteiro (60+ rotas, Sentry) e leva segundos; com a
    conexao ao Neon aberta e ociosa nesse intervalo, o servidor a derruba e a primeira escrita
    morre com `SSL connection has been closed unexpectedly`. Foi o que aconteceu na primeira
    tentativa no Luigi — sem dano, porque nada tinha sido commitado.
    """
    from api.app import _extract_financials, _detect_site, _extract_date
    conn = get_conn()
    criados = 0
    movidas = 0
    tocados = set()
    # (user_id, tournament_id) -> id do registro que abriga aquele torneio.
    #
    # Existe porque o MESMO torneio pode estar dentro de DOIS registros misturados: no acervo do
    # michel, 6 de 239 torneios (t551 e t1177 compartilham o T#4028679584, t790 e t1179 o
    # T#4028679610). O planejamento roda todo ANTES da primeira escrita, entao ele nao ve o
    # registro que outro plano vai criar — e o segundo INSERT batia no UNIQUE
    # (user_id, tournament_id). O ensaio na COPIA do michel pegou isso; Luigi e a conta do dono
    # nao expuseram, porque neles cada torneio estava num registro so.
    #
    # Com o mapa, o segundo grupo MOVE as decisoes para o registro que o primeiro criou, em vez
    # de tentar criar de novo. E o mesmo merge que o upload faz quando um T# reaparece.
    #
    # O mapa nasce UMA vez, aqui, e nao dentro do laco: na primeira versao desta correcao eu o
    # reiniciava a cada plano, o que apagava justamente os registros criados nos planos
    # anteriores — o caso que ele existe para cobrir.
    destino_de = {}
    for _p in planos:
        if _p.get('recusa'):
            continue
        for _item in _p['novos']:
            if _item.get('destino'):
                destino_de[(_p['user_id'], _item['tournament_id'])] = _item['destino']
    for p in planos:
        if p.get('recusa'):
            continue
        d = dict(conn.execute(_adapt(
            "SELECT * FROM tournaments WHERE id=?"), (p['id'],)).fetchone())
        por_hand = por_hand_cache[p['id']]
        # A fila do solver e os spots ANTES de mexer: depois de mover, a associacao decisao ->
        # torneio ja mudou e eu nao saberia mais de quem era cada spot.
        fila_pendente = _fila_do_torneio(conn, p['id'])
        spot_de = _spots_por_decisao(conn, p['id'])

        # registro do estado ANTERIOR do registro que fica, antes de encolher
        dump.registra({'tipo': 'tournament_antes', 'id': d['id'],
                               'raw_text': d.get('raw_text'),
                               'hands_count': d.get('hands_count'),
                               'decisions_count': d.get('decisions_count'),
                               'place': d.get('place'), 'prize': d.get('prize'),
                               'profit': d.get('profit'), 'buy_in': d.get('buy_in'),
                               'result': d.get('result'),
                               'labels_reconciled_at': (str(d.get('labels_reconciled_at'))
                                                        if d.get('labels_reconciled_at')
                                                        else None),
                               'started_at': str(d.get('started_at') or ''),
                               'ended_at': str(d.get('ended_at') or '')})

        for n in p['novos']:
            chave = (d['user_id'], n['tournament_id'])
            destino = n.get('destino') or destino_de.get(chave)
            if destino:
                # MERGE: as decisoes vao para o registro que ja abriga este torneio.
                ids = [i for h in n['hand_ids'] for i in por_hand.get(h, [])]
                for dec_id in ids:
                    dump.registra({'tipo': 'decision_movida', 'decision_id': dec_id,
                                   'de': d['id'], 'para': destino})
                    conn.execute(_adapt("UPDATE decisions SET tournament_id=? WHERE id=?"),
                                 (destino, dec_id))
                    for _tab in TABELAS_COM_OS_DOIS:
                        conn.execute(_adapt(
                            "UPDATE %s SET tournament_id=? WHERE decision_id=?" % _tab),
                            (destino, dec_id))
                movidas += len(ids)
                spots_daqui = {spot_de.get(i, '') for i in ids} & fila_pendente
                for sh in sorted(x for x in spots_daqui if x):
                    conn.execute(_adapt(
                        "INSERT INTO gto_tournament_queue (tournament_id, spot_hash) "
                        "VALUES (?,?) ON CONFLICT DO NOTHING"), (destino, sh))
                    dump.registra({'tipo': 'fila_vinculada', 'tournament_id': destino,
                                   'spot_hash': sh})
                # O destino ganha MAOS, e nao so decisoes. O merge do `/analyze` refaz o
                # `raw_text` com a uniao ordenada por hand_id; sem isso o destino fica com
                # decisoes que o texto dele nao explica — e o REPLAYER le o texto, entao a mao
                # movida nao abriria. Achado no inventario do merge, nao numa execucao.
                dd = dict(conn.execute(_adapt(
                    "SELECT hero, site, raw_text, played_at FROM tournaments WHERE id=?"),
                    (destino,)).fetchone())
                dump.registra({'tipo': 'destino_antes', 'id': destino,
                               'raw_text': dd.get('raw_text')})
                juntas = _ordena_maos(_maos_do_registro(conn, destino) + list(n['maos']))
                texto_d = _texto(juntas)
                hero_d = dd.get('hero') or ''
                site_d = dd.get('site') or _detect_site(texto_d)
                fin_d = _extract_financials(texto_d, hero_d, site_d, None)
                st_d, en_d = extract_session_times(texto_d)
                n_h = value(conn.execute(_adapt(
                    "SELECT COUNT(DISTINCT hand_id) AS n FROM decisions WHERE tournament_id=?"),
                    (destino,)).fetchone(), 'n')
                n_d = value(conn.execute(_adapt(
                    "SELECT COUNT(*) AS n FROM decisions WHERE tournament_id=?"),
                    (destino,)).fetchone(), 'n')
                conn.execute(_adapt(
                    "UPDATE tournaments SET raw_text=?, hands_count=?, decisions_count=?, "
                    "started_at=?, ended_at=?, place=?, prize=?, profit=?, buy_in=?, result=?, "
                    "played_at=? WHERE id=?"),
                    (texto_d, n_h, n_d, st_d, en_d, fin_d.get('place'), fin_d.get('prize'),
                     fin_d.get('profit'), fin_d.get('buy_in'),
                     'itm' if fin_d.get('prize') else None,
                     _extract_date(texto_d) or dd.get('played_at'), destino))
                _refaz_perfis(conn, destino, juntas, site_d, hero_d, dump)
                tocados.add(destino)
                continue

            texto = _texto(n['maos'])
            hero = d.get('hero') or ''
            site = d.get('site') or _detect_site(texto)
            fin = _extract_financials(texto, hero, site, None)
            st, en = extract_session_times(texto)
            nome = d.get('tournament_name')
            # `played_at` vem do texto DESTE grupo, nao herdado. Herdar seria carregar a data de
            # outro torneio — ou `None`, como no registro da minha conta, que deixa o torneio
            # fora de todo filtro por data de jogo (o eixo de tempo do AY-4). O herdado fica
            # como reserva, para o caso de o dialeto nao declarar data.
            quando = _extract_date(texto) or d.get('played_at')
            # `labels_reconciled_at` HERDADO, e isso nao e detalhe: o gancho
            # `_reconcile_drained_tournaments` roda em LOOP CONTINUO e seleciona por
            # `labels_reconciled_at IS NULL`. Nascendo nulo, os registros novos seriam
            # reconciliados em minutos — e o reconcile reavalia label e score por linha (no
            # ensaio: 115 decisoes trocando de banda). Tirar o reconcile daqui sem herdar a
            # marca so transferia o efeito para um momento em que ninguem esta olhando.
            # 70 dos 71 registros dele ja estao reconciliados.
            #
            # `result` DERIVADO do premio re-extraido, com a mesma regra do `_analyze_impl`
            # ('itm' quando ha premio). Herdar propagaria o ITM do conjunto para todos os
            # filhos, inclusive os que nao premiaram.
            conn.execute(_adapt(
                "INSERT INTO tournaments (user_id, tournament_id, site, tournament_name, hero, "
                "played_at, imported_at, hands_count, decisions_count, raw_text, is_pko, "
                "started_at, ended_at, place, prize, profit, buy_in, result, "
                "labels_reconciled_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"),
                (d['user_id'], n['tournament_id'], site, nome, hero,
                 quando, d.get('imported_at'),
                 _maos_contadas(n['hand_ids'], por_hand), 0, texto,
                 d.get('is_pko') or False, st, en,
                 fin.get('place'), fin.get('prize'), fin.get('profit'), fin.get('buy_in'),
                 'itm' if fin.get('prize') else None,
                 d.get('labels_reconciled_at')))
            novo_id = value(conn.execute(_adapt(
                "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
                (d['user_id'], n['tournament_id'])).fetchone(), 'id')
            criados += 1
            destino_de[(d['user_id'], n['tournament_id'])] = novo_id
            dump.registra({'tipo': 'tournament_criado', 'id': novo_id,
                                   'tournament_id': n['tournament_id'],
                                   'user_id': d['user_id']})

            ids = [i for h in n['hand_ids'] for i in por_hand.get(h, [])]
            for dec_id in ids:
                dump.registra({'tipo': 'decision_movida', 'decision_id': dec_id,
                                       'de': d['id'], 'para': novo_id})
                conn.execute(_adapt("UPDATE decisions SET tournament_id=? WHERE id=?"),
                             (novo_id, dec_id))
                # DUAS tabelas guardam decision_id E tournament_id. Mover a decisao sem mexer
                # nelas deixaria a linha apontando para o torneio de onde a decisao SAIU —
                # inconsistencia que o defeito nao causava. Achado varrendo as 8 tabelas com
                # coluna `tournament_id`, nao por teste (regra 5).
                for _tab in TABELAS_COM_OS_DOIS:
                    conn.execute(_adapt(
                        "UPDATE %s SET tournament_id=? WHERE decision_id=?" % _tab),
                        (novo_id, dec_id))
            movidas += len(ids)
            conn.execute(_adapt("UPDATE tournaments SET decisions_count=? WHERE id=?"),
                         (len(ids), novo_id))
            # O vinculo com a fila do solver acompanha as decisoes. Sem isto, quando o solve
            # chegar o gancho reconcilia o registro VELHO e o novo fica com veredito velho para
            # sempre — dano que o defeito nao causava (regra 7).
            spots_daqui = {spot_de.get(i, '') for i in ids} & fila_pendente
            for sh in sorted(x for x in spots_daqui if x):
                conn.execute(_adapt(
                    "INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (?,?) "
                    "ON CONFLICT DO NOTHING"), (novo_id, sh))
                dump.registra({'tipo': 'fila_vinculada', 'tournament_id': novo_id,
                                       'spot_hash': sh})
            # HUD de oponente do registro novo, das maos DELE (ver `_refaz_perfis`).
            _refaz_perfis(conn, novo_id, n['maos'], site, hero, dump)
            tocados.add(novo_id)

        # o registro que fica encolhe para o seu proprio grupo
        texto_fica = _texto(p['fica']['maos'])
        fin = _extract_financials(texto_fica, d.get('hero') or '', d.get('site'), None)
        st, en = extract_session_times(texto_fica)
        n_decs = sum(len(por_hand.get(h, [])) for h in p['fica']['hand_ids'])
        conn.execute(_adapt(
            "UPDATE tournaments SET raw_text=?, hands_count=?, decisions_count=?, "
            "started_at=?, ended_at=?, place=?, prize=?, profit=?, buy_in=?, result=? "
            "WHERE id=?"),
            (texto_fica, _maos_contadas(p['fica']['hand_ids'], por_hand), n_decs, st, en,
             fin.get('place'), fin.get('prize'), fin.get('profit'), fin.get('buy_in'),
             'itm' if fin.get('prize') else None,
             d['id']))
        # E o registro velho solta os spots que nao tem mais nenhuma decisao dele. Um mesmo
        # spot_hash pode ser compartilhado por decisoes de torneios diferentes, entao a remocao
        # olha o que SOBROU, nao o que saiu.
        # A data do registro que fica: preenchida so se estava VAZIA. Se ja havia uma, ela e
        # dado do jogador e nao cabe a este script trocar — mesmo sabendo que num registro
        # misturado ela podia ser de outra noite. Trocar seria decisao de produto.
        if not d.get('played_at'):
            nova_data = _extract_date(texto_fica)
            if nova_data:
                conn.execute(_adapt("UPDATE tournaments SET played_at=? WHERE id=?"),
                             (nova_data, d['id']))
        ids_que_ficam = [i for h in p['fica']['hand_ids'] for i in por_hand.get(h, [])]
        spots_que_ficam = {spot_de.get(i, '') for i in ids_que_ficam}
        for sh in sorted(fila_pendente - spots_que_ficam):
            if not sh:
                continue
            conn.execute(_adapt(
                "DELETE FROM gto_tournament_queue WHERE tournament_id=? AND spot_hash=?"),
                (d['id'], sh))
            dump.registra({'tipo': 'fila_desvinculada', 'tournament_id': d['id'],
                                   'spot_hash': sh})
        # E o registro que fica perde os perfis do CONJUNTO: eles somavam a amostra de
        # todos os torneios do arquivo. Refeitos das maos que sobraram nele.
        _refaz_perfis(conn, d['id'], p['fica']['maos'], d.get('site') or '',
                      d.get('hero') or '', dump)
        tocados.add(d['id'])
        conn.commit()

    # Agregados (`avg_score` e os quatro `*_pct`) pela funcao do produto, e NAO pelo
    # `reconcile_tournament_labels` inteiro.
    #
    # A primeira versao chamava o reconcile, que resume os agregados mas antes disso REAVALIA
    # label e score de cada linha. Medido no ensaio com a copia do unico pagante: **115 decisoes
    # trocaram de banda** (67 small_mistake -> marginal, 48 no inverso) e o `score` de todas foi
    # reescrito, com o `gto_label` intacto em 100% delas — era a politica atual sendo aplicada a
    # linhas antigas (AY-42). Separar registros nao pode mudar 115 vereditos que o jogador ve;
    # se essas linhas devem ser reconciliadas, e decisao propria, com dry-run propria.
    from database.repositories import recalcula_agregados_do_torneio
    for tid in sorted(tocados):
        try:
            recalcula_agregados_do_torneio(conn, tid)
        except Exception as e:
            print('   aviso: agregados falharam em t%s: %s: %s' % (tid, type(e).__name__, e))
    conn.commit()
    conn.close()
    return criados, movidas, len(tocados)


def _reverter(caminho):
    linhas = [json.loads(l) for l in io.open(caminho, encoding='utf-8') if l.strip()]
    conn = get_conn()
    # ordem inversa: primeiro as decisoes voltam, depois os registros criados somem, por fim o
    # registro que ficou e restaurado. Apagar registro com decisao dentro dispara CASCADE.
    n_dec = n_del = n_res = 0
    for l in linhas:
        if l['tipo'] == 'decision_movida':
            conn.execute(_adapt("UPDATE decisions SET tournament_id=? WHERE id=?"),
                         (l['de'], l['decision_id']))
            for _tab in TABELAS_COM_OS_DOIS:
                conn.execute(_adapt(
                    "UPDATE %s SET tournament_id=? WHERE decision_id=?" % _tab),
                    (l['de'], l['decision_id']))
            n_dec += 1
    conn.commit()
    for l in linhas:
        if l['tipo'] == 'perfil_apagado':
            campos = [k for k in l['linha'] if k != 'id']
            marcas = ','.join(['?'] * len(campos))
            try:
                conn.execute(_adapt(
                    "INSERT INTO opponent_profiles (%s) VALUES (%s)" % (
                        ','.join(campos), marcas)),
                    tuple(l['linha'][k] for k in campos))
            except Exception:
                conn.rollback()
        elif l['tipo'] == 'destino_antes':
            conn.execute(_adapt("UPDATE tournaments SET raw_text=? WHERE id=?"),
                         (l['raw_text'], l['id']))
    conn.commit()
    for l in linhas:
        if l['tipo'] == 'fila_vinculada':
            conn.execute(_adapt(
                "DELETE FROM gto_tournament_queue WHERE tournament_id=? AND spot_hash=?"),
                (l['tournament_id'], l['spot_hash']))
        elif l['tipo'] == 'fila_desvinculada':
            conn.execute(_adapt(
                "INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (?,?) "
                "ON CONFLICT DO NOTHING"), (l['tournament_id'], l['spot_hash']))
    conn.commit()
    for l in linhas:
        if l['tipo'] == 'tournament_criado':
            resto = value(conn.execute(_adapt(
                "SELECT COUNT(*) AS n FROM decisions WHERE tournament_id=?"),
                (l['id'],)).fetchone(), 'n')
            if resto:
                print('   NAO apaguei t%s: ainda tem %s decisoes dentro' % (l['id'], resto))
                continue
            conn.execute(_adapt("DELETE FROM tournaments WHERE id=?"), (l['id'],))
            n_del += 1
    for l in linhas:
        if l['tipo'] == 'tournament_antes':
            conn.execute(_adapt(
                "UPDATE tournaments SET raw_text=?, hands_count=?, decisions_count=?, "
                "place=?, prize=?, profit=?, buy_in=?, result=? WHERE id=?"),
                (l['raw_text'], l['hands_count'], l['decisions_count'], l['place'],
                 l['prize'], l['profit'], l['buy_in'], l['result'], l['id']))
            n_res += 1
    conn.commit()
    conn.close()
    print('revertido: %d decisoes de volta, %d registros apagados, %d restaurados' % (
        n_dec, n_del, n_res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', type=int, help='so esta conta')
    ap.add_argument('--tournament', type=int, help='so este registro (id interno)')
    ap.add_argument('--apply', action='store_true', help='escreve (exige --dump)')
    ap.add_argument('--dump', help='arquivo do registro para desfazer')
    ap.add_argument('--reverter', help='desfaz a partir de um dump')
    a = ap.parse_args()

    if a.reverter:
        _reverter(a.reverter)
        return

    if a.apply and not a.dump:
        print('ERRO: --apply exige --dump. Escrita sem registro para desfazer nao acontece.')
        sys.exit(2)

    conn = get_conn()
    where, params = 'raw_text IS NOT NULL', []
    if a.user:
        where += ' AND user_id=?'
        params.append(a.user)
    if a.tournament:
        where += ' AND id=?'
        params.append(a.tournament)
    ids = [dict(r)['id'] for r in conn.execute(_adapt(
        "SELECT id FROM tournaments WHERE %s ORDER BY id" % where), tuple(params)).fetchall()]
    print('registros a examinar: %d' % len(ids))

    planos, cache = [], {}
    for tid in ids:
        r = conn.execute(_adapt(
            "SELECT id, user_id, tournament_id, raw_text FROM tournaments WHERE id=?"),
            (tid,)).fetchone()
        p = _planeja(conn, r)
        if p.get('recusa') == 'um torneio so (nada a separar)':
            continue                      # o caso comum; nao polui o relatorio
        planos.append(p)
        if not p.get('recusa'):
            cache[tid] = _decisoes_por_hand(conn, tid)

    if not planos:
        print('nenhum registro misturado nesse recorte.')
        conn.close()
        return

    _relatorio(conn, planos, cache)
    if not a.apply:
        print()
        print('  dry-run. Para aplicar: --apply --dump <arquivo>')
        conn.close()
        return

    # A conexao do PLANEJAMENTO fecha aqui. O `_aplica` abre a dele depois dos imports
    # pesados — ver a docstring dele.
    conn.close()
    dump = Dump(a.dump)
    print()
    print('APLICANDO (dump em %s)' % a.dump)
    criados, movidas, tocados = _aplica(planos, cache, dump)
    print('linhas no registro para desfazer: %d' % dump.n)
    dump.close()
    print('pronto: %d registros criados, %d decisoes movidas, %d torneios reconciliados' % (
        criados, movidas, tocados))
    print('para desfazer: --reverter %s' % a.dump)


if __name__ == '__main__':
    main()
