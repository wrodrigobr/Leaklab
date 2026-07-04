"""
content_moderation.py — Camada 1: anti-prompt-injection + Camada 2: moderação de texto.

Camada 1: sanitiza inputs antes de qualquer chamada ao LLM.
Camada 2: verifica texto livre (bio, reviews, anotações) contra blocklist local.
"""
from __future__ import annotations
import re
import logging

log = logging.getLogger(__name__)

# ── Camada 1: padrões de prompt injection ─────────────────────────────────────

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+|previous\s+|above\s+)?instructions?",
        r"disregard\s+(all\s+|previous\s+|above\s+)?",
        r"forget\s+(everything|all|your\s+)",
        r"(you are now|act as|pretend (you are|to be))\s",
        r"new\s+(role|persona|instructions?|task|directive)",
        r"(system|assistant|user)\s*:\s",
        r"<\|.*?\|>",
        r"\[INST\]|\[\/INST\]",
        r"###\s*(instruction|system|human|assistant)\s*###",
        # PT-BR variants
        r"ignore\s+(todas?\s+as?\s+)?instruções",
        r"esqueça\s+(tudo|todas|suas?\s+instruções)",
        r"novo\s+(papel|persona|instruções?|tarefa)",
        r"você\s+agora\s+(é|deve\s+ser|age\s+como)",
        r"(finja|simule)\s+(que\s+)?(você\s+é|ser)",
    ]
]

_REPLACEMENT = "[FILTRADO]"


def sanitize_llm_input(text: str, max_len: int = 2000) -> str:
    """
    Remove padrões de prompt injection e trunca ao limite.
    Loga tentativas detectadas para análise.
    """
    if not text:
        return text
    cleaned = text
    found: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            found.append(pattern.pattern)
            cleaned = pattern.sub(_REPLACEMENT, cleaned)
    if found:
        log.warning(
            "Prompt injection attempt detected | patterns=%s | snippet=%.120s",
            found,
            text[:120],
        )
    return cleaned[:max_len]


# ── Camada 2: blocklist de conteúdo ──────────────────────────────────────────

# Termos proibidos em PT-BR e EN. Intencionalmente genérico aqui —
# manter a lista em lowercase; comparação é case-insensitive.
_BLOCKED_TERMS: list[str] = [
    # Ataques / violência explícita
    "matar", "assassinar", "suicídio", "se matar", "kill yourself",
    "death threat",
    # Discurso de ódio / discriminação (suficientemente específico)
    "nazista", "nazi", "fascista", "ku klux", "white power",
    # Spam / scam
    "whatsapp.com", "t.me/", "discord.gg/", "bit.ly/",
    "ganhe dinheiro fácil", "renda extra garantida",
    # Conteúdo adulto explícito
    "pornô", "porno", "xxx", "onlyfans",
]

ModerationResult = tuple[bool, str]  # (is_clean, reason_if_flagged)


def moderate_text(text: str) -> ModerationResult:
    """
    Verifica texto livre contra blocklist local.
    Retorna (True, '') se limpo ou (False, motivo) se flaggeado.
    """
    if not text:
        return True, ""
    lower = text.lower()
    for term in _BLOCKED_TERMS:
        if term in lower:
            log.warning("Content moderation flag | term='%s' | snippet=%.80s", term, text[:80])
            return False, "Conteúdo não permitido detectado"
    return True, ""


# ── Moderação de apelido/username (curto, público) ────────────────────────────
# Leetspeak → letra base, pra normalizar evasões (f0d@ → foda, sh1t → shit).
_LEET = str.maketrans({
    '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't',
    '8': 'b', '@': 'a', '$': 's', '!': 'i', '|': 'i',
})

# Termos ofensivos (PT/EN/ES). Curada e extensível — não é exaustiva; o admin
# consegue limpar o que escapar (o apelido é one-time/travado). Lowercase.
_OFFENSIVE_TERMS: list[str] = [
    # PT
    "caralho", "porra", "buceta", "boceta", "xoxota", "cuzao", "cuzudo",
    "arrombado", "arrombada", "viado", "viadinho", "corno", "piroca",
    "punheta", "escroto", "otario", "babaca", "vagabunda", "filhadaputa",
    "retardado", "mongoloide", "puta", "foda", "fdp", "merda", "bosta",
    # EN
    "fuck", "shit", "bitch", "cunt", "asshole", "dick", "pussy", "nigger",
    "nigga", "faggot", "retard", "whore", "slut", "bastard", "motherfuck",
    "cocksuck", "dickhead",
    # ES
    "mierda", "cabron", "cono", "polla", "joder", "maricon", "pendejo",
    "verga", "gilipollas", "zorra", "culero",
    # geral
    "hitler", "nazista", "nazi",
]


def moderate_handle(handle: str) -> ModerationResult:
    """Modera apelido/username (curto, público). Normaliza leetspeak + separadores,
    depois compara com a lista de termos ofensivos. Pra reduzir falso-positivo
    (ex.: 'reputacao'/'disputa' contêm 'puta'), termos curtos (<5) só batem no INÍCIO
    ou igual; termos longos batem como substring. Retorna (True,'') se limpo."""
    if not handle:
        return True, ""
    norm = re.sub(r"[^a-z]", "", handle.lower().translate(_LEET))
    if not norm:
        return True, ""
    for term in _OFFENSIVE_TERMS:
        hit = (term in norm) if len(term) >= 5 else (norm == term or norm.startswith(term))
        if hit:
            log.warning("Handle moderation flag | term='%s' | handle=%.40s", term, handle[:40])
            return False, "Apelido não permitido"
    return True, ""
