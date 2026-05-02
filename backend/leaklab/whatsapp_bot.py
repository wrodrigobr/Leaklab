"""
whatsapp_bot.py — BACK-016: Coaching Drills via WhatsApp Business API (Meta Cloud API).

Fluxo:
  1. Usuário manda qualquer mensagem → bot detecta se tem questão pendente
  2. Sem questão pendente → gera MCQ baseado no top leak do jogador
  3. Com questão pendente → corrige a resposta e dá feedback
  4. Usuário não cadastrado → instrução para vincular número na plataforma
"""
from __future__ import annotations
import os
import json
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"

# Questões pendentes em memória: { phone_number: { question, answer, explanation } }
_pending: dict[str, dict] = {}


# ── API Meta ──────────────────────────────────────────────────────────────────

def _token() -> str:
    return os.environ.get("WHATSAPP_TOKEN", "")


def send_text(phone_number_id: str, to: str, text: str) -> bool:
    """Envia mensagem de texto simples via Cloud API."""
    url = f"{GRAPH_URL}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    try:
        r = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=10,
        )
        if not r.ok:
            log.error("WhatsApp send error %s: %s", r.status_code, r.text)
        return r.ok
    except Exception as exc:
        log.error("WhatsApp send exception: %s", exc)
        return False


# ── Dispatcher principal ──────────────────────────────────────────────────────

def handle_incoming(phone_number_id: str, from_number: str, message_text: str) -> None:
    """Ponto de entrada chamado pelo webhook POST."""
    from database.repositories import get_user_by_phone

    text = (message_text or "").strip()
    user = get_user_by_phone(from_number)

    if not user:
        send_text(phone_number_id, from_number, _msg_not_registered())
        return

    # Usuário tem questão pendente → checar se está respondendo
    if from_number in _pending:
        _handle_answer(phone_number_id, from_number, user, text)
        return

    # Qualquer mensagem → gera nova questão
    _send_question(phone_number_id, from_number, user)


def _handle_answer(phone_number_id: str, from_number: str, user: dict, text: str) -> None:
    pending = _pending.get(from_number)
    if not pending:
        _send_question(phone_number_id, from_number, user)
        return

    answer = text.strip().upper().replace(")", "").replace(".", "")

    if answer in ("A", "B", "C", "D", "1", "2", "3", "4"):
        # Normaliza para A-D
        if answer.isdigit():
            answer = chr(ord("A") + int(answer) - 1)

        correct = pending["answer"]
        if answer == correct:
            reply = (
                f"✅ *Correto!*\n\n"
                f"_{pending['explanation']}_\n\n"
                f"Ótimo trabalho, {user['username']}! Digite qualquer mensagem para o próximo exercício."
            )
        else:
            reply = (
                f"❌ *Incorreto.* A resposta certa é *{correct}*.\n\n"
                f"_{pending['explanation']}_\n\n"
                f"Não desanime! Digite qualquer mensagem para tentar outro exercício."
            )
        del _pending[from_number]
    else:
        reply = (
            "Responda com a letra da opção: *A*, *B*, *C* ou *D*.\n\n"
            + pending["question_text"]
        )

    send_text(phone_number_id, from_number, reply)


def _send_question(phone_number_id: str, from_number: str, user: dict) -> None:
    from database.repositories import get_leak_summary

    leaks = get_leak_summary(user["id"])
    if not leaks:
        send_text(
            phone_number_id,
            from_number,
            (
                f"Olá, {user['username']}! 👋\n\n"
                "Você ainda não tem torneios analisados.\n"
                "Importe seu histórico na plataforma para ativar os exercícios personalizados."
            ),
        )
        return

    top_leak = leaks[0]
    question_data = _generate_exercise(user, top_leak)
    if not question_data:
        send_text(phone_number_id, from_number, "Não foi possível gerar um exercício agora. Tente novamente em instantes.")
        return

    _pending[from_number] = question_data
    send_text(phone_number_id, from_number, question_data["question_text"])


# ── Geração de exercício com LLM ──────────────────────────────────────────────

def _generate_exercise(user: dict, leak: dict) -> Optional[dict]:
    """
    Gera uma questão MCQ (A/B/C/D) baseada no top leak do jogador.
    Retorna { question_text, answer, explanation } ou None em caso de falha.
    """
    import anthropic

    spot = leak.get("spot", "")
    avg_score = leak.get("avg_score", 0)
    occurrences = leak.get("n", 1)

    system = (
        "Você é um coach de poker especializado em MTTs. "
        "Crie uma questão de múltipla escolha (A, B, C, D) em português sobre o leak identificado. "
        "Retorne SOMENTE JSON com: question_text (string com a pergunta formatada para WhatsApp, "
        "incluindo as 4 alternativas), answer (letra correta: A, B, C ou D), "
        "explanation (explicação breve da resposta correta, 2-3 frases). "
        "A questão deve ser prática e diretamente aplicável ao jogo."
    )

    user_prompt = (
        f"Jogador: {user['username']}\n"
        f"Leak detectado: {spot} (spot: street/ação)\n"
        f"Frequência: {occurrences} ocorrências\n"
        f"Score médio de erro: {avg_score:.3f} (quanto maior, pior)\n\n"
        "Crie uma questão MCQ prática sobre como corrigir este leak. "
        "Contexto: torneios MTT online, stakes baixos/médios."
    )

    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return _fallback_exercise(leak)

        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text.strip()

        # Remove markdown code block se presente
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        return {
            "question_text": data["question_text"],
            "answer": data["answer"].upper(),
            "explanation": data["explanation"],
        }
    except Exception as exc:
        log.error("Exercise LLM failed: %s", exc)
        return _fallback_exercise(leak)


def _fallback_exercise(leak: dict) -> dict:
    spot = leak.get("spot", "turn/call")
    parts = spot.split("/")
    street = parts[0] if parts else "turn"
    action = parts[1] if len(parts) > 1 else "call"

    return {
        "question_text": (
            f"📚 *Exercício — Leak: {street.upper()} / {action.upper()}*\n\n"
            f"Você está no turn com uma mão marginal e enfrenta um bet de 2/3 do pot. "
            f"Qual a abordagem correta para reduzir o leak de *{action}* no {street}?\n\n"
            f"A) Sempre foldar para preservar stack\n"
            f"B) Avaliar equity vs range do oponente antes de decidir\n"
            f"C) Sempre chamar para manter pressure\n"
            f"D) Re-raise bluff para proteger range\n\n"
            "_Responda com A, B, C ou D_"
        ),
        "answer": "B",
        "explanation": (
            f"No {street}, a decisão deve sempre partir da equity real vs o range do oponente. "
            f"Foldar automaticamente ou chamar indiscriminadamente são as principais fontes do leak de {action}."
        ),
    }


# ── Mensagens fixas ───────────────────────────────────────────────────────────

def _msg_not_registered() -> str:
    return (
        "👋 Olá! Sou o *LeakLabs AI Coach*.\n\n"
        "Para receber exercícios personalizados aqui, "
        "vincule seu número de WhatsApp no perfil da plataforma:\n\n"
        "📱 *leaklabs.ai → Perfil → WhatsApp*\n\n"
        "Ainda não tem conta? Acesse leaklabs.ai e crie a sua grátis."
    )
