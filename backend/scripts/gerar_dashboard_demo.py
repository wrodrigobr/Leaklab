"""Gera a FIXTURE do dashboard de demonstração (`/demo`) a partir de dados REAIS.

Por que assim
-------------
O dashboard tem 13 cards com números **interdependentes**: o leak prioritário precisa ser coerente
com o EV perdido, que precisa ser coerente com a cobertura GTO, que precisa ser coerente com a
projeção de carreira. Fabricar esse conjunto à mão erra em silêncio, e um card contradizendo outro
é pior que card nenhum, porque ensina errado.

Derivar de um torneio real dá coerência de graça.

Como
----
Batendo nos **endpoints de verdade**, via `app.test_client()`, e não chamando as funções internas.
Assim a forma do payload é, por construção, a mesma que o frontend consome — se um endpoint mudar
de formato, a fixture regenerada muda junto.

Anonimato
---------
A fixture vai para uma rota PÚBLICA. Nick, nome de torneio e ids sobem por `_ANONIMIZAR` e são
conferidos por `conferir()` antes de qualquer escrita.

Uso:
    python scripts/gerar_dashboard_demo.py --conferir   # levanta e valida, NÃO escreve
    python scripts/gerar_dashboard_demo.py              # regrava a fixture
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mesmo usuário da decisão de exemplo: é o dono do produto, o que resolve o consentimento na
# origem. Ver `scripts/gerar_decisao_exemplo.py`.
USUARIO = 13
DESTINO = os.path.join(os.path.dirname(__file__), "..", "fixtures", "dashboard_demo.json")

# chave na fixture -> rota. A chave é o nome que o frontend usa, não a rota, para o consumo ficar
# legível do lado de lá.
ROTAS = {
    "evolution":         "/history/evolution?days=90",
    "playerStats":       "/metrics/player-stats?days=90",
    "leakRoi":           "/player/leak-roi?days=90",
    "pressureProfile":   "/player/pressure-profile?days=90",
    "confidenceDrift":   "/player/confidence-drift?days=30",
    "dna":               "/player/dna?days=90",
    "leakGraph":         "/player/leak-graph?days=90",
    "career":            "/player/career",
    "cognitiveFailures": "/player/cognitive-failures",
    "strategicTwin":     "/player/strategic-twin",
    "sessionContext":    "/player/session-context",
    "evSummary":         "/player/ev-summary",
    "pendingGtoCount":   "/player/pending-gto-count",
    "gtoAlignment":      "/player/gto-alignment",
    "gtoPosition":       "/player/gto-position",
    "gtoQuality":        "/player/gto-quality",
    "resultsVsGto":      "/player/results-vs-gto",
    "leakFinder":        "/player/leak-finder",
    "tournaments":       "/history/tournaments",
}

# Termos que NÃO podem sair daqui. A varredura é sobre o JSON inteiro serializado, porque nick
# vaza fácil por dentro de narrativa gerada por LLM, não só em campo estruturado.
_PROIBIDOS = ("phpro", "musashibr", "rodrigo")


def _cliente():
    try:
        import flask_cors  # noqa: F401
    except ImportError:
        import unittest.mock as mock
        sys.modules["flask_cors"] = mock.MagicMock()
        sys.modules["flask_cors"].CORS = lambda app, **kw: None
    from api.app import app
    from database.auth import generate_token
    app.config["TESTING"] = True
    return app.test_client(), generate_token(USUARIO, "player")


def coletar():
    cli, token = _cliente()
    cab = {"Authorization": f"Bearer {token}"}
    out, falhas = {}, []
    for chave, rota in ROTAS.items():
        r = cli.get(rota, headers=cab)
        if r.status_code != 200:
            falhas.append(f"{chave} ({rota}) -> HTTP {r.status_code}")
            continue
        out[chave] = r.get_json()
    return out, falhas


def anonimizar(dados):
    """Remove o que identifica. Lista BRANCA nos campos estruturados conhecidos e varredura
    textual no resto — narrativa de LLM não tem esquema para confiar."""
    t = dados.get("tournaments")
    if isinstance(t, dict) and isinstance(t.get("tournaments"), list):
        for i, tor in enumerate(t["tournaments"], start=1):
            tor["tournament_name"] = f"Torneio {i}"
            tor["tournament_id"] = str(100000 + i)
            tor.pop("hero", None)
            tor.pop("user_id", None)
    bruto = json.dumps(dados, ensure_ascii=False)
    for termo in _PROIBIDOS:
        bruto = re.sub(termo, "Jogador", bruto, flags=re.IGNORECASE)
    return json.loads(bruto)


def conferir(dados):
    """Fixture pobre não quebra nada: renderiza meio dashboard e ninguém percebe. É a falha
    silenciosa que interessa aqui, e por isso a conferência exige SUBSTÂNCIA, não presença.

    `{"insufficient_data": true}` passa em qualquer teste de "não-vazio" e produz um dashboard de
    demonstração inteiro dizendo "ainda não dá para afirmar" — o pior resultado possível numa tela
    cujo trabalho é mostrar o que a ferramenta entrega."""
    erros = []
    for chave in ROTAS:
        if chave not in dados:
            erros.append(f"{chave}: ausente")
        elif dados[chave] in (None, {}, []):
            erros.append(f"{chave}: vazio")

    for chave, payload in dados.items():
        if isinstance(payload, dict) and payload.get("insufficient_data") is True:
            erros.append(f"{chave}: insufficient_data=true — o card diria 'sem dado suficiente'")

    tors = (dados.get("tournaments") or {}).get("tournaments") or []
    if len(tors) < 3:
        erros.append(f"só {len(tors)} torneios — o dashboard de demonstração ficaria magro")

    # Os dois cards que carregam a promessa da landing ("achamos onde o EV vazou") não podem vir
    # sem leak nenhum: seria uma demonstração provando o contrário do que vende.
    if not ((dados.get("leakFinder") or {}).get("leaks")):
        erros.append("leakFinder sem leaks — a demonstração nao mostraria o principal")
    if not ((dados.get("leakRoi") or {}).get("leaks")):
        erros.append("leakRoi sem leaks")

    bruto = json.dumps(dados, ensure_ascii=False).lower()
    for termo in _PROIBIDOS:
        if termo in bruto:
            erros.append(f'termo identificavel "{termo}" vazou na fixture')
    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conferir", action="store_true", help="não escreve, só levanta e valida")
    args = ap.parse_args()

    dados, falhas = coletar()
    print(f"  coletados: {len(dados)}/{len(ROTAS)} payloads")
    for f in falhas:
        print("  FALHA NA COLETA:", f)

    dados = anonimizar(dados)
    problemas = conferir(dados)
    for p in problemas:
        print("  REPROVADO:", p)
    if falhas or problemas:
        raise SystemExit("fixture reprovada — nada foi escrito")

    tors = dados["tournaments"]["tournaments"]
    print(f"  {len(tors)} torneios | {(dados['gtoAlignment'] or {}).get('total_decisions')} decisoes | "
          f"{len((dados['leakFinder'] or {}).get('leaks') or [])} leaks")

    if args.conferir:
        print("  ok (nada escrito)")
        return

    destino = os.path.abspath(DESTINO)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"  escrito: {destino} ({os.path.getsize(destino)} bytes)")


if __name__ == "__main__":
    main()
