"""
academy_catalog.py — catálogo dos módulos da Academia + matcher leak→aula.

O plano de estudo (LLM) descreve cada leak em texto (titulo/conceitos/diagnostico/spot).
Aqui, de forma DETERMINÍSTICA (sem depender do LLM acertar ids), casamos cada card com
o(s) módulo(s) da Academia mais relevantes por palavra-chave e anexamos {id, path}. O
frontend resolve o TÍTULO localizado (via i18n academy.modules.<id>.title) e monta o link.

Regra: no máx. 2 módulos por card, os de maior nº de palavras-chave batidas. Sem match → [].
"""
from __future__ import annotations
import re
import unicodedata

# (id, path, keywords) — keywords em PT, específicas o bastante pra não gerar ruído
# (ex.: push/fold NÃO usa 'fold'/'push' crus, que casariam com qualquer card de fold).
ACADEMY_MODULES = [
    ("pushfold",   "/academy/push-fold", [
        "push/fold", "pushfold", "push-fold", "shove", "stack curto", "stack raso",
        "all-in", "all in", "reshove", "m-ratio", "m ratio", "shove ou fold",
        "12bb", "10bb", "8bb", "6bb"]),
    ("icm",        "/academy/icm", [
        "icm", "bolha", "bubble", "pay jump", "sobrevivencia", "sobreviver",
        "mesa final", "final table", "premiacao", "pressao de risco", "risk premium"]),
    ("multiway",   "/academy/multiway", [
        "multiway", "multi-way", "multi way", "3-way", "3 way", "varios jogadores",
        "pote multiway", "multi-pote", "3 no pote"]),
    ("mdf",        "/academy/mdf", [
        "mdf", "defesa minima", "over-fold", "overfold", "foldar demais",
        "frequencia de defesa", "alpha", "defende pouco"]),
    ("blockers",   "/academy/blockers", ["blocker", "bloqueador", "blockers"]),
    ("combos",     "/academy/combos", ["combinatoria", "combos", "combinacoes", "combo de"]),
    ("bet_sizing", "/academy/bet-sizing", [
        "sizing", "tamanho da aposta", "tamanho de aposta", "overbet", "bet sizing",
        "dimensionar a aposta", "aposta grande", "aposta pequena", "over-bet"]),
    ("board_strength", "/academy/board-strength", [
        "textura", "forca de mao", "forca da mao", "board molhado", "board seco",
        "textura de board", "conexao do board", "leitura de board"]),
    ("showdown",   "/academy/showdown", [
        "showdown", "bluff-catch", "bluff catch", "showdown value", "valor de showdown",
        "mao media", "pagar blefe", "bluffcatcher"]),
    ("position",   "/academy/position", [
        "posicao", "em posicao", "fora de posicao", "oop", "ip", "position",
        "vantagem posicional"]),
    ("exploits",   "/academy/exploits", [
        "exploit", "explorar", "station", "calling station", "nit", "agressor",
        "maniaco", "leitura de vilao", "perfil do vilao", "ajuste vs", "hud"]),
    ("imbalances", "/academy/imbalances", [
        "polaridade", "polarizada", "condensada", "elasticidade", "inelastico",
        "desequilibrio", "cobertura de board"]),
    ("pko",        "/academy/pko", [
        "pko", "bounty", "recompensa", "knockout", "captura de bounty"]),
    ("tournament", "/academy/tournament", [
        "estagio do torneio", "fase do torneio", "estrutura do torneio", "profundidade media"]),
    ("ranges",     "/academy/gto-preflop?scenario=rfi", [
        "rfi", "range de abertura", "open-raise", "open raise", "abrir de", "roubar blind",
        "steal", "3-bet", "3bet", "3-bet pot", "defesa de bb", "defesa do bb", "vs open"]),
    ("math",       "/academy/math", [
        "pot odds", "equity", "outs", "regra do 2", "regra 2/4", "probabilidade",
        "odds implicitas", "matematica", "preco do pote"]),
    ("postflop",   "/academy/postflop", [
        "postflop", "pos-flop", "pos flop", "c-bet", "cbet", "continuation bet",
        "double barrel", "barrel", "flop", "turn", "river", "check-raise", "check raise"]),
    ("draws",      "/academy/draws", [
        "projeto", "projetos", "draw", "semi-blefe", "semi blefe", "semiblefe", "flush draw",
        "sequencia aberta", "gutshot", "combo draw", "outs", "fold equity", "chase"]),
]


def _norm(s: str) -> str:
    """lower + remove acentos (casamento robusto)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def modules_for_card(card: dict, max_n: int = 2) -> list[dict]:
    """Casa um card do plano com até `max_n` módulos da Academia (por nº de keywords batidas)."""
    parts = [card.get("titulo", ""), card.get("diagnostico", ""),
             card.get("spot", ""), card.get("exercicio", "")]
    conceitos = card.get("conceitos") or []
    if isinstance(conceitos, list):
        parts.extend(str(c) for c in conceitos)
    hay = _norm(" ".join(p for p in parts if p))
    if not hay:
        return []
    scored = []
    for idx, (mid, path, kws) in enumerate(ACADEMY_MODULES):
        # limite de palavra (\b): evita 'flop' casar dentro de 'preflop', 'ip' dentro de 'flip', etc.
        hits = sum(1 for kw in kws if re.search(r'\b' + re.escape(_norm(kw)) + r'\b', hay))
        if hits > 0:
            scored.append((hits, idx, mid, path))
    # maior nº de hits primeiro; empate mantém a ordem do catálogo (idx).
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{"id": mid, "path": path} for _h, _i, mid, path in scored[:max_n]]


def attach_academy_modules(plan: dict) -> dict:
    """Anexa `academy_modules` a cada card do plano (in-place) e devolve o plano.
    Determinístico e barato: seguro rodar a cada request, independe do LLM."""
    if not isinstance(plan, dict):
        return plan
    for card in (plan.get("cards") or []):
        if isinstance(card, dict):
            card["academy_modules"] = modules_for_card(card)
    return plan
