/**
 * PokerTableV3 — Mesa visual premium portada do leaklab-replayer-v3.html
 *
 * Dois layers SVG:
 *   1. Background inclinado (perspectiva) — feltro + rail
 *   2. Conteúdo flat — assentos, board, pot, chips (imperativo via refs)
 */
import { useEffect, useRef } from "react";
import type { ReplayStep } from "@/lib/api";
import logoWordmark from "@/assets/brand/grindlab_final_horizontal.svg";
import logoIcon from "@/assets/brand/grindlab_icon_traced.svg";

// ── Constants ─────────────────────────────────────────────────────────────────
const CX = 560, CY = 340;
const RX_SEAT = 452, RY_SEAT = 272;
const CARDS_BASE = "/cards/";
const AC_COLORS: Record<string, string> = {
  fold: "#9aa0a8", folds: "#9aa0a8",  // cinza neutro, fold é passivo, não erro
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

const _CARD_RATIO = 167.0869141 / 242.6669922;  // proporção L/A do baralho (~0.6886)

function cardSVG(code: string | null, x: number, y: number, w = 58, h = 84, faceDown = false): string {
  // Margem branca UNIFORME: a moldura abraça a imagem na proporção real do baralho.
  // (Preencher o slot todo com preserveAspectRatio=meet deixava letterbox em cima/
  // baixo → borda superior parecia maior que as laterais.)
  const m = Math.max(2, Math.round(w * (faceDown ? 0.06 : 0.045)));
  let iw = w - 2 * m, ih = iw / _CARD_RATIO;        // ajusta pela largura…
  if (ih > h - 2 * m) { ih = h - 2 * m; iw = ih * _CARD_RATIO; }  // …ou pela altura
  iw = Math.round(iw); ih = Math.round(ih);
  const fw = iw + 2 * m, fh = ih + 2 * m;            // moldura = imagem + margem
  const fx = Math.round(x + (w - fw) / 2), fy = Math.round(y + (h - fh) / 2);  // centrada no slot
  const ix = fx + m, iy = fy + m;
  const rx = Math.round(fw * 0.09);
  const irx = Math.max(1, Math.round(rx * 0.6));
  if (!code || faceDown) {
    // Moldura do VERSO em cinza azulado (não branco) — o branco chamava muito
    // atenção contra o fundo escuro. As faces continuam com moldura branca.
    const p = 3, id = `cd${x}${y}`;
    // Logo GrindLab (só o ícone) centralizado no verso, no lugar do antigo ♠.
    const lw = Math.round(iw * 0.6), lh = Math.round(ih * 0.42);
    const lx = ix + Math.round((iw - lw) / 2), ly = iy + Math.round((ih - lh) / 2);
    return `<rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="${rx}" fill="#7c8696" filter="url(#rp-cshadow)"/>
    <clipPath id="${id}"><rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" rx="${irx}"/></clipPath>
    <rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" rx="${irx}" fill="#0c1b36" stroke="#1a3260" stroke-width="1"/>
    <rect x="${ix + p}" y="${iy + p}" width="${iw - p * 2}" height="${ih - p * 2}" rx="${Math.max(1, irx - 2)}" fill="none" stroke="rgba(140,175,255,0.22)" stroke-width=".9" clip-path="url(#${id})"/>
    <image href="${logoIcon}" x="${lx}" y="${ly}" width="${lw}" height="${lh}" preserveAspectRatio="xMidYMid meet" opacity="0.5" clip-path="url(#${id})"/>`;
  }
  const r = code.slice(0, -1).toUpperCase();
  const suit = code.slice(-1).toLowerCase();
  const rank = RANK_FILE[r] ?? r;
  const file = `${CARDS_BASE}${rank}${SUIT_FILE[suit] ?? suit.toUpperCase()}.svg`;
  const cid = `cf${x}${y}`;
  // O contorno cinza foi removido na origem (stroke-width:0 no retângulo de fundo
  // dos SVGs do baralho), então a face é renderizada no tamanho natural — sem
  // recorte nem overpaint que cortavam o valor/naipe do canto.
  return `<rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="${rx}" fill="#ffffff" filter="url(#rp-cshadow)"/>
    <clipPath id="${cid}"><rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" rx="${irx}"/></clipPath>
    <image href="${file}" x="${ix}" y="${iy}" width="${iw}" height="${ih}" preserveAspectRatio="xMidYMid meet" clip-path="url(#${cid})"/>`;
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
  // Só renderiza as cartas REVELADAS — sem placeholders tracejados nos slots vazios
  // (o feltro mostra a marca GrindLab embaixo até o board sair).
  for (let i = 0; i < cards.length && i < 5; i++) {
    const x = sx + i * (W + GAP);
    h += cardSVG(cards[i], x, y, W, H);
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

// ── Posicionamento de bet chips + dealer button ────────────────────────────────
// Geometria validada (scripts/chip_geometry_check.mjs) — 0 sobreposições com pod/cartas/
// board/entre-si em 6/8/9-max e hero em qualquer assento. Princípio:
//  • Bet chips: âncora na borda DISTANTE de (pod ∪ cartas) ao longo do vetor
//    inboard (pod→centro) + GAP fixo. Folga constante em qualquer assento (a fração
//    do centro falhava porque a mesa é oval); pula as cartas dos bottom seats.
//  • Dealer: lateral, colado no pod — 4 candidatos (dir/esq/baixo/cima), escolhe o
//    válido (sem overlap, dentro do felt), preferindo o lado outboard.
const _HW = 84, _HH = 32, _CARD_HW = 64 + 6 / 2, _CH = 96;
const _CLU_UP = 30, _GAP = 14, _DRX = 20, _DRY = 12;
const _BOARD_B = { x1: CX - (5 * 68 + 4 * 8) / 2, y1: CY - 61, x2: CX + (5 * 68 + 4 * 8) / 2, y2: CY + 49 };
// feltro verde ≈ elipse rx=414 ry=218 (bg-felt). Os pods ficam na BORDA/rail (fora
// do feltro), então o dealer precisa vir INBOARD pra dentro do verde. Raios
// contraídos pela folga do botão (~20×19) p/ o botão caber inteiro.
const _RXF = 414 - 24, _RYF = 218 - 22;
function _inFelt(x: number, y: number): boolean {
  return ((x - CX) / _RXF) ** 2 + ((y - CY) / _RYF) ** 2 <= 1;
}

function _farAlong(cBx: number, cBy: number, hwB: number, hhB: number,
                   px: number, py: number, ux: number, uy: number): number {
  return (cBx - px) * ux + (cBy - py) * uy + hwB * Math.abs(ux) + hhB * Math.abs(uy);
}
function _ovl(a: {x1:number;y1:number;x2:number;y2:number}, b: {x1:number;y1:number;x2:number;y2:number}): boolean {
  return a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1;
}
function placeBetAndDealer(px: number, py: number) {
  const dvx = CX - px, dvy = CY - py, len = Math.hypot(dvx, dvy) || 1;
  const ux = dvx / len, uy = dvy / len;            // inboard (pod→centro)
  // Bet chips: borda distante de (pod ∪ cartas) ao longo de u + gap.
  const cardCY = (py - _HH) - Math.round(_CH * 0.67) + _CH / 2;
  const far = Math.max(
    _farAlong(px, py, _HW, _HH, px, py, ux, uy),
    _farAlong(px, cardCY, _CARD_HW, _CH / 2, px, py, ux, uy),
  );
  const chipX = Math.round(px + (far + _GAP + _CLU_UP) * ux);
  const chipY = Math.round(py + (far + _GAP + _CLU_UP) * uy);
  // Dealer: INBOARD (dentro do feltro) + deslocamento lateral pra livrar cartas e
  // fichas. Busca (inboard d × lateral L), contida na elipse do feltro, escolhendo
  // o mais próximo do pod ("colado"). Outboard cairia no rail preto.
  const tx = -uy, ty = ux;  // tangente
  const podB  = { x1: px - _HW, y1: py - _HH, x2: px + _HW, y2: py + _HH };
  const cby   = (py - _HH) - Math.round(_CH * 0.67);
  const cardB = { x1: px - _CARD_HW, y1: cby, x2: px + _CARD_HW, y2: cby + _CH };
  const cluB  = { x1: chipX - 28, y1: chipY - _CLU_UP, x2: chipX + 28, y2: chipY + 28 };
  let best: { dx: number; dy: number; score: number } | null = null;
  for (const d of [40, 54, 68, 84, 100, 116, 132]) {
    for (const L of [0, 50, -50, 78, -78, 106, -106, 136, -136]) {
      const dx = Math.round(px + ux * d + tx * L);
      const dy = Math.round(py + uy * d + ty * L);
      if (!_inFelt(dx, dy)) continue;
      const db = { x1: dx - _DRX, y1: dy - _DRY, x2: dx + _DRX, y2: dy + _DRY + 7 };
      if (_ovl(db, podB) || _ovl(db, cardB) || _ovl(db, cluB) || _ovl(db, _BOARD_B)) continue;
      const score = -Math.hypot(dx - px, dy - py) - Math.abs(L) * 0.12;
      if (!best || score > best.score) best = { dx, dy, score };
    }
  }
  // fallback: inboard puro (raro — só se nada couber)
  if (!best) best = { dx: Math.round(px + ux * 70), dy: Math.round(py + uy * 70), score: 0 };
  return { chipX, chipY, dealerX: best.dx, dealerY: best.dy };
}

// ── HUD estilo Holdem Manager (box de stats por jogador na mesa) ────────────────
type OppProfile = { archetype: string; confidence: string; hands: number; stats: Record<string, number | null> };
const _ARCH_COLOR: Record<string, string> = {
  calling_station: "#fbbf24", nit: "#7dd3fc", tag: "#34d399", lag: "#fb923c", maniac: "#f87171",
};
const HUD_W = 116, HUD_H = 33;
const _ARCH_SHORT: Record<string, string> = {
  calling_station: "Station", nit: "Nit", tag: "TAG", lag: "LAG", maniac: "Maniac",
};
function _hudPct(v: number | null | undefined): string {
  return v == null ? "–" : String(Math.round(v * 100));
}
function _xmlEsc(s: string): string {
  return (s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
/** Box MÍNIMO de HUD (estilo Holdem Manager): arquétipo + VPIP/PFR. O detalhe completo
 *  (todas as stats rotuladas) vem no `<title>` (tooltip nativo) ao passar o mouse. */
function renderHudBox(cx: number, topY: number, prof: OppProfile, tip: string): string {
  const s = prof.stats || {};
  const lowSample = prof.confidence === "insufficient" || prof.archetype === "unknown";
  const col = lowSample ? "#9aa0a8" : (_ARCH_COLOR[prof.archetype] ?? "#9aa0a8");
  const arch = lowSample ? "?" : (_ARCH_SHORT[prof.archetype] ?? prof.archetype);
  const x = cx - HUD_W / 2;
  return `<g style="cursor:help">
    <title>${_xmlEsc(tip)}</title>
    <rect x="${x}" y="${topY}" width="${HUD_W}" height="${HUD_H}" rx="6" fill="rgba(8,14,26,0.95)" stroke="${col}" stroke-width="1.1"/>
    <circle cx="${x + 11}" cy="${topY + 12}" r="3.4" fill="${col}"/>
    <text x="${x + 20}" y="${topY + 15.5}" fill="${col}" font-family="Inter,sans-serif" font-size="11" font-weight="800" letter-spacing=".03">${arch}</text>
    <text x="${x + HUD_W - 8}" y="${topY + 15}" text-anchor="end" fill="#8893a6" font-family="Share Tech Mono,monospace" font-size="9">${prof.hands}h</text>
    <text x="${x + 11}" y="${topY + 28}" font-family="Share Tech Mono,monospace" font-size="10.5">
      <tspan fill="#7e8a9e">VPIP </tspan><tspan fill="#e6edf8" font-weight="700">${_hudPct(s.vpip_pct)}</tspan><tspan fill="#7e8a9e">  PFR </tspan><tspan fill="#e6edf8" font-weight="700">${_hudPct(s.pfr_pct)}</tspan>
    </text>
  </g>`;
}

function renderSeatsAndChips(
  ev: ReplayStep,
  bb: number,
  unit: "chips" | "bb",
  hero: string,
  aliases: Record<string, string>,
  heroCards: string[],
  revealedCards: Record<string, string[]> = {},
  profiles: Record<string, OppProfile> = {},
  showHud: boolean = false,
  hudTips: Record<string, string> = {},
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
    const seatPlace = placeBetAndDealer(pos.x, pos.y);  // âncoras validadas de bet chips + dealer
    // Hero loses at showdown (muck or beat) → same visual fade as fold
    const heroLost = isHero &&
      ev.type === "showdown" &&
      (ev.summary?.seats?.some(s => s.player === d.player && s.outcome === "lost") ?? false);
    // Não escurece no PRÓPRIO step do fold (é a ação ativa, com borda dourada) —
    // senão o texto "FOLD" sai esmaecido. Só apaga nos steps seguintes.
    const opacity = ((isFolded && !isActive) || heroLost) ? 0.28 : 1;

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
      html += `<text x="${pos.x}" y="${by + 26}" text-anchor="middle" fill="${ac}" font-family="Inter,sans-serif" font-size="${isHero ? 15 : 13.5}" font-weight="700" letter-spacing=".05">${actText}</text>`;
    } else {
      // Fonte do nome reduzida (estava grande demais no pod); o limite de chars
      // sobe um pouco já que a fonte menor cabe mais.
      const maxChars = isHero ? 16 : 15;
      const name = displayName.length > maxChars ? displayName.slice(0, maxChars) + "…" : displayName;
      html += `<text x="${pos.x}" y="${by + 26}" text-anchor="middle" fill="${isHero ? "#ffffff" : "#ddd8d0"}" font-family="Inter,sans-serif" font-size="${isHero ? 14 : 12.5}" font-weight="${isHero ? 600 : 500}" letter-spacing=".05">${name}</text>`;
    }

    // Stack
    const sv = (ev as unknown as Record<string, Record<string, number>>)["stacks"]?.[sn] ?? d.stack;
    html += `<text x="${pos.x}" y="${by + 48}" text-anchor="middle" fill="${isHero ? "#c9e8ff" : "#c0bab0"}" font-family="Share Tech Mono,monospace" font-size="15" font-weight="600" letter-spacing=".05">${fmtAmt(sv, bb, unit)}</text>`;

    // Bounty badge (PKO tournaments) — sobe quando há tab de posição (não colidir)
    if (d.bounty && d.bounty > 0) {
      const bStr = `$${d.bounty.toFixed(2)}`;
      const bw2 = bStr.length * 6.5 + 14;
      const byB = d.pos ? by - 32 : by - 22;
      html += `<rect x="${pos.x - bw2 / 2}" y="${byB}" width="${bw2}" height="16" rx="8" fill="rgba(245,158,11,0.15)" stroke="rgba(245,158,11,0.50)" stroke-width="1"/>`;
      html += `<text x="${pos.x}" y="${byB + 12}" text-anchor="middle" fill="#fbbf24" font-family="Share Tech Mono,monospace" font-size="11" font-weight="700">💀${bStr}</text>`;
    }

    html += "</g>";  // fecha o grupo do seat (com opacity quando folded)
    seatsHtml += html;

    // HUD estilo Holdem Manager — box de stats abaixo do pod, p/ vilões com perfil.
    // Fora do grupo com opacity: permanece visível mesmo quando o jogador folda.
    // Só quando há amostra real (VPIP gateado) — sem "–/–/–" poluindo a mesa.
    // SEMPRE abaixo do pod (preferência do usuário), nunca acima.
    if (showHud && !isHero && profiles[d.player]?.stats?.vpip_pct != null) {
      seatsHtml += renderHudBox(pos.x, by + bh + 5, profiles[d.player], hudTips[d.player] ?? "");
    }

    // Position tab — posição GTO (UTG/MP/CO/BTN/SB/BB) na borda superior do pod.
    // RENDERIZADA FORA DO GRUPO COM OPACITY (igual ao dealer button) pra permanecer
    // 100% visível mesmo quando o jogador folda — em análise a posição de quem
    // foldou importa ("quem abriu/foldou do CO?"). Hero em dourado, vilões neutro.
    // O usuário não deveria ter que contar a partir do dealer button.
    if (d.pos) {
      const pW = d.pos.length * 6.6 + 14;
      const pY = by - 9;  // sobre a borda superior do pod
      const pFill   = isHero ? "rgba(201,168,64,0.96)" : "rgba(18,26,42,0.95)";
      const pStroke = isHero ? "#e3c869" : "rgba(255,255,255,0.26)";
      const pText   = isHero ? "#1a1206" : "#e8eefc";
      seatsHtml += `<rect x="${pos.x - pW / 2}" y="${pY}" width="${pW}" height="17" rx="8.5" fill="${pFill}" stroke="${pStroke}" stroke-width="1"/>`;
      seatsHtml += `<text x="${pos.x}" y="${pY + 12.6}" text-anchor="middle" fill="${pText}" font-family="Inter,sans-serif" font-size="10.5" font-weight="800" letter-spacing=".04">${d.pos}</text>`;
    }

    // Dealer button — RENDERIZADO FORA DO GRUPO COM OPACITY pra permanecer
    // visivel quando o BTN folda. Sem opacity wrapper.
    if (isBtn) {
      // Âncora validada (placeBetAndDealer): lateral, colado no pod, sem overlap.
      const dbX = seatPlace.dealerX;
      const dbY = seatPlace.dealerY;
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
      // Âncora validada (placeBetAndDealer): borda distante de (pod ∪ cartas) +
      // gap fixo na direção do centro. Folga consistente, sem tocar pod/cartas.
      const cx2 = seatPlace.chipX;
      const cy2 = seatPlace.chipY;
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
      // Mesma âncora validada das bet chips (borda distante + gap) — fichas do
      // vencedor pousam no mesmo ponto limpo, sem sobrepor pod/cartas.
      const wPlace = placeBetAndDealer(wpos.x, wpos.y);
      const cx2 = wPlace.chipX;
      const cy2 = wPlace.chipY;
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
  /** HUD HM-style: perfil por nome de jogador + flag de exibição + tooltips (nome→texto) */
  profiles?: Record<string, OppProfile>;
  showHud?: boolean;
  hudTips?: Record<string, string>;
}

export function PokerTableV3({ step, hero, heroCards, bb, betUnit = "bb", playerAliases = {}, revealedCards = {}, profiles = {}, showHud = false, hudTips = {} }: Props) {
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
    const { seats, chips } = renderSeatsAndChips(step, bb, betUnit, hero, playerAliases, heroCards, revealedCards, profiles, showHud, hudTips);
    seatsRef.current!.innerHTML = seats;
    chipsRef.current!.innerHTML = chips;
  }, [step, bb, betUnit, hero, heroCards, playerAliases, revealedCards, profiles, showHud, hudTips]);

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
          {/* Marca GrindLab no feltro (exposição de marca) — atrás do board; as cartas
              comunitárias, quando saem, são desenhadas no layer de conteúdo por cima. */}
          <image href={logoWordmark} x="310" y="286" width="500" height="108"
                 preserveAspectRatio="xMidYMid meet" opacity="0.22" />
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
