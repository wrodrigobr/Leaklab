# Burst do solver — box extra por hora, criado no pico e destruído ao drenar

O solver base (rede privada, `10.0.0.3`, 8 vCPU, `max_solves=2`) drena ~150–300 spots/h.
Num pico (dia de campanha: 1.822 spots num dia), um segundo box **por hora** dobra a vazão e
custa centavos: a Hetzner cobra por hora arredondada pra cima e **para de cobrar no DELETE**.

A decisão (quando subir/descer) é lógica testada na suíte (`leaklab/burst_solver.py` +
`tests/test_burst_solver.py`); a execução é `backend/scripts/burst_do_solver.py`, rodado no
host do app com o python3 do sistema (só stdlib).

## Setup, uma única vez

1. **Token da API** (só o dono): Console Hetzner → projeto → Security → API Tokens →
   Generate, permissão **Read & Write**. Colar no `~/app/.env` do host:
   `HETZNER_API_TOKEN=...` — o script só lê; o token nunca sai do servidor.
2. **Solver no boot**: no box do solver, o serviço precisa estar habilitado
   (`systemctl enable leaklab-solver` ou equivalente) — o clone só serve se o solver_api
   subir sozinho. O `up` verifica via `/health` e, se o clone não responder em 5min,
   destrói o clone e falha barulhento.
3. **Snapshot-base**: `python3 backend/scripts/burst_do_solver.py snapshot` — acha o box
   pelo IP privado 10.0.0.3 e tira snapshot com label `leaklab-burst-base=1`. Aguardar
   ficar *available* no Console. Refazer o snapshot após qualquer mudança no box base.

## Operação

```bash
python3 backend/scripts/burst_do_solver.py status   # fila, bursts vivos, snapshot
python3 backend/scripts/burst_do_solver.py up       # força 1 burst agora
python3 backend/scripts/burst_do_solver.py down     # destrói todos os bursts (nunca a base)
python3 backend/scripts/burst_do_solver.py tick     # 1 decisão automática
```

`tick` automático (cron do host, a cada 10min):

```
*/10 * * * * cd ~/app && python3 backend/scripts/burst_do_solver.py tick >> ~/burst.log 2>&1
```

## Como funciona por dentro

- `up`: cria server do snapshot (**sem IP público** — só rede privada `grindlab-net`),
  espera `/health`, e sobe um `solver-consumer` extra no host apontado no IP do clone.
  A fila é o Postgres compartilhado com claim atômico — dois consumers nunca pegam o
  mesmo spot; o burst simplesmente drena junto.
- `down`: remove o consumer extra e **deleta** o server (deletar é o que encerra cobrança;
  desligado continua cobrando).
- Limiares (em `leaklab/burst_solver.py`): sobe com `pending >= 400`, desce com
  `pending <= 50` e vida mínima de 20min (anti-flapping). `MAX_BURST = 1`.

## Segurança de destruição

DELETE exige **duas** marcas: label `burst=leaklab` **e** nome `burst-solver-*`. A base e o
app não têm nenhuma das duas. O teste da suíte quebra a regra de decisão de propósito.

## Custo

`cpx41` ≈ €0,05/h. Um pico de 6h de burst ≈ €0,30. O snapshot cobra pelo tamanho
(~€0,01/GB/mês) — um custo fixo pequeno para ter o clone a 5 minutos de distância.
