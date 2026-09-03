#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""burst_do_solver.py — box de solver SOB DEMANDA na Hetzner (cria no pico, destrói ao drenar).

Roda NO HOST do app (~/app), com o python3 do sistema — só stdlib, sem pip. Decide com a
lógica testada de `leaklab/burst_solver.py`; executa via API da Hetzner + docker do host.

── Uso ─────────────────────────────────────────────────────────────────────────────────────
  python3 backend/scripts/burst_do_solver.py status      # fila, bursts vivos, snapshot
  python3 backend/scripts/burst_do_solver.py snapshot    # tira o snapshot-base do box do solver
  python3 backend/scripts/burst_do_solver.py up          # força subir 1 burst agora
  python3 backend/scripts/burst_do_solver.py down        # destrói TODOS os bursts (nunca a base)
  python3 backend/scripts/burst_do_solver.py tick        # 1 decisão automática (p/ cron ou timer)

── Pré-requisitos (uma vez; ver deploy/burst-solver.md) ────────────────────────────────────
  1. HETZNER_API_TOKEN (Read & Write) no ~/app/.env — o DONO cria e cola; este script só lê.
  2. Snapshot-base: `snapshot` acha o box do solver pelo IP privado (10.0.0.3), tira snapshot
     com label leaklab-burst-base=1. O solver_api PRECISA estar enabled no systemd do box —
     o clone só serve se subir sozinho no boot (o comando `up` verifica via /health e, se o
     clone não responder em 5min, ele mesmo o destrói e falha barulhento).

── Segurança de destruição ─────────────────────────────────────────────────────────────────
  DELETE só em server com label burst=leaklab E nome começando com burst-solver-. A base e o
  app não têm o label; um bug aqui destruiria produção, então a checagem é dupla e o teste da
  suíte quebra a decisão de propósito.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from leaklab.burst_solver import decidir  # noqa: E402

API = 'https://api.hetzner.cloud/v1'
IP_BASE_SOLVER = os.environ.get('LEAKLAB_SOLVER_PRIV_IP', '10.0.0.3')
REDE = os.environ.get('LEAKLAB_HETZNER_NET', 'grindlab-net')
TIPO_BURST = os.environ.get('LEAKLAB_BURST_TYPE', 'cpx41')   # 8 vCPU, como a base
PREFIXO = 'burst-solver-'
LABEL = 'burst=leaklab'
LABEL_SNAPSHOT = 'leaklab-burst-base'


def _token() -> str:
    tok = os.environ.get('HETZNER_API_TOKEN')
    if not tok:
        for linha in open(os.path.expanduser('~/app/.env'), encoding='utf-8'):
            if linha.startswith('HETZNER_API_TOKEN='):
                tok = linha.split('=', 1)[1].strip()
                break
    if not tok:
        sys.exit('HETZNER_API_TOKEN ausente (crie no Console Hetzner e cole no ~/app/.env).')
    return tok


def _api(caminho: str, metodo: str = 'GET', corpo: dict = None) -> dict:
    req = urllib.request.Request(
        API + caminho, method=metodo,
        data=json.dumps(corpo).encode() if corpo else None,
        headers={'Authorization': f'Bearer {_token()}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or '{}')
    except urllib.error.HTTPError as e:
        # Sem isto o 422 vira traceback mudo — a API SEMPRE manda o motivo no corpo.
        corpo_erro = e.read().decode(errors='replace')
        sys.exit(f'API Hetzner {e.code} em {metodo} {caminho}:\n{corpo_erro}')


def _pending() -> int:
    """Fila do solver, perguntada ao banco DENTRO do container web (o host não tem driver)."""
    out = subprocess.run(
        ['docker', 'compose', 'exec', '-T', 'web', 'python', '-c',
         "from database.schema import get_conn; c=get_conn(); "
         "print(dict(c.execute(\"SELECT COUNT(*) n FROM gto_solver_queue WHERE status='pending'\").fetchone())['n'])"],
        capture_output=True, text=True, cwd=os.path.expanduser('~/app'))
    return int(out.stdout.strip().splitlines()[-1])


def _bursts() -> list:
    servers = _api(f'/servers?label_selector={LABEL}').get('servers', [])
    # Checagem DUPLA: label E prefixo do nome. Nunca confiar numa só.
    return [s for s in servers if s['name'].startswith(PREFIXO)]


def _snapshot_base():
    imgs = _api(f'/images?type=snapshot&label_selector={LABEL_SNAPSHOT}=1').get('images', [])
    return max(imgs, key=lambda i: i['created']) if imgs else None


def _ip_privado(server: dict):
    for n in server.get('private_net', []):
        return n.get('ip')
    return None


def _health(ip: str) -> bool:
    try:
        with urllib.request.urlopen(f'http://{ip}:8765/health', timeout=5) as r:
            return json.loads(r.read()).get('status') == 'ok'
    except Exception:
        return False


def cmd_status():
    pend = _pending()
    vivos = _bursts()
    snap = _snapshot_base()
    print(f'pending na fila do solver: {pend}')
    print(f'snapshot-base: {snap["id"] if snap else "NENHUM (rode `snapshot`)"}')
    for s in vivos:
        ip = _ip_privado(s)
        print(f'burst vivo: {s["name"]} (#{s["id"]}) ip={ip} '
              f'health={"ok" if ip and _health(ip) else "SEM RESPOSTA"} criado={s["created"]}')
    if not vivos:
        print('nenhum burst vivo.')


def cmd_snapshot():
    alvo = None
    for s in _api('/servers').get('servers', []):
        if _ip_privado(s) == IP_BASE_SOLVER:
            alvo = s
            break
    if not alvo:
        sys.exit(f'nenhum server com IP privado {IP_BASE_SOLVER} — confira o box do solver.')
    print(f'snapshot do box do solver: {alvo["name"]} (#{alvo["id"]}) — pode levar minutos...')
    r = _api(f'/servers/{alvo["id"]}/actions/create_image', 'POST', {
        'type': 'snapshot', 'description': 'leaklab solver base (burst)',
        'labels': {LABEL_SNAPSHOT: '1'}})
    print(f'snapshot pedido: image #{r["image"]["id"]} (aguarde ficar available no Console)')


def cmd_up():
    snap = _snapshot_base()
    if not snap:
        sys.exit('sem snapshot-base — rode `snapshot` primeiro (e aguarde available).')
    rede = next((n for n in _api('/networks').get('networks', []) if n['name'] == REDE), None)
    if not rede:
        sys.exit(f'rede privada {REDE} não encontrada.')
    nome = f'{PREFIXO}{int(time.time())}'
    print(f'criando {nome} ({TIPO_BURST}) do snapshot #{snap["id"]}...')
    r = _api('/servers', 'POST', {
        'name': nome, 'server_type': TIPO_BURST, 'image': snap['id'],
        'location': 'fsn1', 'networks': [rede['id']],
        'labels': {'burst': 'leaklab'},
        # Sem IP público: o burst só conversa na rede privada. Menos superfície, sem custo de IPv4.
        'public_net': {'enable_ipv4': False, 'enable_ipv6': False}})
    sid = r['server']['id']
    ip = None
    for _ in range(60):   # até 5min para boot + solver_api
        time.sleep(5)
        s = _api(f'/servers/{sid}')['server']
        ip = _ip_privado(s)
        if ip and _health(ip):
            break
    else:
        print('clone NÃO respondeu /health em 5min — destruindo (solver não sobe no boot?).')
        _api(f'/servers/{sid}', 'DELETE')
        sys.exit(1)
    print(f'burst pronto: {nome} ip={ip}. Subindo consumer extra apontado nele...')
    subprocess.run(['docker', 'compose', 'run', '-d', '--rm', '--name', f'burst-consumer-{sid}',
                    '-e', f'GTO_SOLVER_URL=http://{ip}:8765',
                    '-e', 'GTO_SOLVER_CONCURRENCY=2',
                    'solver-consumer'], check=True, cwd=os.path.expanduser('~/app'))
    print('burst OPERANDO: fila compartilhada no Postgres, claim atômico — sem trabalho duplicado.')


def cmd_down():
    vivos = _bursts()
    if not vivos:
        print('nenhum burst para destruir.')
        return
    for s in vivos:
        subprocess.run(['docker', 'rm', '-f', f'burst-consumer-{s["id"]}'],
                       capture_output=True, cwd=os.path.expanduser('~/app'))
        _api(f'/servers/{s["id"]}', 'DELETE')
        print(f'destruído: {s["name"]} (#{s["id"]}) — cobrança encerrada.')


def cmd_tick():
    from datetime import datetime, timezone
    vivos = _bursts()
    minutos = 0.0
    if vivos:
        mais_novo = max(datetime.fromisoformat(s['created']).timestamp() for s in vivos)
        minutos = (datetime.now(timezone.utc).timestamp() - mais_novo) / 60
    d = decidir(_pending(), len(vivos), minutos)
    print(f'decisão: {d.acao} ({d.motivo})')
    if d.acao == 'subir':
        cmd_up()
    elif d.acao == 'descer':
        cmd_down()


if __name__ == '__main__':
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'status').lower()
    {'status': cmd_status, 'snapshot': cmd_snapshot, 'up': cmd_up,
     'down': cmd_down, 'tick': cmd_tick}.get(cmd, cmd_status)()
