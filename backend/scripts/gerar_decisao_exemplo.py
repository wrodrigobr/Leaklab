"""Gera a DECISÃO DE EXEMPLO da landing/dashboard vazio a partir de uma mão REAL.

Por que existe
--------------
O exemplo mostrado a quem ainda não subiu arquivo nenhum era escrito à mão: números
plausíveis, uma frase, e nada da evidência que a análise de verdade produz. Quem via aquilo
não via o produto — via uma maquete dele.

Aqui a decisão sai da MESMA pipeline do `/replay` (parser → build_decision_inputs_for_hand →
evaluate_decision → _build_replay_data). O que a landing mostra é, literalmente, o que o
motor produziu para uma mão jogada.

Por que congelado num arquivo, e não servido ao vivo
----------------------------------------------------
A landing é pública e deslogada. Servir ao vivo a mão de um jogador expõe dado dele para
sempre, a cada visita, sem que ele tenha pedido isso. A fixture é gerada uma vez, revisada,
e o que vai para o repositório não tem nick, nem id de torneio, nem id de mão.

O congelamento tem um preço declarado: se o motor mudar, o exemplo NÃO acompanha sozinho.
Rode este script de novo quando quiser realinhar, e confira o diff.

Uso:
    python scripts/gerar_decisao_exemplo.py                  # regrava a fixture
    python scripts/gerar_decisao_exemplo.py --conferir       # só confere, não escreve
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# A mão escolhida. Critérios da escolha, para quem for trocar:
#   - preflop com cobertura GTO real (`preflop_gto.available`), senão o card fica vazio;
#   - erro de verdade (`small_mistake` → nível "Erro"), porque o exemplo tem que mostrar o
#     produto ACHANDO algo, não confirmando um acerto;
#   - stack normal (26bb), não um spot exótico de 2bb que ninguém reconhece;
#   - SEM `open_size_mismatch` (ver o guarda em `conferir`);
#   - o leak mais universal de MTT: foldar demais contra open de posição tardia;
#   - estratégia MISTA (Raise 66% / Call 34%), que mostra mais do produto do que uma barra
#     única de 100% — o exemplo existe para dizer o que a ferramenta sabe fazer.
# É uma mão do próprio dono do produto (user 13), o que resolve o consentimento na origem.
#
# A primeira escolhida foi outra (A2s, BB vs SB, 2.0bb perdidos — o maior EV da amostra) e ela
# foi DESCARTADA por causa do `open_size_mismatch`: o vilão abriu 17bb onde o GTO abre 3bb. A
# range de defesa de 76% é vs open mínimo, então o "defenda 76%" não valia para o que o herói
# enfrentou. Como exemplo de vitrine, seria uma análise com asterisco.
TORNEIO_DB_ID = 151
MAO_ID = "257048419516"
USUARIO = 13

# NÃO usar `backend/data/`: o .gitignore ignora a pasta inteira (por causa do .db local), então
# a fixture nunca chegaria ao repositório nem à imagem — o endpoint responderia vazio em
# produção e ninguém veria falha nenhuma no dev.
DESTINO = os.path.join(os.path.dirname(__file__), "..", "fixtures", "decisao_exemplo.json")

# Só estes campos vão para a fixture. Lista BRANCA, não negra: campo novo do replay não
# vaza para a landing por esquecimento. Nick, id de mão, id de torneio e assentos ficam de fora.
CAMPOS_DA_DECISAO = [
    "type", "street", "action", "is_hero", "is_error", "error_label",
    "best_action", "gto_label", "gto_action", "gto_approx_stack",
    "hand_equity", "equity_source", "pot_odds_equity", "adjusted_required_equity",
    "hero_stack_bb", "m_ratio", "icm_pressure", "icm_tax_pct", "ev_loss_bb",
    "n_active_opponents", "icm_zone_approx", "preflop_gto", "hero_cards", "board",
]


def carregar_step():
    from database.repositories import get_decisions, get_tournament_by_db_id
    from leaklab.parser import parse_pokerstars_file_from_text
    from leaklab.pipeline import build_decision_inputs_for_hand
    from leaklab.decision_engine_v11 import evaluate_decision
    import api.app as app_mod

    t = get_tournament_by_db_id(USUARIO, TORNEIO_DB_ID)
    if not t or not t.get("raw_text"):
        raise SystemExit(f"torneio {TORNEIO_DB_ID} sem raw_text no banco local")

    alvo = next((h for h in parse_pokerstars_file_from_text(t["raw_text"])
                 if str(h.hand_id) == MAO_ID), None)
    if not alvo:
        raise SystemExit(f"mao {MAO_ID} nao encontrada no torneio {TORNEIO_DB_ID}")

    da_mao = [d for d in get_decisions(t["id"]) if str(d.get("hand_id")) == MAO_ID]
    indice_gto = {
        (d.get("street", ""), (d.get("action_taken", "") or "").rstrip("s") or d.get("action_taken", "")):
        {"gto_label": d.get("gto_label"), "gto_action": d.get("gto_action"),
         "facing_bet": d.get("facing_bet"), "gto_depth_capped": d.get("gto_depth_capped")}
        for d in da_mao if d.get("gto_label")
    }

    # Mesmo caminho do /replay: o engine roda AO VIVO (o banco pode ter label de versão antiga).
    vivas = []
    for di in build_decision_inputs_for_hand(alvo):
        r = evaluate_decision(di)
        acao = (r.get("actionTaken", "") or "").rstrip("s") or r.get("actionTaken", "")
        g = indice_gto.get((di["street"], acao), {})
        vivas.append({
            "hand_id": MAO_ID, "street": di["street"],
            "action_taken": r.get("actionTaken", ""), "best_action": r.get("bestAction", ""),
            "label": r["evaluation"]["label"], "score": r["evaluation"]["mistakeScore"],
            "context": di.get("context", {}), "math": di.get("math", {}),
            "thresholds": r.get("thresholds", {}),
            "breakdown": r["evaluation"].get("scoreBreakdown", {}),
            "gto_label": g.get("gto_label"), "gto_action": g.get("gto_action"),
            "gto_depth_capped": 1 if g.get("gto_depth_capped") else 0,
            "facing_bet": g.get("facing_bet"),
            "ev_loss_bb": (r.get("gto") or {}).get("ev_loss_bb"),
            "bet_intent": r.get("bet_intent"), "threebet_intent": r.get("threebet_intent"),
            "reco_rationale": r.get("reco_rationale"),
            "icm_zone_approx": bool(r.get("icm_zone_approx")),
            "_di": di,
        })

    replay = app_mod._build_replay_data(alvo, vivas, t.get("hero", alvo.hero))
    passos = [s for s in replay.get("timeline", [])
              if s.get("is_hero") and s.get("type") == "action" and s.get("street") == "preflop"
              and (s.get("action") or "").lower() not in ("shows", "mucks", "posts")]
    if not passos:
        raise SystemExit("a mao nao produziu decisao de heroi no preflop")
    return passos[0]


def montar_fixture(step):
    fixture = {k: step[k] for k in CAMPOS_DA_DECISAO if k in step and step[k] is not None}
    # Campos estruturais que o tipo ReplayStep exige mas o card não lê. Ficam NEUTROS de
    # propósito: é o que garante que nenhum nick ou pilha de vilão viaje junto.
    fixture.update({
        "type": "action", "desc": "", "hero": "", "seats": {}, "bets": {}, "folded": [],
        "pot": 0, "pot_bb": 0, "bb": 0, "button": 0,
    })
    return fixture


def conferir(fixture):
    """O exemplo só serve se tiver a evidência TODA. Sem isto, a fixture pode ficar pobre
    em silêncio e a landing volta a mostrar meia análise sem ninguém notar."""
    erros = []
    pg = fixture.get("preflop_gto") or {}
    if not pg.get("available"):
        erros.append("preflop_gto.available falso — o card fica sem a evidência principal")
    for campo in ("hand_type", "scenario", "position", "range_pct", "recommended_actions"):
        if not pg.get(campo):
            erros.append(f"preflop_gto.{campo} ausente")
    if not (pg.get("hand_freq") or pg.get("fold_pct")):
        erros.append("sem frequência por ação — não há barras de 'como o GTO joga'")
    if fixture.get("hand_equity") is None:
        erros.append("hand_equity ausente")
    if fixture.get("adjusted_required_equity") is None and fixture.get("pot_odds_equity") is None:
        erros.append("equity necessária ausente")
    if not fixture.get("error_label"):
        erros.append("error_label ausente — o card não teria veredito")
    # O vilão abriu num tamanho que o GTO não abre: a range de defesa mostrada é vs o open
    # MÍNIMO, então ela não descreve o que o herói enfrentou. A análise segue honesta no
    # replay (o card avisa), mas como VITRINE é uma análise com asterisco. A primeira mão
    # escolhida caiu exatamente aqui, e o número bonito de EV quase a fez passar.
    if pg.get("open_size_mismatch"):
        erros.append(f"open_size_mismatch {pg['open_size_mismatch']} — "
                     "a range de defesa não corresponde ao open enfrentado")
    for proibido in ("hero", "seats"):
        if fixture.get(proibido):
            erros.append(f"campo identificável preenchido: {proibido}")
    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conferir", action="store_true", help="não escreve, só valida")
    args = ap.parse_args()

    fixture = montar_fixture(carregar_step())
    problemas = conferir(fixture)
    if problemas:
        for p in problemas:
            print("  FALHA:", p)
        raise SystemExit("fixture reprovada — nada foi escrito")

    pg = fixture["preflop_gto"]
    print(f"  mao {pg['hand_type']} · {pg['position']} vs {pg['vs_position']} · {pg['stack_bucket']}")
    print(f"  jogou {fixture['action']} · GTO {fixture.get('gto_action')} · "
          f"EV perdido {fixture.get('ev_loss_bb')}bb · veredito {fixture['error_label']}")

    if args.conferir:
        print("  ok (nada escrito)")
        return

    destino = os.path.abspath(DESTINO)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"  escrito: {destino}")


if __name__ == "__main__":
    main()
