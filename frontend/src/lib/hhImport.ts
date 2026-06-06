// hhImport.ts — lê um arquivo de hand history PokerStars de volta pro estado do
// Hand Builder, em modo "continuação": todas as mãos do arquivo viram as mãos
// concluídas e o builder é configurado (mesa/blinds/jogadores/button) a partir da
// ÚLTIMA mão, pronto pra você seguir construindo a próxima. (Reverso parcial do
// hhGenerator — só o cabeçalho/seats da última mão; as mãos ficam raw, sem perda.)
import type { PlayerInput } from "./hhGenerator";

export interface ImportedTournament {
  hands: string[];          // texto raw de cada mão (vira completedHands)
  handId: string;           // id da última mão (o caller incrementa pra próxima)
  tournamentId: string;
  buyIn: string;
  level: string;
  sb: number; bb: number; ante: number;
  maxSeats: number;
  players: PlayerInput[];   // seat, name, stack (em fichas) da última mão
  buttonSeat: number;
  heroName: string;
  heroSeat: number;
}

export function splitHands(text: string): string[] {
  if (!text) return [];
  // Quebra antes de cada "PokerStars Hand #..." preservando o bloco.
  const parts = text.split(/(?=^PokerStars Hand #)/m);
  return parts.map(p => p.trim()).filter(p => /^PokerStars Hand #/.test(p));
}

export function importHandHistory(text: string): ImportedTournament | null {
  const hands = splitHands(text);
  if (!hands.length) return null;
  const last = hands[hands.length - 1];

  const handId       = last.match(/Hand #(\d+)/)?.[1] ?? "100000001";
  const tournamentId = last.match(/Tournament #(\d+)/)?.[1] ?? "999999";
  const buyInM       = last.match(/\$([\d.]+)\+\$?([\d.]+)/);
  const buyIn        = buyInM ? `${buyInM[1]}+${buyInM[2]}` : "";
  const levelM       = last.match(/Level (\w+) \((\d+)\/(\d+)\)/);
  const level        = levelM?.[1] ?? "I";
  const sb           = levelM ? parseInt(levelM[2], 10) : 50;
  const bb           = levelM ? parseInt(levelM[3], 10) : 100;
  const ante         = parseInt(last.match(/posts the ante (\d+)/)?.[1] ?? "0", 10) || 0;
  const maxSeats     = parseInt(last.match(/(\d+)-max/)?.[1] ?? "9", 10);
  const buttonSeat   = parseInt(last.match(/Seat #(\d+) is the button/)?.[1] ?? "1", 10);

  const players: PlayerInput[] = [];
  const seatRe = /^Seat (\d+): (.+?) \((\d+) in chips/gm;
  let m: RegExpExecArray | null;
  while ((m = seatRe.exec(last)) !== null) {
    players.push({ seat: parseInt(m[1], 10), name: m[2].trim(), stack: parseInt(m[3], 10) });
  }
  if (players.length < 2) return null;

  const heroName = last.match(/Dealt to (.+?) \[/)?.[1]?.trim() ?? players[0].name;
  const heroSeat = players.find(p => p.name === heroName)?.seat ?? players[0].seat;

  return {
    hands, handId, tournamentId, buyIn, level, sb, bb, ante, maxSeats,
    players, buttonSeat, heroName, heroSeat,
  };
}
