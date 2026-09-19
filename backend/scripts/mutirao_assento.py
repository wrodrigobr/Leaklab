# -*- coding: utf-8 -*-
"""Mutirao do AY-29b: re-solve do acervo antigo com o ASSENTO EFETIVO, fora do Neon.

── O pedido (19/09) ──────────────────────────────────────────────────────────────────────────

O dono: "Vamos fazer um script para rodar na maquina local. Apontando para o solver de prod.
Colocando os spots com baixa prioridade, e armazenando localmente os dados. Depois fazemos um
update direto no neon de uma so vez."

E, antes disso, o que matou a rotina anterior: "nao podemos deixa-lo ligado, vai gerar um custo
alto". A rotina que rodava dentro do consumidor gravava nó a nó no Neon; a 150-300 spots por hora
(numero medido e escrito no `burst_do_solver`), um lote de 300 mantinha o banco acordado por uma a
duas horas. A carona de 15 minutos controlava o INICIO do lote e nao a duracao dele. Este script
existe para o Neon so acordar duas vezes: uma para dar o trabalho, outra para receber o resultado.

── As tres fases ────────────────────────────────────────────────────────────────────────────

    python scripts/mutirao_assento.py puxar     --limite 50   > lote.json
    python scripts/mutirao_assento.py resolver  lote.json
    python scripts/mutirao_assento.py empurrar  --chunk 200

`puxar` e `empurrar` rodam DENTRO do container de producao (o script se manda por ssh), porque e
la que a `DATABASE_URL` mora -- nenhuma credencial do Neon encosta nesta maquina. `resolver` roda
aqui, com o Neon dormindo.

── Baixa prioridade, medida e nao suposta ───────────────────────────────────────────────────

O solver expoe `/health` com `active_solves` e `max_solves`. Antes de cada solve o script pergunta:
se producao esta usando o solver, ele ESPERA. Nao e estimativa de ociosidade, e a resposta do
proprio recurso -- e nao custa uma consulta ao banco para saber.

── O que este script NUNCA faz ──────────────────────────────────────────────────────────────

Re-chavear no antigo. O no velho fica onde esta e continua servindo a decisao dele pelo degrau
legado da cascata do `lookup_gto`; o no novo nasce sob a chave do assento efetivo. Re-chavear
faria o veredito de um spot responder por outro, que e a cicatriz do hash do board.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(AQUI, '..', 'data', 'mutirao_assento.db')

HOST = os.environ.get('LEAKLAB_HOST', 'deploy@167.233.139.122')
SOLVER = os.environ.get('MUTIRAO_SOLVER_URL', 'http://127.0.0.1:18765')

#: Quanto esperar quando o solver estiver ocupado com trabalho de producao.
ESPERA_S = 20


# ── Armazenamento local ─────────────────────────────────────────────────────────────────────

def _db():
    os.makedirs(os.path.dirname(BANCO), exist_ok=True)
    c = sqlite3.connect(BANCO)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS spots (
                     spot_hash   TEXT PRIMARY KEY,
                     tournament  INTEGER,
                     street      TEXT,
                     assento     TEXT,
                     payload     TEXT NOT NULL,
                     resultado   TEXT,
                     erro        TEXT,
                     solvado_em  TEXT,
                     empurrado   INTEGER NOT NULL DEFAULT 0
                 )""")
    c.commit()
    return c


# ── Ponte com producao: o script se manda por ssh e devolve JSON ───────────────────────────

def _no_container(codigo: str, entrada: str = None) -> str:
    """Roda `codigo` dentro do container `web` e devolve o stdout.

    A entrada opcional vai por stdin do proprio python remoto. Nada e escrito no host.
    """
    cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=20', HOST,
           'cd ~/app && docker compose exec -T web python -']
    r = subprocess.run(cmd, input=codigo if entrada is None else codigo.replace('__ENTRADA__', entrada),
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
    if r.returncode != 0:
        sys.exit('falha no container:\n%s' % (r.stderr or '')[-2000:])
    return r.stdout


_PUXAR = r'''
import json, sys
sys.path.insert(0, "/app")
from database.repositories import get_decisions, _adapt
from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.pareamento_decisoes import BaldeDeDecisoes
from leaklab.preflop_gto_ranges import _mapa_da_mesa
import leaklab.gto_solver as GS
import api.app as APP

LIMITE = __LIMITE__
FEITOS = set(json.loads("""__FEITOS__"""))

CAP = []
_orig = GS.montar_payload_postflop
def espiao(*a, **kw):
    out = _orig(*a, **kw)
    CAP.append({"kwargs": dict(kw), "resultado": out})
    return out
GS.montar_payload_postflop = espiao
APP.montar_payload_postflop = espiao
# Dubla o enfileirador: este passo NAO escreve nada, so descobre o payload.
import database.repositories as REPO
REPO.enqueue_solver_spot = lambda *a, **kw: True
APP.enqueue_solver_spot = lambda *a, **kw: True

def norm(a):
    if not a: return ""
    a = a.rstrip("s") if a.endswith("s") else a
    return "allin" if a in ("all-in","allin","jam","shove") else a

conn = get_conn()
sql = ("SELECT DISTINCT d.tournament_id AS tid FROM decisions d "
       "JOIN tournaments t ON t.id = d.tournament_id "
       "WHERE d.street IN ('flop','turn','river') AND d.position IS NOT NULL "
       "AND d.num_players IS NOT NULL AND t.raw_text IS NOT NULL "
       "ORDER BY d.tournament_id")
tids = [int(dict(r)["tid"]) for r in conn.execute(_adapt(sql)).fetchall()]
conn.close()

saida = []
for tid in tids:
    if len(saida) >= LIMITE: break
    conn = get_conn()
    row = conn.execute(_adapt("SELECT raw_text, user_id FROM tournaments WHERE id = ?"), (tid,)).fetchone()
    conn.close()
    if not row: continue
    row = dict(row)
    linhas = get_decisions(tid)
    balde = BaldeDeDecisoes(linhas, lambda d: (norm(d.get("street","")), norm(d.get("action_taken",""))))
    for hand in parse_hand_history(row.get("raw_text") or ""):
        if len(saida) >= LIMITE: break
        for di in build_decision_inputs_for_hand(hand):
            if len(saida) >= LIMITE: break
            if di.get("street") not in ("flop","turn","river"): continue
            linha = balde.proxima((norm(di["street"]), norm(di.get("player_action","") or "")))
            if not linha: continue
            n = int(linha.get("num_players") or 0)
            if not (2 <= n <= 10): continue
            cru = (linha.get("position") or "").upper()
            if _mapa_da_mesa(n).get(cru, cru) == cru: continue
            CAP.clear()
            APP._enfileirar_spot_da_decisao(di, float(linha.get("facing_bet") or 0), tid)
            if not CAP or not CAP[-1]["resultado"]: continue
            h, payload = CAP[-1]["resultado"]
            if h in FEITOS: continue
            saida.append({"spot_hash": h, "tournament": tid, "street": linha.get("street"),
                          "assento": cru, "payload": payload})
print("__JSON__" + json.dumps(saida))
'''


def puxar(limite: int):
    """Descobre os payloads do assento EFETIVO, dentro do container. Nao escreve nada em prod."""
    c = _db()
    feitos = [r['spot_hash'] for r in c.execute("SELECT spot_hash FROM spots")]
    codigo = _PUXAR.replace('__LIMITE__', str(int(limite))).replace('__FEITOS__', json.dumps(feitos))
    out = _no_container(codigo)
    marca = out.find('__JSON__')
    if marca < 0:
        sys.exit('o container nao devolveu JSON:\n%s' % out[-1500:])
    novos = json.loads(out[marca + len('__JSON__'):].strip())

    # ── A TRAVA QUE FALTOU, e que custou os primeiros 8 spots ─────────────────────────────
    #
    # O `puxar` roda DENTRO do container, e o container so traduz o assento se a imagem tiver o
    # conserto do AY-29. Codigo e assado na imagem: commitar aqui nao muda nada la (regra 4 da
    # casa). Na primeira tentativa, producao rodava `397007b2` e devolveu payload com o ROTULO DA
    # SALA -- se eu tivesse empurrado, teria gravado no legado achando que era novo.
    #
    # Um lote inteiro sem nenhuma traducao e a assinatura exata desse estado.
    traduzidos = sum(1 for s in novos if json.loads(s['payload']).get('position') != s['assento'])
    if novos and traduzidos == 0:
        sys.exit('NENHUM dos %d spots veio com o assento traduzido. O container de producao ainda '
                 'nao tem o conserto do AY-29 (o codigo e assado na imagem). Faca o deploy antes '
                 'de puxar, senao o mutirao re-solva sob a chave LEGADA.' % len(novos))
    if traduzidos < len(novos):
        print('AVISO: %d de %d spots vieram sem traducao e foram descartados'
              % (len(novos) - traduzidos, len(novos)))
        novos = [s for s in novos if json.loads(s['payload']).get('position') != s['assento']]

    for s in novos:
        c.execute("INSERT OR IGNORE INTO spots (spot_hash, tournament, street, assento, payload) "
                  "VALUES (?,?,?,?,?)",
                  (s['spot_hash'], s['tournament'], s['street'], s['assento'], s['payload']))
    c.commit()
    pend = c.execute("SELECT COUNT(*) n FROM spots WHERE resultado IS NULL").fetchone()['n']
    print('puxados %d spots novos. pendentes de solve: %d' % (len(novos), pend))
    c.close()


# ── Fase 2: resolver aqui, com o Neon dormindo ─────────────────────────────────────────────

def _solver_livre() -> bool:
    """Producao esta usando o solver AGORA? A resposta vem do proprio recurso, nao de estimativa."""
    try:
        req = urllib.request.Request(SOLVER + '/health', headers={'User-Agent': 'GrindLab/mutirao'})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode('utf-8', errors='replace'))
        return int(d.get('active_solves') or 0) == 0
    except Exception:
        return False        # sem resposta, nao avanca: o silencio nao e permissao


_CHAVE = None


def _chave_do_solver() -> str:
    """A chave do solver, buscada por ssh em tempo de execucao e guardada SO na memoria.

    Ela nao vai para arquivo, nao vai para o repositorio e nao precisa ser colada em lugar nenhum.
    O host ja a tem no `.env`; pedir a ele na hora e mais seguro do que ter uma copia por aqui.
    `GTO_SOLVER_API_KEY` no ambiente tem precedencia, para quem quiser rodar sem ssh.
    """
    global _CHAVE
    if _CHAVE:
        return _CHAVE
    _CHAVE = os.environ.get('GTO_SOLVER_API_KEY') or ''
    if not _CHAVE:
        r = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=20', HOST,
             'cd ~/app && docker compose exec -T web printenv GTO_SOLVER_API_KEY'],
            capture_output=True, text=True, timeout=120)
        _CHAVE = (r.stdout or '').strip().splitlines()[-1].strip() if r.stdout.strip() else ''
    if not _CHAVE:
        sys.exit('nao consegui obter a chave do solver (nem do ambiente, nem do host)')
    return _CHAVE


def _solve(payload: dict, timeout=900):
    req = urllib.request.Request(
        SOLVER + '/solve', data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'GrindLab/mutirao',
                 'x-api-key': _chave_do_solver()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', errors='replace'))


def resolver(limite: int):
    c = _db()
    pend = [dict(r) for r in c.execute(
        "SELECT spot_hash, payload FROM spots WHERE resultado IS NULL AND erro IS NULL LIMIT ?",
        (int(limite),))]
    print('a resolver: %d spots (solver em %s)' % (len(pend), SOLVER))
    feitos = falhos = esperas = 0
    for i, s in enumerate(pend, 1):
        while not _solver_livre():
            esperas += 1
            print('  solver ocupado com producao, esperando %ds...' % ESPERA_S)
            time.sleep(ESPERA_S)
        t0 = time.time()
        try:
            res = _solve(json.loads(s['payload']))
            if not res or not res.get('hand_table'):
                raise ValueError('resposta sem hand_table')
            c.execute("UPDATE spots SET resultado=?, solvado_em=datetime('now') WHERE spot_hash=?",
                      (json.dumps(res), s['spot_hash']))
            feitos += 1
        except Exception as e:
            c.execute("UPDATE spots SET erro=? WHERE spot_hash=?", (str(e)[:300], s['spot_hash']))
            falhos += 1
        c.commit()
        if i % 10 == 0 or i == len(pend):
            print('  %d/%d  (%.1fs no ultimo)' % (i, len(pend), time.time() - t0))
    print('resolvidos %d, falhos %d, esperas por producao %d' % (feitos, falhos, esperas))
    c.close()


# ── Fase 3: empurrar para o Neon, de uma vez ──────────────────────────────────────────────

_EMPURRAR = r'''
import json, sys
sys.path.insert(0, "/app")
from database.repositories import insert_gto_nodes, upsert_tree_strategy
from leaklab.gto_utils import compute_tree_hash

LOTE = json.loads("""__ENTRADA__""")
gravados = arvores = 0
for s in LOTE:
    p = json.loads(s["payload"]); res = s["resultado"]
    insert_gto_nodes([{
        "street": p["street"], "position": p["position"], "board": p["board"],
        "hero_hand": p["hero_hand"], "hero_stack_bb": p["hero_stack_bb"],
        "facing_size_bb": p["facing_size_bb"],
        "gto_action": res.get("primary_action"), "gto_frequency": res.get("primary_freq"),
        "exploitability_pct": res.get("exploitability_pct") or res.get("exploitability"),
        "strategy_json": json.dumps(res.get("strategy") or {}),
        "source": "solver_cli",
    }])
    gravados += 1
    if res.get("hand_table") and res.get("actions"):
        try:
            th = compute_tree_hash(p)
            upsert_tree_strategy(th, p["board"], res["actions"], res["hand_table"])
            arvores += 1
        except Exception as e:
            print("arvore falhou: %s" % str(e)[:120])
print("__OK__%d,%d" % (gravados, arvores))
'''


def empurrar(chunk: int, seco: bool):
    c = _db()
    pend = [dict(r) for r in c.execute(
        "SELECT spot_hash, payload, resultado FROM spots "
        "WHERE resultado IS NOT NULL AND empurrado = 0")]
    print('prontos para o Neon: %d spots' % len(pend))
    if seco:
        print('SECO: nada enviado. Rode com --aplicar para escrever.')
        return
    enviados = 0
    for i in range(0, len(pend), chunk):
        bloco = pend[i:i + chunk]
        dados = json.dumps([{'payload': s['payload'], 'resultado': json.loads(s['resultado'])}
                            for s in bloco])
        out = _no_container(_EMPURRAR, entrada=dados)
        if '__OK__' not in out:
            sys.exit('o container nao confirmou a gravacao:\n%s' % out[-1500:])
        g, a = out.split('__OK__')[1].strip().split(',')
        for s in bloco:
            c.execute("UPDATE spots SET empurrado=1 WHERE spot_hash=?", (s['spot_hash'],))
        c.commit()
        enviados += len(bloco)
        print('  bloco %d: %s nos, %s arvores  (total %d/%d)' % (i // chunk + 1, g, a, enviados, len(pend)))
    print('empurrados %d spots' % enviados)
    c.close()


def estado():
    c = _db()
    for k, sql in (('total', "SELECT COUNT(*) n FROM spots"),
                   ('sem solve', "SELECT COUNT(*) n FROM spots WHERE resultado IS NULL AND erro IS NULL"),
                   ('resolvidos', "SELECT COUNT(*) n FROM spots WHERE resultado IS NOT NULL"),
                   ('com erro', "SELECT COUNT(*) n FROM spots WHERE erro IS NOT NULL"),
                   ('ja no Neon', "SELECT COUNT(*) n FROM spots WHERE empurrado = 1")):
        print('  %-12s %d' % (k, c.execute(sql).fetchone()['n']))
    c.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='fase', required=True)
    p1 = sub.add_parser('puxar');    p1.add_argument('--limite', type=int, default=50)
    p2 = sub.add_parser('resolver'); p2.add_argument('--limite', type=int, default=100)
    p3 = sub.add_parser('empurrar')
    p3.add_argument('--chunk', type=int, default=200)
    p3.add_argument('--aplicar', action='store_true')
    sub.add_parser('estado')
    a = ap.parse_args()
    if a.fase == 'puxar':
        puxar(a.limite)
    elif a.fase == 'resolver':
        resolver(a.limite)
    elif a.fase == 'empurrar':
        empurrar(a.chunk, seco=not a.aplicar)
    else:
        estado()


if __name__ == '__main__':
    main()
