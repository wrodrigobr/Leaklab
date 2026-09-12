# -*- coding: utf-8 -*-
"""O reparo do nome do heroi conserta o que deve e RECUSA o que nao deve (12/09).

── O caso ─────────────────────────────────────────────────────────────────────────────────

Medido em producao: 21 torneios de duas contas com `tournaments.hero` gravado como o literal
`'Hero'`, enquanto o arquivo diz `MichelDiens` / `Michel Diens` / `Luciper`. As decisoes SAO
delas (casam 89% a 100% com o heroi do arquivo e 0% com o nome gravado), entao o dano e o rotulo.

Na MESMA varredura apareceram 18 torneios de outra conta cujo `hero` tambem divergo — e esses
NAO podem ser tocados: os arquivos tem de 2 a 6 herois (sao hand histories de terceiros), e
renomear pela maioria trocaria uma pessoa por outra escolhida por frequencia.

── Por que o guarda existe, e por que ele testa as RECUSAS ────────────────────────────────

Um reparo que acerta 21 e estraga 18 e pior que nenhum reparo. O valor deste script esta tanto
no que ele escreve quanto no que ele se nega a escrever, e e por isso que os cenarios negativos
sao a maior parte deste arquivo.

O criterio e ESTRUTURAL, nao um corte de porcentagem: o arquivo tem de ter UM heroi so, o nome
gravado nao pode ser jogador do arquivo, e o nome novo tem de aparecer entre os jogadores. Um
corte em "90% das acoes casam" seria numero arbitrario — o t208 de producao da 89% e e
exatamente o mesmo caso.

── O efeito colateral que o reparo leva junto ─────────────────────────────────────────────

O `/analyze` grava perfil de oponente para todo jogador `!= hero`. Com o `hero` errado, o
PROPRIO jogador entrou como oponente de si mesmo (21 de 21 torneios em producao). Renomear so a
coluna deixaria um "read" sobre ele mesmo no replay, e o guarda cobra que esse perfil saia — e
que o perfil do vilao de VERDADE fique.
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_BACK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _multi_heroi(raw):
    """Um arquivo com DOIS herois, no mesmo dialeto.

    Concatenar dialetos diferentes nao serve e a primeira versao do ensaio caiu nisso: a deteccao
    de site escolhe UM parser para o texto inteiro, as maos do outro dialeto nem sao lidas, e o
    cenario multi nunca se formava. O jeito que funciona e trocar o `Dealt to` de parte das maos.
    """
    blocos = [b for b in re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]
    metade = len(blocos) // 2
    return ''.join(b.replace('HeroPlayer', 'OutroCara') if i >= metade else b
                   for i, b in enumerate(blocos))


_SEMENTE = r'''
import io, os, sys
sys.path.insert(0, r"{back}")
os.environ["LEAKLAB_DB"] = r"{db}"
os.environ.pop("DATABASE_URL", None)
from database.schema import get_conn, init_db
from database.repositories import _adapt, upsert_opponent_profile
from leaklab.parser import parse_hand_history, heroi_das_maos
init_db()
conn = get_conn()
conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (1,'u','u@e.st','h')"))
raw = io.open(r"{raw}", encoding="utf-8").read()
multi = io.open(r"{multi}", encoding="utf-8").read()
maos = parse_hand_history(raw)
certo = heroi_das_maos(maos)
CEN = [(1, "Hero", raw), (2, certo, raw), (3, "Villain2", raw), (4, "Hero", multi),
       (5, "Fantasma", raw)]
for tid, hero, r in CEN:
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, site, raw_text) VALUES (?, 1, ?, 'T', ?, 'pokerstars', ?)"),
                 (tid, "T%d" % tid, hero, r))
n = 0
for tid in (1, 5):
    for m in maos:
        for a in (m.actions or []):
            if (a.player or "").strip() != certo:
                continue
            n += 1
            conn.execute(_adapt("INSERT INTO decisions (id, tournament_id, hand_id, street, "
                                "action_taken, best_action, label, score, position, num_players) "
                                "VALUES (?, ?, ?, 'preflop', ?, 'fold', 'standard', 0.0, 'BB', 9)"),
                         (n, tid, str(m.hand_id), (a.action or "").lower().rstrip("s")))
conn.commit()
upsert_opponent_profile(1, certo, {{"hands": 120}})       # o PROPRIO jogador: tem de sair
upsert_opponent_profile(1, "Villain2", {{"hands": 110}})  # vilao de verdade: tem de FICAR
conn.close()
print(certo)
'''

_ESTADO = r'''
import io, json, os, sys
sys.path.insert(0, r"{back}")
os.environ["LEAKLAB_DB"] = r"{db}"
os.environ.pop("DATABASE_URL", None)
from database.schema import get_conn
conn = get_conn()
t = {{str(r[0]): r[1] for r in conn.execute("SELECT id, hero FROM tournaments ORDER BY id").fetchall()}}
p = sorted(r[1] for r in conn.execute("SELECT tournament_id, player_name FROM opponent_profiles").fetchall())
conn.close()
print(json.dumps({{"tournaments": t, "perfis": p}}))
'''


def _py(codigo, **fmt):
    f = os.path.join(tempfile.gettempdir(), 'rh_%d.py' % os.getpid())
    io.open(f, 'w', encoding='utf-8').write(codigo.format(**fmt))
    r = subprocess.run([sys.executable, f], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                PYTHONIOENCODING='utf-8'))
    os.unlink(f)
    assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-2000:])
    return r.stdout.strip()


def _script(db, *args):
    r = subprocess.run([sys.executable, '-m', 'scripts.repara_heroi_do_arquivo'] + list(args),
                       cwd=_BACK, capture_output=True, text=True,
                       env=dict(os.environ, LEAKLAB_DB=db, PYTHONDONTWRITEBYTECODE='1',
                                PYTHONIOENCODING='utf-8', DATABASE_URL=''))
    return r.stdout


def _prepara():
    """Banco descartavel com os 5 cenarios. Devolve (caminho_do_db, nome_do_heroi_certo)."""
    tmp = tempfile.mkdtemp(prefix='reparo_heroi_')
    db = os.path.join(tmp, 'h.db')
    raw = os.path.join(_FIX, 'revalidation_mini.txt')
    multi = os.path.join(tmp, 'multi.txt')
    io.open(multi, 'w', encoding='utf-8', newline='\n').write(
        _multi_heroi(io.open(raw, encoding='utf-8').read()))
    certo = _py(_SEMENTE, back=_BACK, db=db, raw=raw, multi=multi)
    return db, certo


def test_o_dry_run_separa_os_cinco_cenarios():
    db, certo = _prepara()
    saida = _script(db)
    assert 'A REPARAR' in saida, saida
    # 1 (placeholder) e 5 (nome inventado) entram; 2 ja esta certo; 3 e 4 sao recusados.
    assert re.search(r'A REPARAR\s+2', saida), saida
    assert re.search(r'RECUSADO multi-heroi\s+1', saida), saida
    assert re.search(r'RECUSADO nome gravado E jogador\s+1', saida), saida
    assert re.search(r'nome OK\s+1', saida), saida
    assert 'DRY-RUN' in saida and 'GRAVADOS' not in saida, 'o dry-run escreveu'


def test_o_dry_run_NAO_escreve():
    """Controle do controle: sem `--apply`, o banco sai intacto."""
    db, certo = _prepara()
    antes = _py(_ESTADO, back=_BACK, db=db)
    _script(db)
    assert _py(_ESTADO, back=_BACK, db=db) == antes, 'o dry-run mexeu no banco'


def test_o_apply_conserta_so_o_que_deve():
    db, certo = _prepara()
    saida = _script(db, '--apply')
    assert 'GRAVADOS 2 torneios' in saida, saida
    estado = json.loads(_py(_ESTADO, back=_BACK, db=db))
    t = estado['tournaments']
    assert t['1'] == certo, ('o placeholder nao foi corrigido', t)
    assert t['5'] == certo, ('o nome inventado nao foi corrigido', t)
    assert t['2'] == certo, ('mexeu no que ja estava certo', t)
    # AS RECUSAS: intactas.
    assert t['3'] == 'Villain2', ('renomeou um torneio cujo hero e jogador de verdade', t)
    assert t['4'] == 'Hero', ('renomeou um arquivo MULTI-heroi (o caso de terceiros)', t)


def test_o_perfil_do_proprio_jogador_sai_e_o_do_vilao_FICA():
    db, certo = _prepara()
    _script(db, '--apply')
    perfis = json.loads(_py(_ESTADO, back=_BACK, db=db))['perfis']
    assert certo not in perfis, ('o jogador continua como oponente de si mesmo', perfis)
    assert 'Villain2' in perfis, ('o reparo apagou o perfil de um vilao de verdade', perfis)


def test_o_registro_para_desfazer_sai_completo():
    db, certo = _prepara()
    dump = os.path.join(os.path.dirname(db), 'dump.jsonl')
    _script(db, '--apply', '--dump', dump)
    linhas = [json.loads(l) for l in io.open(dump, encoding='utf-8') if l.strip()]
    assert len(linhas) == 2, linhas
    por_id = {l['id']: l for l in linhas}
    assert por_id[1]['de'] == 'Hero' and por_id[1]['para'] == certo, por_id[1]
    assert por_id[1]['perfil_apagado'] == certo, ('o dump nao registra o perfil apagado; sem '
                                                  'isso o rollback fica incompleto', por_id[1])
    assert por_id[5]['de'] == 'Fantasma' and por_id[5]['perfil_apagado'] is None, por_id[5]


def test_a_segunda_passagem_nao_acha_nada():
    """Idempotente: o reparo nao pode ficar reescrevendo a mesma coisa a cada rodada."""
    db, certo = _prepara()
    _script(db, '--apply')
    assert 'nada a reparar' in _script(db), 'a 2a passagem ainda acha trabalho'


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
