# -*- coding: utf-8 -*-
"""Meta semanal declarada pelo aluno (Fase 3 da spec cobranca-proximo-passo.md §6).

A cobrança passa a ser contra o compromisso DELE, não contra um ideal nosso: "você prometeu 3,
treinou em 1". Isso muda a psicologia da mensagem — não é o app cobrando, é o espelho.

── Desvio consciente da spec ─────────────────────────────────────────────────────────────────

A spec dizia "quantas SESSÕES por semana". Medido: `progression_attempts` não tem identidade de
sessão, só carimbos de tempo — não dá para saber onde uma sessão termina e outra começa.
Perguntar em sessões e contar dias seria um número que não responde a pergunta feita, que é
exatamente o tipo de coisa que este projeto não faz.

Então a pergunta é em DIAS e a medida é em DIAS. De quebra, dia é a unidade melhor: treinar 3
vezes numa terça e nada no resto da semana é pior que 3 dias espalhados, e é a mesma tese do SRS
que já sustenta o resto do produto.

── Semana de segunda a domingo, no fuso do ALUNO ─────────────────────────────────────────────

Semana móvel de 7 dias nunca "reseta", e sem reset a meta não é um compromisso, é um saldo. Já a
fronteira precisa ser no fuso do aluno: os carimbos são UTC, e quem treina 21h no Brasil viraria
o dia (e às vezes a semana) errado.
"""
from __future__ import annotations

from datetime import datetime, timedelta

# As opções oferecidas. Três é o padrão sugerido; duas é o piso de quem tem pouca rotina e cinco
# o teto de quem grinda. Mais opções que isto vira formulário, e formulário ninguém responde.
OPCOES = (2, 3, 5)


def _local(iso: str, tz_offset_min: int) -> datetime | None:
    """Carimbo UTC → hora local do aluno. `tz_offset_min` é o offset em minutos (BRT = -180)."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso)[:26].replace(' ', 'T'))
    except ValueError:
        return None
    return dt + timedelta(minutes=tz_offset_min)


def inicio_da_semana(agora: str, tz_offset_min: int = 0) -> str | None:
    """Segunda-feira 00:00 da semana de `agora`, devolvida em ISO LOCAL (não UTC).

    O chamador compara com carimbos já convertidos para local — misturar os dois fusos aqui é
    o jeito clássico de a contagem errar por algumas horas na virada da semana.
    """
    dt = _local(agora, tz_offset_min)
    if dt is None:
        return None
    segunda = (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return segunda.isoformat()


def dias_treinados_na_semana(carimbos: list, agora: str, tz_offset_min: int = 0) -> int:
    """Quantos DIAS distintos desta semana têm pelo menos uma tentativa.

    Distintos de propósito: 40 spots numa terça contam 1, igual a 12 spots numa terça. A meta é
    sobre frequência, e frequência é o que o espaçamento exige.
    """
    ini = inicio_da_semana(agora, tz_offset_min)
    if not ini:
        return 0
    dias = set()
    for c in (carimbos or []):
        dt = _local(c, tz_offset_min)
        if dt is not None and dt.isoformat() >= ini:
            dias.add(dt.date().isoformat())
    return len(dias)


def progresso_semanal(meta: int | None, dias: int) -> dict | None:
    """O par (prometidas, feitas) que viaja no payload. None quando o aluno não declarou meta —
    e None é o sinal de "ainda não perguntamos", que é o que dispara a pergunta na tela."""
    if not meta:
        return None
    return {'prometidas': int(meta), 'feitas': int(dias),
            'cumprida': int(dias) >= int(meta)}


def normalizar_meta(valor) -> int | None:
    """Aceita só o que foi oferecido. Meta vinda de fora da lista (curiosidade ou script) viraria
    um número que a tela não sabe renderizar e que o e-mail cobraria como promessa."""
    # `int(3.7)` daria 3 — truncamento silencioso que transformaria uma entrada ambígua numa
    # promessa que o aluno não fez. Valor não inteiro é recusado, não arredondado.
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    if f != int(f):
        return None
    v = int(f)
    return v if v in OPCOES else None
