/**
 * PokerTableV3 — Mesa visual premium portada do leaklab-replayer-v3.html
 *
 * Dois layers SVG:
 *   1. Background inclinado (perspectiva) — feltro + rail
 *   2. Conteúdo flat — assentos, board, pot, chips (imperativo via refs)
 */
import { useEffect, useRef } from "react";
import type { ReplayStep } from "@/lib/api";

// ── Constants ─────────────────────────────────────────────────────────────────
const CX = 560, CY = 340;
const RX_SEAT = 452, RY_SEAT = 272;
const CARDS_BASE = "/cards/";
const AC_COLORS: Record<string, string> = {
  fold: "#e52020", folds: "#e52020",
  call: "#3aaa52", calls: "#3aaa52",
  raise: "#c9a840", raises: "#c9a840",
  bet: "#c9a840", bets: "#c9a840",
  check: "#5580aa", checks: "#5580aa",
  "all-in": "#ff4040", jam: "#ff4040",
  muck: "#888888", mucks: "#888888",
  show: "#3aaa52", shows: "#3aaa52",
};
// Display label — normalizes plural parser forms to singular
const ACTION_LABEL: Record<string, string> = {
  folds: "fold", checks: "check", calls: "call",
  bets: "bet", raises: "raise", mucks: "muck", shows: "show",
};
const DENOM = [
  { val: 1000, top: "#c9a84c", side: "#957a34" },
  { val: 500,  top: "#9b72c0", side: "#70509a" },
  { val: 100,  top: "#484848", side: "#2c2c2c" },
  { val: 25,   top: "#5580c0", side: "#3d60a0" },
  { val: 5,    top: "#b84040", side: "#8c2a2a" },
  { val: 1,    top: "#b0a040", side: "#887830" },
];
const RANK_FILE: Record<string, string> = { T: "10" };
const SUIT_FILE: Record<string, string> = { s: "S", h: "H", d: "D", c: "C" };

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtAmt(v: number, bb: number, unit: "chips" | "bb"): string {
  if (unit === "bb") {
    const x = Math.round(v / bb * 10) / 10;
    return (x % 1 === 0 ? x.toFixed(0) : x.toFixed(1)) + " BB";
  }
  return Math.round(v).toLocaleString("pt-BR");
}

function breakChips(amount: number) {
  amount = Math.round(amount);
  const chips: typeof DENOM = [];
  for (const d of DENOM) {
    const n = Math.floor(amount / d.val);
    if (n > 0) {
      const show = Math.min(n, 4);
      for (let i = 0; i < show; i++) chips.push(d);
      amount -= n * d.val;
    }
    if (chips.length >= 7) break;
  }
  if (chips.length === 0) chips.push(DENOM[DENOM.length - 1]);
  return chips.slice(0, 7);
}

function chipStackSVG(cx: number, bottomY: number, amount: number): string {
  const RX = 16, RY = 10, CH = 5, N = 4;
  const chips = breakChips(amount);
  if (!chips.length) return "";
  let h = "";
  for (let i = 0; i < chips.length; i++) {
    const { top: topCol, side: sideCol } = chips[i];
    const ty = bottomY - (i + 1) * CH;
    const by2 = bottomY - i * CH;
    h += `<rect x="${cx - RX}" y="${ty}" width="${RX * 2}" height="${CH}" fill="${sideCol}"/>`;
    h += `<ellipse cx="${cx}" cy="${by2}" rx="${RX}" ry="${RY}" fill="${sideCol}"/>`;
    h += `<ellipse cx="${cx}" cy="${ty}" rx="${RX}" ry="${RY}" fill="${topCol}"/>`;
    for (let s = 0; s < N; s++) {
      const a = (s / N) * Math.PI * 2;
      const ex = (cx + Math.cos(a) * (RX - 3.5)).toFixed(1);
      const ey = (ty + Math.sin(a) * (RY - 2.8)).toFixed(1);
      const rot = ((a * 180 / Math.PI) + 90).toFixed(1);
      h += `<ellipse cx="${ex}" cy="${ey}" rx="2.0" ry="1.0" fill="rgba(255,255,255,0.82)" transform="rotate(${rot},${ex},${ey})"/>`;
    }
    h += `<ellipse cx="${cx}" cy="${ty}" rx="${(RX * 0.62).toFixed(1)}" ry="${(RY * 0.62).toFixed(1)}" fill="none" stroke="rgba(255,255,255,0.38)" stroke-width=".9"/>`;
    h += `<ellipse cx="${cx}" cy="${ty}" rx="${(RX * 0.58).toFixed(1)}" ry="${(RY * 0.58).toFixed(1)}" fill="rgba(255,255,255,0.92)"/>`;
  }
  const top = chips[chips.length - 1];
  const label = top.val >= 1000 ? (top.val / 1000) + "K" : String(top.val);
  const topY = bottomY - chips.length * CH;
  h += `<text x="${cx}" y="${topY}" text-anchor="middle" dominant-baseline="middle" fill="#111" font-family="Inter,sans-serif" font-size="9" font-weight="900" letter-spacing=".15">${label}</text>`;
  return h;
}

function cardSVG(code: string | null, x: number, y: number, w = 58, h = 84, faceDown = false): string {
  const rx = Math.round(w * 0.09);
  if (!code || faceDown) {
    const p = 4, id = `cd${x}${y}`;
    return `<clipPath id="${id}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}"/></clipPath>
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="#0c1b36" stroke="#1a3260" stroke-width="1" filter="url(#rp-cshadow)"/>
    <rect x="${x + p}" y="${y + p}" width="${w - p * 2}" height="${h - p * 2}" rx="${rx - 2}" fill="none" stroke="rgba(140,175,255,0.22)" stroke-width=".9" clip-path="url(#${id})"/>
    <text x="${x + w / 2}" y="${y + h * 0.45}" text-anchor="middle" dominant-baseline="central" fill="rgba(140,175,255,0.14)" font-family="sans-serif" font-size="${Math.round(w * 0.40)}" clip-path="url(#${id})">♠</text>`;
  }
  const r = code.slice(0, -1).toUpperCase();
  const suit = code.slice(-1).toLowerCase();
  const rank = RANK_FILE[r] ?? r;
  const file = `${CARDS_BASE}${rank}${SUIT_FILE[suit] ?? suit.toUpperCase()}.svg`;
  return `<image href="${file}" x="${x}" y="${y}" width="${w}" height="${h}" filter="url(#rp-cshadow)" preserveAspectRatio="xMidYMid meet"/>`;
}

function buildLayout(seatNums: number[], heroSeat: number | undefined) {
  const n = seatNums.length;
  const heroIdx = heroSeat !== undefined ? seatNums.indexOf(heroSeat) : n - 1;
  const rotOffset = heroIdx >= 0 ? 180 - (360 / n) * heroIdx : 0;
  const layout: Record<number, { x: number; y: number; dir: "top" | "bottom" }> = {};
  seatNums.forEach((s, i) => {
    const baseAng = -90 + (360 / n) * i + rotOffset;
    const ang = baseAng * Math.PI / 180;
    const x = Math.round(CX + RX_SEAT * Math.cos(ang));
    const y = Math.round(CY + RY_SEAT * Math.sin(ang));
    layout[s] = { x, y, dir: y < CY ? "top" : "bottom" };
  });
  return layout;
}

function renderBoard(cards: string[]): string {
  const W = 68, H = 110, GAP = 8;
  const totalW = 5 * W + 4 * GAP;
  const sx = CX - totalW / 2;
  const y = CY - H / 2 - 6;
  let h = "";
  for (let i = 0; i < 5; i++) {
    const x = sx + i * (W + GAP);
    if (i < cards.length) {
      h += cardSVG(cards[i], x, y, W, H);
    } else {
      h += `<rect x="${x}" y="${y}" width="${W}" height="${H}" rx="4" fill="rgba(0,0,0,0.18)" stroke="rgba(255,255,255,0.07)" stroke-width="1" stroke-dasharray="5 4"/>`;
    }
  }
  return h;
}

function renderPot(pot: number, bb: number, unit: "chips" | "bb"): string {
  if (pot <= 0) return "";
  const cardH = 110, cardY = CY - cardH / 2 - 6;
  const cardBottom = cardY + cardH;
  const potStr = fmtAmt(pot, bb, unit);

  // pill dimensions
  const pillH = 32;
  const pillW = Math.max(110, potStr.length * 12 + 82);
  const pillX = CX - pillW / 2;
  const pillY = cardY - 16 - pillH;
  const textY  = pillY + pillH * 0.66;
  const labelX = CX - pillW / 2 + 14;
  const valueX = CX - pillW / 2 + 50;

  let h = "";
  h += `<rect x="${pillX}" y="${pillY}" width="${pillW}" height="${pillH}" rx="${pillH / 2}"
    fill="rgba(6,12,28,0.76)" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>`;
  h += `<text x="${labelX}" y="${textY}"
    fill="#c9a84c" font-family="Space Grotesk,sans-serif" font-size="10" font-weight="600" letter-spacing="1.8">POT</text>`;
  h += `<text x="${valueX}" y="${textY}"
    fill="rgba(255,255,255,0.96)" font-family="Space Grotesk,sans-serif" font-size="16" font-weight="700">${potStr}</text>`;

  const chipBottomY = cardBottom + 38;
  const potChipX = CX - 36;
  h += chipStackSVG(potChipX, chipBottomY, pot);

  // chip label pill
  const cpW = Math.max(72, potStr.length * 9 + 20);
  const cpX = potChipX - cpW / 2;
  const cpY = chipBottomY + 8;
  h += `<rect x="${cpX}" y="${cpY}" width="${cpW}" height="20" rx="10"
    fill="rgba(6,12,28,0.68)" stroke="rgba(255,255,255,0.10)" stroke-width="1"/>`;
  h += `<text x="${potChipX}" y="${cpY + 14}" text-anchor="middle"
    fill="rgba(255,255,255,0.90)" font-family="Space Grotesk,sans-serif" font-size="12" font-weight="600">${potStr}</text>`;

  return h;
}

function renderSeatsAndChips(
  ev: ReplayStep,
  bb: number,
  unit: "chips" | "bb",
  hero: string,
  aliases: Record<string, string>,
  heroCards: string[],
  revealedCards: Record<string, string[]> = {},
): { seats: string; chips: string } {
  const seatNums = Object.keys(ev.seats).map(Number).sort((a, b) => a - b);
  const heroSeatNum = seatNums.find((sn) => ev.seats[sn]?.player === hero);
  const layout = buildLayout(seatNums, heroSeatNum);
  const bw = 168, bh = 64, brad = 32;
  let seatsHtml = "", chipsHtml = "";

  seatNums.forEach((sn) => {
    const d = ev.seats[sn];
    const pos = layout[sn];
    if (!d || !pos) return;

    const isHero = d.player === hero;
    const isBtn = sn === ev.button;
    const isFolded = (ev.folded ?? []).includes(d.player);
    const isActive = ev.type === "action" && ev.seat === sn;
    const bx = pos.x - bw / 2, by = pos.y - bh / 2;
    // Hero loses at showdown (muck or beat) → same visual fade as fold
    const heroLost = isHero &&
      ev.type === "showdown" &&
      (ev.summary?.seats?.some(s => s.player === d.player && s.outcome === "lost") ?? false);
    const opacity = (isFolded || heroLost) ? 0.28 : 1;

    let bg = "#1c1c1c", bd = "#323232", bdW = 1.5;
    if (isActive) { bd = "#c9a840"; bdW = 3; }
    if (isActive && ev.is_error && ev.is_hero) { bg = "#250808"; bd = "#e52020"; bdW = 3; }

    let html = `<g opacity="${opacity}">`;

    // Cards — always above the pod; bottom 33% hidden behind pod (pod drawn after cards)
    const cw = 64, ch = 96, cg = 6;
    if (isHero && heroCards.length === 2) {
      const cardY = by - Math.round(ch * 0.67);
      html += cardSVG(heroCards[0], pos.x - cw - cg / 2, cardY, cw, ch);
      html += cardSVG(heroCards[1], pos.x + cg / 2, cardY, cw, ch);
    } else if (!isHero && !isFolded) {
      const vw = cw, vh = ch;
      const vcY = by - Math.round(vh * 0.67);
      const seatKey = String(sn);
      if (seatKey in revealedCards) {
        // Showdown: cards known for this seat
        const shown = revealedCards[seatKey];
        if (shown.length >= 2) {
          // Show face-up
          html += cardSVG(shown[0], pos.x - vw - cg / 2, vcY, vw, vh);
          html += cardSVG(shown[1], pos.x + cg / 2, vcY, vw, vh);
        }
        // empty array = mucked: render nothing (player hid their cards)
      } else {
        // Unknown: face-down
        html += cardSVG(null, pos.x - vw - cg / 2, vcY, vw, vh, true);
        html += cardSVG(null, pos.x + cg / 2, vcY, vw, vh, true);
      }
    }

    // Pod
    html += `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="${brad}" fill="${bg}" stroke="${bd}" stroke-width="${bdW}"/>`;
    if (isActive) {
      html += `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="${brad}" fill="rgba(201,168,64,0.07)"/>`;
    }

    // Name — substituído pela ação quando o jogador está atuando
    const displayName = (aliases[d.player] ?? d.player);
    const rawAction = isActive ? (ev.action ?? null) : null;
    const actText = rawAction ? (ACTION_LABEL[rawAction] ?? rawAction).toUpperCase() : null;
    const ac = rawAction ? (AC_COLORS[rawAction] ?? "#888") : null;
    if (actText) {
      // Linha 1: ação com cor
      html += `<text x="${pos.x}" y="${by + 27}" text-anchor="middle" fill="${ac}" font-family="Inter,sans-serif" font-size="${isHero ? 17 : 15}" font-weight="700" letter-spacing=".05">${actText}</text>`;
    } else {
      const maxChars = isHero ? 14 : 13;
      const name = displayName.length > maxChars ? displayName.slice(0, maxChars) + "…" : displayName;
      html += `<text x="${pos.x}" y="${by + 27}" text-anchor="middle" fill="${isHero ? "#ffffff" : "#ddd8d0"}" font-family="Inter,sans-serif" font-size="${isHero ? 17 : 15}" font-weight="${isHero ? 600 : 500}" letter-spacing=".05">${name}</text>`;
    }

    // Stack
    const sv = (ev as unknown as Record<string, Record<string, number>>)["stacks"]?.[sn] ?? d.stack;
    html += `<text x="${pos.x}" y="${by + 48}" text-anchor="middle" fill="${isHero ? "#c9e8ff" : "#c0bab0"}" font-family="Share Tech Mono,monospace" font-size="15" font-weight="600" letter-spacing=".05">${fmtAmt(sv, bb, unit)}</text>`;

    // Bounty badge (PKO tournaments)
    if (d.bounty && d.bounty > 0) {
      const bStr = `$${d.bounty.toFixed(2)}`;
      const bw2 = bStr.length * 6.5 + 14;
      html += `<rect x="${pos.x - bw2 / 2}" y="${by - 22}" width="${bw2}" height="16" rx="8" fill="rgba(245,158,11,0.15)" stroke="rgba(245,158,11,0.50)" stroke-width="1"/>`;
      html += `<text x="${pos.x}" y="${by - 10}" text-anchor="middle" fill="#fbbf24" font-family="Share Tech Mono,monospace" font-size="11" font-weight="700">💀${bStr}</text>`;
    }

    html += "</g>";  // fecha o grupo do seat (com opacity quando folded)
    seatsHtml += html;

    // Dealer button — RENDERIZADO FORA DO GRUPO COM OPACITY pra permanecer
    // visivel quando o BTN folda. Sem opacity wrapper.
    if (isBtn) {
      const heroPosBtn = heroSeatNum !== undefined ? layout[heroSeatNum] : null;
      const isAdjacentBtn = heroPosBtn !== null && Math.abs(pos.y - heroPosBtn.y) < 80;
      // Dealer perto do pod do jogador, mas com folga. perpOff dá separação
      // lateral; t controla quão longe do pod (no eixo player→centro).
      const t = isHero ? 0.28 : isAdjacentBtn ? 0.34 : 0.30;
      const dvx = CX - pos.x, dvy = CY - pos.y;
      const dlen = Math.sqrt(dvx * dvx + dvy * dvy) || 1;
      // perpSign -1 nos dois casos: dealer fica do lado oposto às cartas/bets
      // (visualmente "abaixo e à direita" pra seats no quadrante esquerdo
      // inferior do feltro). Antes hero usava -1 e demais usavam 1 — invertido.
      const perpSign = -1;
      const perpDist = isHero ? 90 : 30;
      const perpX = Math.round(perpSign * (dvy / dlen) * perpDist);
      const perpY = Math.round(perpSign * (-dvx / dlen) * perpDist);
      const dbX = Math.round(pos.x + dvx * t) + perpX;
      // Ajuste vertical fino: dealer sobe 12px (independente da geometria
      // perpendicular, pra não afetar deslocamento horizontal).
      const dbY = Math.round(pos.y + dvy * t) + perpY - 12;
      const dRX = 20, dRY = 12, dCH = 7, dN = 4;
      const dTy = dbY, dBy2 = dbY + dCH;
      let btnHtml = `<rect x="${dbX - dRX}" y="${dTy}" width="${dRX * 2}" height="${dCH}" fill="#b4b4b4"/>`;
      btnHtml += `<ellipse cx="${dbX}" cy="${dBy2}" rx="${dRX}" ry="${dRY}" fill="#b4b4b4"/>`;
      btnHtml += `<ellipse cx="${dbX}" cy="${dTy}" rx="${dRX}" ry="${dRY}" fill="#f4f0ec"/>`;
      for (let s = 0; s < dN; s++) {
        const a = (s / dN) * Math.PI * 2;
        const ex = (dbX + Math.cos(a) * (dRX - 4)).toFixed(1);
        const ey = (dTy + Math.sin(a) * (dRY - 3)).toFixed(1);
        const rot = ((a * 180 / Math.PI) + 90).toFixed(1);
        btnHtml += `<ellipse cx="${ex}" cy="${ey}" rx="2.5" ry="1.2" fill="rgba(55,55,55,0.50)" transform="rotate(${rot},${ex},${ey})"/>`;
      }
      btnHtml += `<ellipse cx="${dbX}" cy="${dTy}" rx="${(dRX * 0.58).toFixed(1)}" ry="${(dRY * 0.58).toFixed(1)}" fill="rgba(255,255,255,0.90)"/>`;
      btnHtml += `<path d="M0,-6 L1.42,-1.95 L5.71,-1.85 L2.29,0.74 L3.53,4.85 L0,2.4 L-3.53,4.85 L-2.29,0.74 L-5.71,-1.85 L-1.42,-1.95 Z" fill="#222" transform="translate(${dbX},${dTy})"/>`;
      seatsHtml += btnHtml;
    }

    // Bet chips — na linha jogador→centro, próximas ao pod, sempre dentro do feltro.
    // No showdown, todas as bets ja foram somadas ao pot e estao fluindo pros
    // vencedores — nao renderiza apostas dos seats pra evitar 'blinds estaticas'.
    const isShowdown = ev.type === "showdown";
    const bet = isShowdown ? 0 : (ev.bets?.[sn] ?? 0);
    if (bet > 0) {
      const dvx = CX - pos.x, dvy = CY - pos.y;
      const blen = Math.sqrt(dvx * dvx + dvy * dvy) || 1;
      // Hero: mais ao centro; jogadores laterais: mais próximos ao pod
      const isSide = !isHero && Math.abs(pos.x - CX) > 80;
      // Seats imediatamente adjacentes ao hero (mesma altura ~) puxados pra frente
      // pra reforçar separação das cartas. Demais seats inferiores ficam default.
      const heroPosT2 = heroSeatNum !== undefined ? layout[heroSeatNum] : null;
      const isAdjT2 = !isHero && pos.dir === "bottom" && heroPosT2 !== null
                       && Math.abs(pos.y - heroPosT2.y) < 80;
      // t2 = fração da distância seat→centro. Menor = bets mais próximas ao
      // pod do jogador. Adjacente ao hero ganha um pouco de avanço (0.42)
      // pra somar ao perpOff lateral e ficar visualmente equilibrado — antes
      // estava 0.72 (quase no pot, longe demais do jogador).
      let t2 = isHero ? 0.46 : isSide ? 0.26 : 0.36;
      if (isAdjT2) t2 = 0.38;
      // Hero: offset perpendicular horário (+28px para a direita do ponto de vista do hero).
      // Seats adjacentes ao hero (parte inferior do feltro, dir='bottom') tambem ganham
      // offset perpendicular pra nao sobrepor as cartas do jogador.
      // Sinal: hero usa anti-horario; vizinhos inferiores usam horario (afastam-se
      // do centro inferior onde o hero está renderizado).
      let perpOffX = 0, perpOffY = 0;
      if (isHero) {
        perpOffX = Math.round((-dvy / blen) * 28);
        perpOffY = Math.round((dvx / blen) * 28);
      } else if (pos.dir === "bottom") {
        // Desvio em direção ao centro só pra seats IMEDIATAMENTE adjacentes ao hero
        // (cartas dele estão na mesma altura). Seats mais distantes (SB/BB num
        // 9-max longe do hero) já estão suficientemente afastados sem offset.
        const heroPos = heroSeatNum !== undefined ? layout[heroSeatNum] : null;
        const isAdjacentToHero = heroPos !== null && Math.abs(pos.y - heroPos.y) < 80;
        if (isAdjacentToHero) {
          // Sign flipped: chip se afasta do hero (esquerdo do hero vai mais
          // pra esquerda; direito do hero, mais pra direita). Antes estava
          // invertido — empurrava em direção ao hero, fichas ficavam centrais.
          const sign = pos.x < CX ? -1 : 1;
          perpOffX = Math.round(sign * (-dvy / blen) * 24);
          perpOffY = Math.round(sign * (dvx / blen) * 24);
        }
      }
      const cx2 = Math.round(pos.x + dvx * t2) + perpOffX;
      const cy2 = Math.round(pos.y + dvy * t2) + perpOffY;
      chipsHtml += chipStackSVG(cx2, cy2, bet);
      const betStr = fmtAmt(bet, bb, unit);
      chipsHtml += `<rect x="${cx2 - 28}" y="${cy2 + 10}" width="56" height="18" rx="9" fill="rgba(0,0,0,0.80)" stroke="rgba(255,255,255,0.15)" stroke-width=".8"/>
                    <text x="${cx2}" y="${cy2 + 23}" text-anchor="middle" fill="#fff" font-family="Share Tech Mono,monospace" font-size="13" font-weight="700">${betStr}</text>`;
    }
  });

  // Winner pot chips — displaced toward each winner at showdown
  if (ev.type === "showdown" && ev.summary?.winners?.length) {
    for (const winner of ev.summary.winners) {
      if (winner.won <= 0) continue;
      const wpos = layout[winner.seat];
      if (!wpos) continue;
      const isWinnerHero = ev.seats[winner.seat]?.player === hero;
      const dvx = CX - wpos.x, dvy = CY - wpos.y;
      const blen = Math.sqrt(dvx * dvx + dvy * dvy) || 1;
      const isSide = !isWinnerHero && Math.abs(wpos.x - CX) > 80;
      // Bottom-side seats avançam mais (t=0.42) pra não sobrepor cartas.
      const heroPosW = heroSeatNum !== undefined ? layout[heroSeatNum] : null;
      const isAdjacentW = !isWinnerHero && heroPosW !== null
                          && Math.abs(wpos.y - heroPosW.y) < 80;
      const t2 = isWinnerHero ? 0.46 : isAdjacentW ? 0.42 : isSide ? 0.26 : 0.36;
      // Perp offset: hero usa horário; vizinhos inferiores movem em direção ao centro
      // (mesma lógica das bets) pra afastar das cartas.
      let offX = 0, offY = 0;
      if (isWinnerHero) {
        offX = Math.round((-dvy / blen) * 28);
        offY = Math.round((dvx / blen) * 28);
      } else if (isAdjacentW) {
        const sign = wpos.x < CX ? 1 : -1;
        offX = Math.round(sign * (-dvy / blen) * 14);
        offY = Math.round(sign * (dvx / blen) * 14);
      }
      const cx2 = Math.round(wpos.x + dvx * t2) + offX;
      const cy2 = Math.round(wpos.y + dvy * t2) + offY;
      chipsHtml += chipStackSVG(cx2, cy2, winner.won);
      const wonStr = fmtAmt(winner.won, bb, unit);
      chipsHtml += `<rect x="${cx2 - 32}" y="${cy2 + 10}" width="64" height="18" rx="9" fill="rgba(0,0,0,0.80)" stroke="rgba(201,168,64,0.35)" stroke-width=".8"/>
                    <text x="${cx2}" y="${cy2 + 23}" text-anchor="middle" fill="#c9a840" font-family="Share Tech Mono,monospace" font-size="13" font-weight="700">+${wonStr}</text>`;
    }
  }

  return { seats: seatsHtml, chips: chipsHtml };
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  step:           ReplayStep;
  hero:           string;
  heroCards:      string[];
  bb:             number;
  betUnit?:       "chips" | "bb";
  playerAliases?: Record<string, string>;
  /** seat_str → cards shown at showdown; empty array = mucked (no cards rendered) */
  revealedCards?: Record<string, string[]>;
}

export function PokerTableV3({ step, hero, heroCards, bb, betUnit = "bb", playerAliases = {}, revealedCards = {} }: Props) {
  const boardRef = useRef<SVGGElement>(null);
  const potRef   = useRef<SVGGElement>(null);
  const seatsRef = useRef<SVGGElement>(null);
  const chipsRef = useRef<SVGGElement>(null);

  useEffect(() => {
    if (!boardRef.current) return;
    boardRef.current.innerHTML = renderBoard(step.board ?? []);
    // Suppress center pot when chips are being displaced to winners
    const hasWinners = step.type === "showdown" && (step.summary?.winners?.length ?? 0) > 0;
    potRef.current!.innerHTML  = hasWinners ? "" : renderPot(step.pot ?? 0, bb, betUnit);
    const { seats, chips } = renderSeatsAndChips(step, bb, betUnit, hero, playerAliases, heroCards, revealedCards);
    seatsRef.current!.innerHTML = seats;
    chipsRef.current!.innerHTML = chips;
  }, [step, bb, betUnit, hero, heroCards, playerAliases, revealedCards]);

  return (
    <div
      className="relative w-full rounded-2xl"
      style={{
        background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)",
        aspectRatio: "16 / 10",
      }}
    >
      {/* Layer 1 — tilted background (felt + rail) — clipped to rounded corners */}
      <div
        className="absolute inset-0 overflow-hidden rounded-2xl"
        style={{ perspective: "1100px", perspectiveOrigin: "50% 0%" }}
      >
        <svg
          viewBox="0 0 1120 630"
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="xMidYMid meet"
          className="w-full h-full block"
          style={{ transform: "rotateX(9deg)", transformOrigin: "50% 60%" }}
        >
          <defs>
            <radialGradient id="bg-felt" cx="48%" cy="38%" r="60%">
              <stop offset="0%"   stopColor="#42b85a" />
              <stop offset="48%"  stopColor="#2d9242" />
              <stop offset="100%" stopColor="#1c6028" />
            </radialGradient>
            <radialGradient id="bg-rail" cx="50%" cy="25%" r="64%">
              <stop offset="0%"   stopColor="#252525" />
              <stop offset="100%" stopColor="#0c0c0c" />
            </radialGradient>
            <radialGradient id="bg-vig" cx="50%" cy="50%" r="62%">
              <stop offset="36%"  stopColor="rgba(0,0,0,0)" />
              <stop offset="100%" stopColor="rgba(0,0,0,0.55)" />
            </radialGradient>
            <filter id="bg-shadow" x="-25%" y="-25%" width="150%" height="150%">
              <feDropShadow dx="0" dy="16" stdDeviation="28" floodColor="#000" floodOpacity=".95" />
            </filter>
          </defs>
          <ellipse cx="562" cy="353" rx="445" ry="245" fill="#000" filter="url(#bg-shadow)" />
          <ellipse cx="560" cy="340" rx="442" ry="240" fill="url(#bg-rail)" />
          <ellipse cx="560" cy="340" rx="442" ry="240" fill="none" stroke="#2c2c2c" strokeWidth="1.2" />
          <ellipse cx="560" cy="340" rx="418" ry="222" fill="none" stroke="#1a1a1a" strokeWidth="5" />
          <ellipse cx="560" cy="340" rx="414" ry="218" fill="url(#bg-felt)" />
          <ellipse cx="560" cy="340" rx="403" ry="207" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="1.5" />
          <ellipse cx="560" cy="340" rx="414" ry="218" fill="url(#bg-vig)" />
          <text x="560" y="351" textAnchor="middle" fill="rgba(255,255,255,0.022)"
                fontFamily="Inter,sans-serif" fontSize="58" fontWeight="800" letterSpacing="16">LEAKLAB</text>
        </svg>
      </div>

      {/* Layer 2 — flat content (seats, board, pot, chips) */}
      <svg
        viewBox="0 0 1120 630"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="xMidYMid meet"
        className="absolute inset-0 w-full h-full block"
        style={{ overflow: "visible" }}
      >
        <defs>
          <filter id="rp-cshadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="1" dy="2" stdDeviation="3" floodColor="#000" floodOpacity=".55" />
          </filter>
        </defs>
        <g ref={boardRef} />
        <g ref={potRef} />
        <g ref={seatsRef} />
        <g ref={chipsRef} />
      </svg>
    </div>
  );
}
