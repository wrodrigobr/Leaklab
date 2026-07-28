# Deploy da API (Hetzner CX23)

O host `~/app` **é** o checkout deste repositório. `docker-compose.yml` e `deploy/nginx.conf`
moram aqui porque viveram meses só no servidor, e isso custou caro: sem eles versionados, não dava
para responder de fora perguntas básicas — se o consumidor rodava como serviço, se o nginx
apontava para onde deveria — e cada resposta virava um ida-e-volta com o operador.

## Deploy

```bash
cd ~/app && git pull && docker compose up -d --build
```

O código é **assado na imagem** (não é bind-mount), então sem `--build` o container sobe com o
código antigo e o fix "não aparece". Isso já foi diagnosticado como bug mais de uma vez.

O `--build` sem serviço nomeado reconstrói `web` **e** `solver-consumer` — os dois usam a mesma
imagem, e esquecer o segundo deixa os workers de fila rodando código velho.

## Serviços

| serviço | o que faz |
|---|---|
| `web` | gunicorn, 2 workers. Só a API HTTP. |
| `solver-consumer` | drena `gto_solver_queue` **e** `gto_hand_requests`. Sem ele, o dashboard anuncia "spots sendo validados" que ninguém valida. |
| `nginx` | TLS da Cloudflare + proxy para `web`. |

## Por que o login caía depois de todo deploy

Com `proxy_pass http://web:5000;` literal, o nginx resolvia `web` **uma vez**, na carga da config.
Todo `up -d --build` recria o container com IP novo, e o nginx seguia batendo no morto: 502 antes
de chegar na aplicação. Como 502 não carrega cabeçalho CORS, o navegador reportava

```
No 'Access-Control-Allow-Origin' header is present on the requested resource
```

que parece problema de CORS e não é — é a API inalcançável. O sintoma enganava o diagnóstico.

Resolvido no `nginx.conf` com `resolver 127.0.0.11` + `proxy_pass $backend$request_uri`. Os três
detalhes que fazem funcionar estão comentados lá; o mais fácil de errar é omitir o `$request_uri`,
porque o nginx descarta a URI quando o `proxy_pass` usa variável, e aí toda rota cai na raiz.

**Fallback**, se algum dia o proxy voltar a servir 502 depois de um deploy:

```bash
cd ~/app && docker compose restart nginx
```

## Verificação pós-deploy

```bash
cd ~/app && docker compose ps
docker compose exec web python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:5000/health').status)"
docker compose logs --since=10m solver-consumer
```

O log do consumidor deve ser **quieto**: no máximo uma linha a cada 5 minutos. Se um `req_id`
reaparecer de 6 em 6 segundos, o build não pegou (ver a separação de cadências em
`_gto_hand_worker_loop`).

Não há `curl` na imagem — daí o `python -c` acima.

## Cron do host

```
0  3 * * *  expire_subscriptions.py
15 3 * * *  expire_coach_trials.py
```

Ambos escrevem em `/home/deploy/app/cron.log`, que o usuário `deploy` possui.

**Nunca aponte log de cron para `/var/log/`.** Existiu uma linha drenando `gto_hand_requests` a
cada 5 minutos redirecionando para `/var/log/grindlab-hand-drain.log`; o `deploy` não pode criar
arquivo lá, o shell do cron falha ao abrir o redirecionamento e **o comando nunca chega a
executar**. O cron parecia configurado, nunca rodou, e não deixou rastro — porque o rastro era
justamente o arquivo que ele não conseguia escrever. Essa linha foi removida: quem drena aquela
fila agora é o `solver-consumer`.

## Arquivos que continuam só no host

- `.env` — segredos.
- `deploy/cloudflare-ips.conf` — lista de IPs da Cloudflare, regenerada de fora.
- `/etc/ssl/cloudflare/` — certificado de origem.
