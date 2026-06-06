import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Download, Play, Trash2, RotateCcw, FileText, ChevronRight, Star, Settings2, Loader2, Undo2, Upload } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { tournaments } from "@/lib/api";
import { importHandHistory } from "@/lib/hhImport";
import { cn } from "@/lib/utils";
import {
  generateHandHistory,
  type HandInput,
  type PlayerInput,
  type HandAction,
  type Street,
  type ActionType,
} from "@/lib/hhGenerator";

const RANKS = ["A","K","Q","J","T","9","8","7","6","5","4","3","2"];
const SUITS: { s: string; label: string; color: string }[] = [
  { s: "s", label: "♠", color: "text-foreground" },
  { s: "h", label: "♥", color: "text-red-400" },
  { s: "d", label: "♦", color: "text-sky-400" },
  { s: "c", label: "♣", color: "text-emerald-400" },
];

// 1bb = 100 chips internamente. Mantém o builder "bb-native": stacks/apostas
// são digitados em bb e convertidos pra fichas só na geração do HH (clean: 2.5bb=250).
const BB_CHIPS = 100;
const TABLE_SIZES = [6, 8, 9] as const;
type TableSize = (typeof TABLE_SIZES)[number];

// Nomes de posição autoritativos — espelham backend hand_state_builder._position_names
// (ordered[0]=SB, [1]=BB, ..., [n-1]=BTN). Garante que o que o builder mostra é
// exatamente o que a análise atribui pelo assento.
function positionNames(n: number): string[] {
  const names: string[] = new Array(n).fill("");
  names[0] = "SB"; names[1] = "BB";
  names[n - 1] = "BTN";
  if (n >= 4) names[n - 2] = "CO";
  if (n >= 6) names[n - 3] = "HJ";
  const utgSeq = ["UTG", "UTG+1", "UTG+2", "MP1", "MP2", "MP3"];
  let ui = 0;
  for (let i = 2; i < n; i++) {
    if (!names[i]) { names[i] = utgSeq[ui] ?? `MP${ui + 1}`; ui++; }
  }
  return names;
}

// ── Card picker ────────────────────────────────────────────────────────────────

function CardPicker({
  selected, onPick, count = 1, disabled = new Set<string>(), label, clearLabel, compact = false,
}: {
  selected: string[];
  onPick: (cards: string[]) => void;
  count: number;
  disabled?: Set<string>;
  label: string;
  clearLabel: string;
  compact?: boolean;
}) {
  const toggle = (card: string) => {
    if (disabled.has(card) && !selected.includes(card)) return;
    if (selected.includes(card)) {
      onPick(selected.filter(c => c !== card));
    } else {
      if (selected.length >= count) onPick([...selected.slice(1), card]);
      else onPick([...selected, card]);
    }
  };
  const wCls = compact ? "w-8 h-11" : "w-9 h-12";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
        <span className="font-mono text-[10px] text-primary">{selected.length}/{count}</span>
        {selected.length > 0 && (
          <button onClick={() => onPick([])} className="ml-auto text-[10px] text-muted-foreground hover:text-foreground">{clearLabel}</button>
        )}
      </div>
      <div className="flex flex-wrap gap-0.5">
        {RANKS.map(r => SUITS.map(s => {
          const card = r + s.s;
          const isSel = selected.includes(card);
          const isDis = disabled.has(card) && !isSel;
          return (
            <button
              key={card}
              data-card={card}
              onClick={() => toggle(card)}
              disabled={isDis}
              className={cn(
                "rounded border font-mono text-xs font-bold flex flex-col items-center justify-center transition-all",
                wCls,
                isSel ? "bg-primary text-primary-foreground border-primary scale-105 shadow-md" :
                isDis ? "bg-muted/20 text-muted-foreground/40 border-border/30 cursor-not-allowed" :
                "bg-card border-border hover:border-primary/60 hover:bg-primary/5",
                !isSel && !isDis && s.color
              )}
            >
              <span className="leading-none">{r}</span>
              <span className="leading-none text-[10px]">{s.label}</span>
            </button>
          );
        }))}
      </div>
    </div>
  );
}

// ── Action button ─────────────────────────────────────────────────────────────

function ActionButton({
  available, onClick, color, children,
}: {
  available: boolean;
  onClick: () => void; color: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={!available}
      className={cn(
        "px-3 py-1.5 rounded-md font-mono text-[11px] font-bold uppercase tracking-wider transition-colors",
        available ? color : "bg-muted/20 text-muted-foreground/40 cursor-not-allowed"
      )}
    >
      {children}
    </button>
  );
}

// chips ↔ BB (UI em bb; HH guarda chips)
const toBB = (chips: number, bb: number): number => Math.round((chips / bb) * 100) / 100;
const fmtBB = (chips: number, bb: number): string => `${toBB(chips, bb).toFixed(toBB(chips, bb) % 1 === 0 ? 0 : 1)}bb`;

// ── Defaults (bb-native: 6-max, 100bb) ──────────────────────────────────────────

const DEFAULT_TABLE: TableSize = 6;
const DEFAULT_STACK_BB = 100;

function buildPlayers(size: TableSize, stackBb: number): PlayerInput[] {
  const names = positionNames(size);
  // assento i (1..N), button no assento N → ordered[0]=seat1=SB ... ordered[N-1]=seatN=BTN.
  return Array.from({ length: size }, (_, k) => ({
    seat: k + 1,
    name: names[k],
    stack: Math.round(stackBb * BB_CHIPS),
  }));
}

const DEFAULTS = {
  // Torneio/metadados (Avançado) — auto-preenchidos; irrelevantes pra recriar um spot.
  handId: "100000001",
  tournamentId: "999999",
  buyIn: "1.00+0.10",
  level: "I",
  sb: BB_CHIPS / 2,   // 0.5bb
  bb: BB_CHIPS,       // 1bb
  ante: 0,
  // Mesa (Simples)
  tableSize: DEFAULT_TABLE as TableSize,
  stackBb: DEFAULT_STACK_BB,
  players: buildPlayers(DEFAULT_TABLE, DEFAULT_STACK_BB),
  buttonSeat: DEFAULT_TABLE,           // BTN no último assento
  heroSeat: DEFAULT_TABLE,             // hero = BTN por padrão
  heroCards: [] as string[],
  actions: [] as HandAction[],
  board: { flop: [] as string[], turn: "", river: "" },
  showWinner: "",
  winAmount: 0,
  completedHands: [] as string[],
};

type BuilderState = typeof DEFAULTS;

const initialState = (): BuilderState => {
  const stored = typeof window !== "undefined" ? localStorage.getItem("handBuilderDraft") : null;
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      return {
        ...DEFAULTS,
        ...parsed,
        players:        Array.isArray(parsed.players) && parsed.players.length ? parsed.players : DEFAULTS.players,
        heroCards:      Array.isArray(parsed.heroCards)      ? parsed.heroCards      : DEFAULTS.heroCards,
        actions:        Array.isArray(parsed.actions)        ? parsed.actions        : DEFAULTS.actions,
        completedHands: Array.isArray(parsed.completedHands) ? parsed.completedHands : DEFAULTS.completedHands,
        board: {
          flop:  Array.isArray(parsed?.board?.flop) ? parsed.board.flop : DEFAULTS.board.flop,
          turn:  parsed?.board?.turn ?? "",
          river: parsed?.board?.river ?? "",
        },
      };
    } catch { /* fall through */ }
  }
  return DEFAULTS;
};

export default function HandBuilder() {
  const { t } = useTranslation("handbuilder");
  const navigate = useNavigate();
  const [state, setState] = useState(initialState);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeErr, setAnalyzeErr] = useState("");
  const [importErr, setImportErr] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Histórico pra UNDO: snapshot do estado ANTES de cada mutação discreta (ação,
  // carta, próxima mão, carregar arquivo…). undo() restaura o último snapshot.
  const historyRef = useRef<BuilderState[]>([]);
  const [undoDepth, setUndoDepth] = useState(0);
  const snapshot = () => {
    historyRef.current.push(state);
    if (historyRef.current.length > 60) historyRef.current.shift();
    setUndoDepth(historyRef.current.length);
  };
  const undo = () => {
    const prev = historyRef.current.pop();
    if (!prev) return;
    setState(prev);
    setUndoDepth(historyRef.current.length);
  };

  useEffect(() => {
    localStorage.setItem("handBuilderDraft", JSON.stringify(state));
  }, [state]);

  const update = <K extends keyof BuilderState>(key: K, val: BuilderState[K]) =>
    setState(s => ({ ...s, [key]: val }));

  // Carrega um arquivo .txt de hand history pra CONTINUAR: as mãos do arquivo viram
  // as concluídas e a mesa/blinds/jogadores/button são lidos da última mão, prontos
  // pra próxima (button rotaciona, hand_id +1).
  const onLoadFile = async (file: File | null) => {
    setImportErr("");
    if (!file) return;
    const text = await file.text();
    const imp = importHandHistory(text);
    if (!imp) { setImportErr(t("import.error")); return; }
    snapshot();
    const seatNums = imp.players.map(p => p.seat).sort((a, b) => a - b);
    const bIdx = seatNums.indexOf(imp.buttonSeat);
    const nextBtn = seatNums[(bIdx + 1) % seatNums.length] ?? imp.buttonSeat;
    const uiSize = ([6, 8, 9] as number[]).includes(imp.maxSeats) ? imp.maxSeats : imp.players.length;
    const heroStack = imp.players.find(p => p.seat === imp.heroSeat)?.stack ?? imp.players[0].stack;
    setState(s => ({
      ...s,
      completedHands: imp.hands,
      handId: String(Number(imp.handId) + 1),
      tournamentId: imp.tournamentId,
      buyIn: imp.buyIn || s.buyIn,
      level: imp.level,
      sb: imp.sb, bb: imp.bb, ante: imp.ante,
      tableSize: uiSize as TableSize,
      stackBb: Math.max(1, Math.round(heroStack / imp.bb)),
      players: imp.players,
      buttonSeat: nextBtn,
      heroSeat: imp.heroSeat,
      heroCards: [], actions: [],
      board: { flop: [], turn: "", river: "" },
      showWinner: "", winAmount: 0,
    }));
  };

  const heroPlayer = state.players.find(p => p.seat === state.heroSeat);
  const foldedPlayers = useMemo(() =>
    new Set(state.actions.filter(a => a.action === "fold").map(a => a.player)),
    [state.actions]
  );

  // Ordem clockwise a partir do SB (depois do button): [SB, BB, UTG, ..., BTN]
  const clockwiseFromSb = useMemo<PlayerInput[]>(() => {
    if (state.players.length === 0) return [];
    const seatNums = state.players.map(p => p.seat).sort((a, b) => a - b);
    const btnIdx = seatNums.indexOf(state.buttonSeat);
    if (btnIdx === -1) return state.players;
    const ordered: PlayerInput[] = [];
    for (let i = 1; i <= seatNums.length; i++) {
      const seat = seatNums[(btnIdx + i) % seatNums.length];
      const p = state.players.find(x => x.seat === seat);
      if (p) ordered.push(p);
    }
    return ordered;
  }, [state.players, state.buttonSeat]);

  // Posição autoritativa (mesma lógica do backend) pelo índice clockwise.
  const positionOf = (player: PlayerInput): string => {
    const idx = clockwiseFromSb.findIndex(p => p.seat === player.seat);
    if (idx === -1) return "";
    return positionNames(clockwiseFromSb.length)[idx] ?? "";
  };

  const currentStreet: Street = useMemo(() => {
    if (state.board.river) return "river";
    if (state.board.turn)  return "turn";
    if (state.board.flop.length === 3) return "flop";
    return "preflop";
  }, [state.board]);

  const currentActor = useMemo<PlayerInput | null>(() => {
    if (clockwiseFromSb.length < 2) return null;
    const active = clockwiseFromSb.filter(p => !foldedPlayers.has(p.name));
    if (active.length <= 1) return null;

    const streetActions = state.actions.filter(a => a.street === currentStreet);
    if (streetActions.length === 0) {
      if (currentStreet === "preflop") return active[2 % active.length] ?? active[0];
      return active[0];
    }
    const lastActor = streetActions[streetActions.length - 1].player;
    const lastIdxFull = clockwiseFromSb.findIndex(p => p.name === lastActor);
    const startFrom = lastIdxFull >= 0 ? lastIdxFull : -1;
    for (let i = 1; i <= clockwiseFromSb.length; i++) {
      const candidate = clockwiseFromSb[(startFrom + i + clockwiseFromSb.length) % clockwiseFromSb.length];
      if (!foldedPlayers.has(candidate.name)) return candidate;
    }
    return active[0];
  }, [clockwiseFromSb, foldedPlayers, currentStreet, state.actions]);

  const maxBetThisStreet = useMemo(() => {
    const streetActions = state.actions.filter(a => a.street === currentStreet);
    const blindContext = currentStreet === "preflop";
    let maxBet = blindContext ? state.bb : 0;
    const totalByPlayer = new Map<string, number>();
    if (blindContext) {
      const sbP = clockwiseFromSb[0]; const bbP = clockwiseFromSb[1];
      if (sbP) totalByPlayer.set(sbP.name, state.sb);
      if (bbP) totalByPlayer.set(bbP.name, state.bb);
    }
    for (const a of streetActions) {
      if (a.action === "fold" || a.action === "check") continue;
      const v = a.amount ?? 0;
      totalByPlayer.set(a.player, Math.max(totalByPlayer.get(a.player) ?? 0, v));
      if (v > maxBet) maxBet = v;
    }
    return { maxBet, totalByPlayer };
  }, [state.actions, currentStreet, state.sb, state.bb, clockwiseFromSb]);

  const facing = useMemo(() => {
    if (!currentActor) return { invested: 0, toCall: 0, facingBet: false };
    const invested = maxBetThisStreet.totalByPlayer.get(currentActor.name) ?? 0;
    const toCall = Math.max(0, maxBetThisStreet.maxBet - invested);
    return { invested, toCall, facingBet: toCall > 0 };
  }, [currentActor, maxBetThisStreet]);

  // Pote no momento da ação do currentActor (em fichas): antes + blinds + maior
  // comprometido por jogador em cada street até a atual (inclui as apostas já feitas
  // nesta street). Base dos atalhos de sizing pot-relative.
  const potBefore = useMemo(() => {
    let pot = state.ante * state.players.length;
    const streets: Street[] = ["preflop", "flop", "turn", "river"];
    for (const st of streets) {
      const committed = new Map<string, number>();
      if (st === "preflop") {
        if (clockwiseFromSb[0]) committed.set(clockwiseFromSb[0].name, state.sb);
        if (clockwiseFromSb[1]) committed.set(clockwiseFromSb[1].name, state.bb);
      }
      for (const a of state.actions.filter(x => x.street === st)) {
        if (a.action === "fold" || a.action === "check") continue;
        committed.set(a.player, Math.max(committed.get(a.player) ?? 0, a.amount ?? 0));
      }
      for (const v of committed.values()) pot += v;
      if (st === currentStreet) break;
    }
    return pot;
  }, [state.actions, state.ante, state.players.length, state.sb, state.bb, clockwiseFromSb, currentStreet]);

  const streetComplete = useMemo<boolean>(() => {
    const active = clockwiseFromSb.filter(p => !foldedPlayers.has(p.name));
    if (active.length <= 1) return true;
    const streetActions = state.actions.filter(a => a.street === currentStreet);
    for (const p of active) {
      const playerActions = streetActions.filter(a => a.player === p.name);
      if (playerActions.length === 0) return false;
      const last = playerActions[playerActions.length - 1];
      if (last.action === "allin") continue;
      if (last.action === "fold")  continue;
      const invested = maxBetThisStreet.totalByPlayer.get(p.name) ?? 0;
      if (invested < maxBetThisStreet.maxBet) return false;
    }
    return true;
  }, [clockwiseFromSb, foldedPlayers, state.actions, currentStreet, maxBetThisStreet]);

  const handComplete = useMemo<boolean>(() => {
    const active = clockwiseFromSb.filter(p => !foldedPlayers.has(p.name));
    if (active.length <= 1) return true;
    return streetComplete && currentStreet === "river";
  }, [clockwiseFromSb, foldedPlayers, streetComplete, currentStreet]);

  const pendingBoardStreet: Street | null = useMemo(() => {
    if (!streetComplete || handComplete) return null;
    if (currentStreet === "preflop" && state.board.flop.length !== 3) return "flop";
    if (currentStreet === "flop"    && !state.board.turn)             return "turn";
    if (currentStreet === "turn"    && !state.board.river)            return "river";
    return null;
  }, [streetComplete, handComplete, currentStreet, state.board]);

  const usedCards = useMemo(() => {
    const all = new Set<string>();
    state.heroCards.forEach(c => all.add(c));
    state.board.flop.forEach(c => all.add(c));
    if (state.board.turn)  all.add(state.board.turn);
    if (state.board.river) all.add(state.board.river);
    return all;
  }, [state.heroCards, state.board]);

  // ── Position-first setup ────────────────────────────────────────────────────

  // Regera a mesa pro tamanho dado (descarta a mão atual). Usado pelos botões 6/8/9.
  const setTableSize = (size: TableSize) => {
    const hasContent = state.actions.length > 0 || state.heroCards.length > 0;
    if (hasContent && !confirm(t("setup.confirmResize"))) return;
    snapshot();
    const players = buildPlayers(size, state.stackBb);
    setState(s => ({
      ...s,
      tableSize: size,
      players,
      buttonSeat: size,
      heroSeat: size,
      heroCards: [],
      actions: [],
      board: { flop: [], turn: "", river: "" },
      showWinner: "",
      winAmount: 0,
    }));
  };

  const applyStackToAll = (stackBb: number) => {
    setState(s => ({
      ...s,
      stackBb,
      players: s.players.map(p => ({ ...p, stack: Math.round(stackBb * BB_CHIPS) })),
    }));
  };

  const editPlayer = (seat: number, patch: Partial<PlayerInput>) => {
    update("players", state.players.map(p => p.seat === seat ? { ...p, ...patch } : p));
  };
  const setPlayerStackBb = (seat: number, stackBb: number) =>
    editPlayer(seat, { stack: Math.round(Math.max(0, stackBb) * BB_CHIPS) });

  const addAction = (action: ActionType, player: string, amount?: number) => {
    snapshot();
    update("actions", [...state.actions, { player, street: currentStreet, action, amount }]);
  };

  const clearCurrentHand = () => {
    const hasContent = state.actions.length > 0 || state.heroCards.length > 0
      || state.board.flop.length > 0 || state.board.turn || state.board.river
      || state.showWinner || state.winAmount > 0;
    if (hasContent && !confirm(t("actions.confirmClear"))) return;
    snapshot();
    setState(s => ({
      ...s,
      heroCards: [], actions: [],
      board: { flop: [], turn: "", river: "" },
      showWinner: "", winAmount: 0,
    }));
  };

  // ── HH preview ──────────────────────────────────────────────────────────────

  const handInput: HandInput | null = useMemo(() => {
    if (!heroPlayer || state.players.length < 2 || state.heroCards.length !== 2) return null;
    return {
      handId: state.handId,
      tournamentId: state.tournamentId,
      buyIn: state.buyIn,
      level: state.level,
      sb: state.sb, bb: state.bb, ante: state.ante,
      maxSeats: state.tableSize,
      players: state.players,
      buttonSeat: state.buttonSeat,
      heroName: heroPlayer.name,
      heroCards: state.heroCards.join(" "),
      actions: state.actions,
      board: {
        flop: state.board.flop.length === 3 ? state.board.flop : undefined,
        turn: state.board.turn || undefined,
        river: state.board.river || undefined,
      },
      winner: state.showWinner && state.winAmount > 0
        ? { player: state.showWinner, amount: state.winAmount }
        : undefined,
    };
  }, [state, heroPlayer]);

  const hhText = handInput ? generateHandHistory(handInput) : "";
  const fullHhText = useMemo(() => {
    const parts = [...state.completedHands];
    if (hhText) parts.push(hhText);
    return parts.join("\n\n\n");
  }, [state.completedHands, hhText]);

  const exportTxt = () => {
    if (!fullHhText) return;
    const blob = new Blob([fullHhText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `tournament_${state.tournamentId}.txt`;
    a.click(); URL.revokeObjectURL(url);
  };

  const nextHand = () => {
    if (!hhText) return;
    snapshot();
    const invested = new Map<string, number>();
    state.players.forEach(p => invested.set(p.name, state.ante));
    if (clockwiseFromSb[0]) invested.set(clockwiseFromSb[0].name, (invested.get(clockwiseFromSb[0].name) ?? 0) + state.sb);
    if (clockwiseFromSb[1]) invested.set(clockwiseFromSb[1].name, (invested.get(clockwiseFromSb[1].name) ?? 0) + state.bb);
    const byPlayerStreet = new Map<string, number>();
    for (const a of state.actions) {
      if (a.action === "fold" || a.action === "check") continue;
      const k = `${a.street}|${a.player}`;
      const prev = byPlayerStreet.get(k) ?? 0;
      const v = a.amount ?? 0;
      if (v > prev) {
        invested.set(a.player, (invested.get(a.player) ?? 0) + (v - prev));
        byPlayerStreet.set(k, v);
      }
    }
    if (clockwiseFromSb[0]) {
      const k = `preflop|${clockwiseFromSb[0].name}`;
      if (byPlayerStreet.has(k)) invested.set(clockwiseFromSb[0].name, (invested.get(clockwiseFromSb[0].name) ?? 0) - state.sb);
    }
    if (clockwiseFromSb[1]) {
      const k = `preflop|${clockwiseFromSb[1].name}`;
      if (byPlayerStreet.has(k)) invested.set(clockwiseFromSb[1].name, (invested.get(clockwiseFromSb[1].name) ?? 0) - state.bb);
    }
    // Carryover de stacks só quando há vencedor+pote (tracking de torneio real).
    // Sem vencedor (comum ao recriar de vídeo), mantém os stacks — você ajusta
    // por mão pelas posições. Evita "sumir" fichas sem ninguém coletar.
    const hasWinner = !!state.showWinner && state.winAmount > 0;
    const updatedPlayers = hasWinner
      ? state.players.map(p => {
          const lost = invested.get(p.name) ?? 0;
          const won  = state.showWinner === p.name ? state.winAmount : 0;
          return { ...p, stack: Math.max(0, p.stack - lost + won) };
        })
      : state.players;
    const seatNums = updatedPlayers.map(p => p.seat).sort((a, b) => a - b);
    const btnIdx = seatNums.indexOf(state.buttonSeat);
    const nextBtn = seatNums[(btnIdx + 1) % seatNums.length] ?? state.buttonSeat;
    const nextHandId = String(Number(state.handId) + 1);
    setState(s => ({
      ...s,
      completedHands: [...s.completedHands, hhText],
      handId: nextHandId,
      players: updatedPlayers,
      buttonSeat: nextBtn,
      heroCards: [], actions: [],
      board: { flop: [], turn: "", river: "" },
      showWinner: "", winAmount: 0,
    }));
  };

  const resetAll = () => {
    if (!confirm(t("preview.confirmReset"))) return;
    localStorage.removeItem("handBuilderDraft");
    setState(initialState());
  };

  // Analisa o torneio recriado e abre o resultado. O builder é DONO do seu
  // tournament_id, então re-analisar a mesma sessão deve SOBRESCREVER (não dar 409
  // "já importado") — apaga o torneio anterior com esse id antes de reimportar.
  const analyzeNow = async () => {
    if (!fullHhText || analyzing) return;
    setAnalyzing(true); setAnalyzeErr("");
    try {
      await tournaments.deleteOne(state.tournamentId).catch(() => {});
      const res = await tournaments.analyze(fullHhText);
      navigate(`/tournaments/${res.tournament_id}`);
    } catch (e) {
      setAnalyzeErr(e instanceof Error ? e.message : t("preview.analyzeError"));
      setAnalyzing(false);
    }
  };

  // Posições em ordem de ação (UTG…BTN, SB, BB) pra exibir os chips de setup.
  const actionOrder = useMemo<PlayerInput[]>(() => {
    if (clockwiseFromSb.length < 2) return clockwiseFromSb;
    return [...clockwiseFromSb.slice(2), clockwiseFromSb[0], clockwiseFromSb[1]];
  }, [clockwiseFromSb]);

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />
      <div className="mx-auto max-w-[1400px] px-6 py-8 space-y-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
            <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
          </div>
          <div className="flex items-center gap-2">
            <input ref={fileInputRef} type="file" accept=".txt,text/plain" className="hidden"
              onChange={e => { onLoadFile(e.target.files?.[0] ?? null); e.target.value = ""; }} />
            <button onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-background border border-border font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground hover:border-primary/60 transition-colors"
              title={t("import.tip")}>
              <Upload className="size-3" /> {t("import.load")}
            </button>
            <button onClick={undo} disabled={undoDepth === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-background border border-border font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground hover:border-primary/60 transition-colors disabled:opacity-30 disabled:hover:border-border"
              title={t("actions.undoTip")}>
              <Undo2 className="size-3" /> {t("actions.undo")}
            </button>
          </div>
        </div>
        {importErr && <p className="text-xs text-destructive font-mono">{importErr}</p>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── Left ─────────────────────────────────────────────────────── */}
          <div className="lg:col-span-2 space-y-6">

            {/* Mesa (simples: tamanho + stack) */}
            <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-4">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div className="space-y-1">
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("setup.table")}</span>
                  <div className="flex gap-1">
                    {TABLE_SIZES.map(sz => (
                      <button key={sz} onClick={() => setTableSize(sz)}
                        className={cn("px-3 py-1.5 rounded-md font-mono text-xs font-bold transition-colors",
                          state.tableSize === sz ? "bg-primary text-primary-foreground" : "bg-background border border-border hover:border-primary/60")}>
                        {sz}-max
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("setup.stackDepth")}</span>
                  <div className="flex items-center gap-1.5">
                    <input type="number" min={1} value={state.stackBb}
                      onChange={e => applyStackToAll(Math.max(1, +e.target.value || 0))}
                      className="w-20 bg-background border border-border rounded px-2 py-1.5 font-mono tabular-nums text-right text-sm" />
                    <span className="font-mono text-[11px] text-muted-foreground">bb</span>
                    <div className="flex gap-1 ml-1">
                      {[40, 75, 100].map(d => (
                        <button key={d} onClick={() => applyStackToAll(d)}
                          className="px-2 py-1 rounded font-mono text-[10px] text-muted-foreground hover:text-primary border border-border/50">{d}</button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Posições — clique na estrela pra marcar o hero; edita stack por posição */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("setup.positions")}</span>
                  <span className="text-[10px] text-muted-foreground">· {t("setup.clickHero")}</span>
                </div>
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
                  {actionOrder.map(p => {
                    const pos = positionOf(p);
                    const isHero = p.seat === state.heroSeat;
                    const isBtn = p.seat === state.buttonSeat;
                    return (
                      <div key={p.seat}
                        className={cn("rounded-lg border p-2 transition-colors",
                          isHero ? "border-primary bg-primary/10" : "border-border bg-background")}>
                        <div className="flex items-center justify-between">
                          <span className={cn("font-mono text-xs font-bold", isHero ? "text-primary" : "text-foreground")}>{pos}</span>
                          <button onClick={() => update("heroSeat", p.seat)} title={t("setup.markHero")}
                            className={cn("transition-colors", isHero ? "text-primary" : "text-muted-foreground/40 hover:text-primary")}>
                            <Star className={cn("size-3.5", isHero && "fill-primary")} />
                          </button>
                        </div>
                        <div className="flex items-center gap-1 mt-1">
                          <input type="number" min={0} value={toBB(p.stack, state.bb)}
                            onChange={e => setPlayerStackBb(p.seat, +e.target.value || 0)}
                            className="w-full bg-transparent border-b border-border/40 px-0.5 py-0.5 font-mono tabular-nums text-[11px] text-right focus:border-primary outline-none" />
                          <span className="font-mono text-[9px] text-muted-foreground">bb</span>
                        </div>
                        {isBtn && <span className="block mt-0.5 font-mono text-[8px] text-muted-foreground/60">BTN</span>}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Avançado: metadados de torneio + blinds custom + diagrama */}
              <details open={showAdvanced} onToggle={e => setShowAdvanced((e.target as HTMLDetailsElement).open)}
                className="rounded-lg border border-border/50 bg-background/40">
                <summary className="flex items-center gap-1.5 px-3 py-2 cursor-pointer font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground select-none">
                  <Settings2 className="size-3" /> {t("advanced.title")}
                </summary>
                <div className="p-3 pt-1 space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.handId")}</span>
                      <input type="text" value={state.handId} onChange={e => update("handId", e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.tournamentId")}</span>
                      <input type="text" value={state.tournamentId} onChange={e => update("tournamentId", e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.buyIn")}</span>
                      <input type="text" value={state.buyIn} onChange={e => update("buyIn", e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.level")}</span>
                      <input type="text" value={state.level} onChange={e => update("level", e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.sb")}</span>
                      <input type="number" value={state.sb} onChange={e => update("sb", +e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.bb")}</span>
                      <input type="number" value={state.bb} onChange={e => update("bb", +e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.ante")}</span>
                      <input type="number" value={state.ante} onChange={e => update("ante", +e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums" />
                    </label>
                    <label className="space-y-1">
                      <span className="font-mono text-[10px] text-muted-foreground">{t("advanced.btnSeat")}</span>
                      <select value={state.buttonSeat} onChange={e => update("buttonSeat", +e.target.value)}
                        className="w-full bg-background border border-border rounded px-2 py-1 font-mono">
                        {state.players.map(p => p.seat).sort((a, b) => a - b).map(s => (
                          <option key={s} value={s}>{t("advanced.seat")} {s}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <p className="font-mono text-[9px] text-muted-foreground/70">{t("advanced.note")}</p>
                  {/* Renomear jogadores (opcional) */}
                  <div className="space-y-1.5">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("advanced.players")}</span>
                    {clockwiseFromSb.map(p => (
                      <div key={p.seat} className="flex items-center gap-2 text-sm">
                        <span className="font-mono text-[10px] text-muted-foreground w-12">{positionOf(p)}</span>
                        <input type="text" value={p.name}
                          onChange={e => editPlayer(p.seat, { name: e.target.value })}
                          className="flex-1 bg-background border border-border rounded px-2 py-1 text-xs" />
                        <button onClick={() => update("heroSeat", p.seat)}
                          className={cn("font-mono text-[10px] px-2 py-1 rounded", p.seat === state.heroSeat ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-primary")}>
                          hero
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </details>
            </section>

            {/* Hero cards */}
            {heroPlayer && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <CardPicker
                  label={t("heroCards.label", { pos: positionOf(heroPlayer) })}
                  selected={state.heroCards} count={2} disabled={usedCards}
                  clearLabel={t("common.clear")}
                  onPick={cards => { snapshot(); update("heroCards", cards); }}
                />
              </section>
            )}

            {/* Actions */}
            {heroPlayer && state.players.length >= 2 && state.heroCards.length === 2 && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                    {t("actions.title")} · <span className="text-primary">{t(`street.${currentStreet}`)}</span>
                  </h2>
                  <div className="flex items-center gap-1">
                    <button onClick={undo} disabled={undoDepth === 0}
                      className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase text-muted-foreground hover:text-foreground disabled:opacity-30"
                      title={t("actions.undoTip")}>
                      <Undo2 className="size-3" /> {t("actions.undo")}
                    </button>
                    <button onClick={clearCurrentHand}
                      className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase text-muted-foreground hover:text-destructive">
                      <Trash2 className="size-3" /> {t("actions.clearHand")}
                    </button>
                  </div>
                </div>

                {streetComplete && pendingBoardStreet ? (
                  <div className="rounded-lg border-2 border-amber-500/40 bg-amber-500/5 p-4 text-center space-y-2">
                    <p className="text-sm font-bold text-amber-300">{t("actions.streetComplete", { street: t(`street.${currentStreet}`) })}</p>
                    <p className="text-xs text-muted-foreground">{t(`actions.selectBoard.${pendingBoardStreet}`)}</p>
                  </div>
                ) : handComplete ? (
                  <div className="rounded-lg border-2 border-emerald-500/40 bg-emerald-500/5 p-4 text-center space-y-3">
                    <p className="text-sm font-bold text-emerald-300">{t("actions.handDone")}</p>
                    <p className="text-xs text-muted-foreground">{t("actions.handDoneHint")}</p>
                    <button onClick={nextHand}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-emerald-500 text-emerald-950 font-mono text-xs font-bold uppercase tracking-widest hover:bg-emerald-400">
                      <ChevronRight className="size-3.5" /> {t("actions.nextHand")}
                    </button>
                  </div>
                ) : (
                  <CurrentActorCard
                    actor={currentActor}
                    positionLabel={currentActor ? positionOf(currentActor) : ""}
                    facing={facing} bb={state.bb}
                    pot={potBefore} maxBet={maxBetThisStreet.maxBet}
                    isPreflop={currentStreet === "preflop"}
                    onAddAction={(action, amount) => {
                      if (!currentActor) return;
                      addAction(action, currentActor.name, amount);
                    }}
                  />
                )}

                {/* Status table */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5 pt-2 border-t border-border/40">
                  {clockwiseFromSb.map(p => {
                    const folded = foldedPlayers.has(p.name);
                    const isCurrent = currentActor?.name === p.name;
                    const bet = maxBetThisStreet.totalByPlayer.get(p.name) ?? 0;
                    return (
                      <div key={p.seat} className={cn(
                        "flex items-center gap-1.5 px-2 py-1 rounded text-[11px] border transition-colors",
                        isCurrent ? "border-primary bg-primary/10" :
                        folded    ? "border-border/30 opacity-40 line-through" : "border-border/50"
                      )}>
                        <span className="font-mono text-[9px] text-muted-foreground w-12">{positionOf(p)}</span>
                        <span className="font-mono flex-1 truncate">{p.name}</span>
                        {bet > 0 && <span className="font-mono text-[10px] tabular-nums text-foreground/70">{fmtBB(bet, state.bb)}</span>}
                      </div>
                    );
                  })}
                </div>

                {/* Action log */}
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {state.actions.length === 0 && (
                    <p className="text-xs text-muted-foreground italic">{t("actions.noActions")}</p>
                  )}
                  {state.actions.map((a, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs font-mono">
                      <span className="text-muted-foreground w-14">[{t(`street.${a.street}`)}]</span>
                      <span className="text-foreground flex-1">{a.player}</span>
                      <span className="text-primary uppercase">{t(`act.${a.action}`)}</span>
                      {a.amount != null && <span className="tabular-nums text-foreground/70">{fmtBB(a.amount, state.bb)}</span>}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Board */}
            {state.actions.length > 0 && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{t("board.title")}</h2>
                <CardPicker label={t("board.flop")} count={3} selected={state.board.flop}
                  disabled={usedCards} clearLabel={t("common.clear")}
                  onPick={cards => { snapshot(); update("board", { ...state.board, flop: cards }); }} />
                {state.board.flop.length === 3 && (
                  <CardPicker label={t("board.turn")} count={1} selected={state.board.turn ? [state.board.turn] : []}
                    disabled={usedCards} clearLabel={t("common.clear")}
                    onPick={cards => { snapshot(); update("board", { ...state.board, turn: cards[0] || "" }); }} />
                )}
                {state.board.turn && (
                  <CardPicker label={t("board.river")} count={1} selected={state.board.river ? [state.board.river] : []}
                    disabled={usedCards} clearLabel={t("common.clear")}
                    onPick={cards => { snapshot(); update("board", { ...state.board, river: cards[0] || "" }); }} />
                )}
              </section>
            )}

            {/* Winner */}
            {state.actions.length > 0 && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{t("winner.title")}</h2>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <label className="space-y-1">
                    <span className="font-mono text-[10px] text-muted-foreground">{t("winner.player")}</span>
                    <select value={state.showWinner} onChange={e => update("showWinner", e.target.value)}
                      className="w-full bg-background border border-border rounded px-2 py-1">
                      <option value="">{t("winner.choose")}</option>
                      {state.players.map(p => <option key={p.seat} value={p.name}>{positionOf(p)} · {p.name}</option>)}
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="font-mono text-[10px] text-muted-foreground">{t("winner.pot")}</span>
                    <div className="flex items-center gap-1">
                      <input type="number" step="0.1" value={state.winAmount ? toBB(state.winAmount, state.bb) : ""}
                        onChange={e => update("winAmount", Math.round((+e.target.value || 0) * state.bb))}
                        className="flex-1 bg-background border border-border rounded px-2 py-1 font-mono tabular-nums text-right" />
                      <span className="font-mono text-[10px] text-muted-foreground">bb</span>
                    </div>
                  </label>
                </div>
              </section>
            )}
          </div>

          {/* ── Right: preview ───────────────────────────────────────────── */}
          <div className="space-y-4">
            <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3 sticky top-4">
              <div className="flex items-center justify-between">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                  <FileText className="inline size-3 mr-1" /> {t("preview.title")}
                </h2>
                <div className="flex items-center gap-2">
                  <button onClick={exportTxt} disabled={!fullHhText}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-primary/10 text-primary font-mono text-[10px] uppercase tracking-widest hover:bg-primary/20 disabled:opacity-30">
                    <Download className="size-3" /> .txt
                  </button>
                  <button onClick={resetAll}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase text-muted-foreground hover:text-destructive">
                    <RotateCcw className="size-3" /> {t("preview.reset")}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="text-muted-foreground">
                  {t("preview.handNo", { n: state.completedHands.length + 1 })}
                  {state.completedHands.length > 0 && (
                    <span className="text-primary"> · {t("preview.inFile", { n: state.completedHands.length })}</span>
                  )}
                </span>
                <span className="text-primary">#{state.tournamentId}</span>
              </div>

              <pre className="bg-background border border-border/50 rounded p-3 text-[10px] font-mono leading-relaxed text-foreground/80 max-h-[600px] overflow-auto whitespace-pre-wrap">
                {fullHhText || t("preview.placeholder")}
              </pre>

              {/* Próxima mão — finaliza a atual e começa a próxima (acumula no arquivo) */}
              <button onClick={nextHand} disabled={state.actions.length === 0}
                className="flex items-center justify-center gap-1 w-full px-3 py-2 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono text-[10px] font-bold uppercase tracking-widest hover:bg-emerald-500/25 disabled:opacity-30 disabled:hover:bg-emerald-500/15">
                <ChevronRight className="size-3" /> {t("preview.nextHand")}
              </button>
              <p className="text-[9px] text-muted-foreground/70 text-center leading-snug">{t("preview.buildTip")}</p>

              {fullHhText && (
                <button onClick={analyzeNow} disabled={analyzing}
                  className="flex items-center justify-center gap-1 w-full px-3 py-2 rounded-md bg-primary text-primary-foreground font-mono text-[10px] uppercase tracking-widest hover:bg-primary/90 disabled:opacity-60">
                  {analyzing ? <Loader2 className="size-3 animate-spin" /> : <Play className="size-3" />}
                  {analyzing ? t("preview.analyzing") : t("preview.analyzeTournament")}
                </button>
              )}
              {analyzeErr && (
                <p className="text-[10px] text-destructive font-mono">{analyzeErr}</p>
              )}
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Current actor card ──────────────────────────────────────────────────────

// Botão de atalho de sizing (preenche o campo de aposta em bb).
function SizeBtn({ label, onClick, title }: { label: string; onClick: () => void; title?: string }) {
  return (
    <button onClick={onClick} title={title}
      className="px-2 py-1 rounded border border-border/60 font-mono text-[10px] font-bold text-muted-foreground hover:text-primary hover:border-primary/60 transition-colors">
      {label}
    </button>
  );
}

function CurrentActorCard({
  actor, positionLabel, facing, bb, pot, maxBet, isPreflop, onAddAction,
}: {
  actor: PlayerInput | null;
  positionLabel: string;
  facing: { invested: number; toCall: number; facingBet: boolean };
  bb: number;
  pot: number;        // pote no momento da ação (fichas)
  maxBet: number;     // maior aposta da street (fichas)
  isPreflop: boolean;
  onAddAction: (action: ActionType, amount?: number) => void;
}) {
  const { t } = useTranslation("handbuilder");
  const [amountBB, setAmountBB] = useState<number>(0);
  useEffect(() => { setAmountBB(0); }, [actor?.name]);

  if (!actor) {
    return (
      <div className="rounded-lg bg-background border border-border/50 p-4 text-center text-sm text-muted-foreground">
        {t("actions.handOver")}
      </div>
    );
  }

  const canCheck = !facing.facingBet;
  const canCall  = facing.facingBet;
  const canBet   = !facing.facingBet;
  const canRaise = facing.facingBet;

  const callAmountChips = facing.facingBet ? facing.invested + facing.toCall : 0;
  const minRaiseChips   = facing.facingBet ? facing.invested + facing.toCall * 2 : 0;
  const defaultBetBB    = 2.5;
  const callAmountBB = toBB(callAmountChips, bb);
  const minRaiseBB   = toBB(minRaiseChips, bb);

  // ── Atalhos de sizing contextuais (preenchem o campo em bb) ─────────────────
  const r1 = (x: number) => Math.round(x * 10) / 10;
  const potBb    = toBB(pot, bb);
  const maxBetBb = toBB(maxBet, bb);
  // open = preflop e ninguém raisou além do BB (só o BB é a "aposta")
  const openContext    = isPreflop && facing.facingBet && maxBetBb <= 1.01;
  const reraiseContext = facing.facingBet && !openContext;          // 3bet+/raise postflop
  const betContext     = !facing.facingBet;                        // bet postflop (ou BB option)
  // pot-size raise "to" (contribuição total na street) = invested + pote + 2·toCall
  const potRaiseBb = r1(toBB(facing.invested + pot + 2 * facing.toCall, bb));

  const submit = (action: ActionType) => {
    const needsAmount = action === "bet" || action === "raise" || action === "call" || action === "allin";
    let chipsVal = Math.round(amountBB * bb);
    if (action === "call")  chipsVal = callAmountChips;
    if (action === "allin") chipsVal = actor.stack + facing.invested;
    onAddAction(action, needsAmount ? chipsVal : undefined);
    setAmountBB(0);
  };

  return (
    <div className="rounded-lg bg-primary/5 border-2 border-primary/30 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] uppercase tracking-widest text-primary">{t("actions.turn")}</span>
          <span className="text-lg font-bold text-foreground">{positionLabel}</span>
        </div>
        <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] font-bold uppercase tracking-wider bg-primary/15 text-primary ring-1 ring-primary/30">
          {actor.name}
        </span>
      </div>

      <div className="flex items-center gap-4 text-[11px] font-mono flex-wrap">
        <span><span className="text-muted-foreground">{t("actions.stack")}:</span> <span className="tabular-nums text-foreground">{fmtBB(actor.stack, bb)}</span></span>
        <span><span className="text-muted-foreground">{t("actions.pot")}:</span> <span className="tabular-nums text-foreground">{fmtBB(pot, bb)}</span></span>
        {facing.invested > 0 && (
          <span><span className="text-muted-foreground">{t("actions.invested")}:</span> <span className="tabular-nums text-foreground">{fmtBB(facing.invested, bb)}</span></span>
        )}
        {facing.facingBet && (
          <span><span className="text-muted-foreground">{t("actions.toCall")}:</span> <span className="tabular-nums text-blue-400">{fmtBB(facing.toCall, bb)}</span></span>
        )}
      </div>

      {/* Atalhos de sizing (preenchem o campo; depois clique Bet/Raise) */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <div className="flex items-center gap-1">
          <input type="number" step="0.1" value={amountBB || ""} onChange={e => setAmountBB(+e.target.value || 0)}
            placeholder={openContext ? defaultBetBB.toFixed(1) : facing.facingBet ? minRaiseBB.toFixed(1) : r1(potBb / 2).toFixed(1)}
            className="w-20 bg-background border border-border rounded px-2 py-1.5 text-sm font-mono tabular-nums text-right" />
          <span className="font-mono text-[10px] text-muted-foreground">bb</span>
        </div>
        {openContext && [2, 2.5, 3].map(v => (
          <SizeBtn key={v} label={`${v}bb`} onClick={() => setAmountBB(v)} title={t("actions.szOpen")} />
        ))}
        {reraiseContext && (<>
          <SizeBtn label={t("actions.szMin")} onClick={() => setAmountBB(r1(minRaiseBB))} title={t("actions.szMinTip")} />
          <SizeBtn label="3x" onClick={() => setAmountBB(r1(3 * maxBetBb))} title={t("actions.sz3xTip")} />
          <SizeBtn label="pot" onClick={() => setAmountBB(potRaiseBb)} title={t("actions.szPotRaiseTip")} />
        </>)}
        {betContext && (<>
          <SizeBtn label="⅓" onClick={() => setAmountBB(r1(potBb / 3))} title={t("actions.szPotFracTip")} />
          <SizeBtn label="½" onClick={() => setAmountBB(r1(potBb / 2))} title={t("actions.szPotFracTip")} />
          <SizeBtn label="⅔" onClick={() => setAmountBB(r1(potBb * 2 / 3))} title={t("actions.szPotFracTip")} />
          <SizeBtn label="pot" onClick={() => setAmountBB(r1(potBb))} title={t("actions.szPotTip")} />
        </>)}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <ActionButton available color="bg-zinc-500/20 text-zinc-300 hover:bg-zinc-500/30" onClick={() => submit("fold")}>{t("act.fold")}</ActionButton>
        <ActionButton available={canCheck} color="bg-sky-500/20 text-sky-300 hover:bg-sky-500/30" onClick={() => submit("check")}>{t("act.check")}</ActionButton>
        <ActionButton available={canCall} color="bg-blue-500/20 text-blue-300 hover:bg-blue-500/30" onClick={() => submit("call")}>
          {t("act.call")} {callAmountChips > 0 ? `(${callAmountBB.toFixed(1)}bb)` : ""}
        </ActionButton>
        <ActionButton available={canBet} color="bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30" onClick={() => submit("bet")}>{t("act.bet")}</ActionButton>
        <ActionButton available={canRaise} color="bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30" onClick={() => submit("raise")}>{t("act.raise")}</ActionButton>
        <ActionButton available color="bg-red-500/20 text-red-300 hover:bg-red-500/30" onClick={() => submit("allin")}>{t("act.allin")}</ActionButton>
      </div>
    </div>
  );
}
