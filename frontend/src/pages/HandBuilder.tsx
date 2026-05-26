import { useEffect, useMemo, useState } from "react";
import { Download, Play, Plus, Trash2, RotateCcw, FileText, ChevronRight } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
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

const ALL_CARDS = RANKS.flatMap(r => SUITS.map(s => r + s.s));

// ── Card picker ────────────────────────────────────────────────────────────────

function CardPicker({
  selected, onPick, count = 1, disabled = new Set<string>(),
  label,
}: {
  selected: string[];
  onPick: (cards: string[]) => void;
  count: number;
  disabled?: Set<string>;
  label: string;
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
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</p>
        <span className="font-mono text-[10px] text-primary">{selected.length}/{count}</span>
        {selected.length > 0 && (
          <button onClick={() => onPick([])} className="ml-auto text-[10px] text-muted-foreground hover:text-foreground">limpar</button>
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
              onClick={() => toggle(card)}
              disabled={isDis}
              className={cn(
                "w-9 h-12 rounded border font-mono text-xs font-bold flex flex-col items-center justify-center transition-all",
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
  action, available, onClick, color, children,
}: {
  action: ActionType; available: boolean;
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

// ── Main page ─────────────────────────────────────────────────────────────────

const MAX_SEATS = 9;

const initialState = () => {
  const stored = typeof window !== "undefined" ? localStorage.getItem("handBuilderDraft") : null;
  if (stored) {
    try { return JSON.parse(stored); } catch { /* fall through */ }
  }
  return {
    handId: "100000001",
    tournamentId: "999999",
    buyIn: "1.00+0.10",
    level: "V",
    sb: 40,
    bb: 80,
    ante: 10,
    players: [] as PlayerInput[],
    buttonSeat: 1,
    heroSeat: 9,
    heroCards: [] as string[],
    actions: [] as HandAction[],
    board: { flop: [] as string[], turn: "", river: "" },
    showWinner: "",
    winAmount: 0,
  };
};

export default function HandBuilder() {
  const [state, setState] = useState(initialState);

  // Persist draft
  useEffect(() => {
    localStorage.setItem("handBuilderDraft", JSON.stringify(state));
  }, [state]);

  const update = <K extends keyof typeof state>(key: K, val: (typeof state)[K]) =>
    setState(s => ({ ...s, [key]: val }));

  const heroPlayer = state.players.find(p => p.seat === state.heroSeat);
  const foldedPlayers = useMemo(() =>
    new Set(state.actions.filter(a => a.action === "fold").map(a => a.player)),
    [state.actions]
  );

  // Ordem clockwise a partir do SB (depois do button): [SB, BB, UTG, UTG+1, ..., BTN]
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

  const positionLabel = (player: PlayerInput): string => {
    const idx = clockwiseFromSb.findIndex(p => p.name === player.name);
    if (idx === -1) return "";
    const n = clockwiseFromSb.length;
    if (idx === n - 1) return "BTN";
    if (idx === 0)     return "SB";
    if (idx === 1)     return "BB";
    if (idx === 2)     return n > 4 ? "UTG" : "UTG/CO";
    if (idx === n - 2) return "CO";
    if (idx === n - 3) return "HJ";
    if (idx === n - 4) return "LJ";
    return `UTG+${idx - 2}`;
  };

  // Current street derivada do board
  const currentStreet: Street = useMemo(() => {
    if (state.board.river) return "river";
    if (state.board.turn)  return "turn";
    if (state.board.flop.length === 3) return "flop";
    return "preflop";
  }, [state.board]);

  // Próximo a agir (auto-rotaciona clockwise a partir do último que agiu)
  const currentActor = useMemo<PlayerInput | null>(() => {
    if (clockwiseFromSb.length < 2) return null;
    const active = clockwiseFromSb.filter(p => !foldedPlayers.has(p.name));
    if (active.length <= 1) return null; // hand acabou

    const streetActions = state.actions.filter(a => a.street === currentStreet);
    if (streetActions.length === 0) {
      // Início da street: preflop começa UTG (idx 2); postflop começa SB (idx 0)
      if (currentStreet === "preflop") return active[2 % active.length] ?? active[0];
      return active[0];
    }
    const lastActor = streetActions[streetActions.length - 1].player;
    const lastIdx = active.findIndex(p => p.name === lastActor);
    if (lastIdx === -1) return active[0];
    return active[(lastIdx + 1) % active.length];
  }, [clockwiseFromSb, foldedPlayers, currentStreet, state.actions]);

  // Maior aposta nesta street (pra determinar "facing bet")
  const maxBetThisStreet = useMemo(() => {
    const streetActions = state.actions.filter(a => a.street === currentStreet);
    const blindContext = currentStreet === "preflop";
    let maxBet = blindContext ? state.bb : 0;
    // Total por player nesta street
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

  // Quanto o currentActor já tem investido nesta street + quanto falta pra call
  const facing = useMemo(() => {
    if (!currentActor) return { invested: 0, toCall: 0, facingBet: false };
    const invested = maxBetThisStreet.totalByPlayer.get(currentActor.name) ?? 0;
    const toCall = Math.max(0, maxBetThisStreet.maxBet - invested);
    return { invested, toCall, facingBet: toCall > 0 };
  }, [currentActor, maxBetThisStreet]);

  // Detecta se a street fechou (todos active matched o maxBet OU foldaram OU all-in).
  // Bloqueia o currentActor card e prompta seleção do próximo board.
  const streetComplete = useMemo<boolean>(() => {
    const active = clockwiseFromSb.filter(p => !foldedPlayers.has(p.name));
    if (active.length <= 1) return true;  // hand acabou
    const streetActions = state.actions.filter(a => a.street === currentStreet);

    // Preflop: SB e BB têm posts, mas precisam de ação voluntária (BB tem option).
    // Para todas as streets, cada player ativo precisa de ao menos 1 ação na street.
    for (const p of active) {
      const playerActions = streetActions.filter(a => a.player === p.name);
      if (playerActions.length === 0) return false;
      const last = playerActions[playerActions.length - 1];
      if (last.action === "allin") continue;          // all-in não precisa matchar mais
      if (last.action === "fold")  continue;          // já está fora (não deveria ocorrer aqui)
      const invested = maxBetThisStreet.totalByPlayer.get(p.name) ?? 0;
      if (invested < maxBetThisStreet.maxBet) return false;  // ainda devendo
    }
    return true;
  }, [clockwiseFromSb, foldedPlayers, state.actions, currentStreet, maxBetThisStreet]);

  const handComplete = useMemo<boolean>(() => {
    const active = clockwiseFromSb.filter(p => !foldedPlayers.has(p.name));
    if (active.length <= 1) return true;
    return streetComplete && currentStreet === "river";
  }, [clockwiseFromSb, foldedPlayers, streetComplete, currentStreet]);

  // Próxima street pendente (a que precisa do board). Skip se a mão acabou.
  const pendingBoardStreet: Street | null = useMemo(() => {
    if (!streetComplete || handComplete) return null;
    if (currentStreet === "preflop" && state.board.flop.length !== 3) return "flop";
    if (currentStreet === "flop"    && !state.board.turn)             return "turn";
    if (currentStreet === "turn"    && !state.board.river)            return "river";
    return null;
  }, [streetComplete, handComplete, currentStreet, state.board]);

  // Disabled cards = already used
  const usedCards = useMemo(() => {
    const all = new Set<string>();
    state.heroCards.forEach(c => all.add(c));
    state.board.flop.forEach(c => all.add(c));
    if (state.board.turn)  all.add(state.board.turn);
    if (state.board.river) all.add(state.board.river);
    return all;
  }, [state.heroCards, state.board]);

  // Add player
  const addPlayer = () => {
    const occupied = new Set(state.players.map(p => p.seat));
    const nextSeat = Array.from({ length: MAX_SEATS }, (_, i) => i + 1).find(s => !occupied.has(s));
    if (!nextSeat) return;
    update("players", [...state.players, {
      seat: nextSeat,
      name: `Player${state.players.length + 1}`,
      stack: 3000,
    }]);
  };

  const removePlayer = (seat: number) => {
    update("players", state.players.filter(p => p.seat !== seat));
  };

  const editPlayer = (seat: number, patch: Partial<PlayerInput>) => {
    update("players", state.players.map(p => p.seat === seat ? { ...p, ...patch } : p));
  };

  // Add action
  const addAction = (action: ActionType, player: string, amount?: number) => {
    update("actions", [...state.actions, { player, street: currentStreet, action, amount }]);
  };

  const removeLastAction = () => {
    if (state.actions.length === 0) return;
    update("actions", state.actions.slice(0, -1));
  };

  // Live HH preview
  const handInput: HandInput | null = useMemo(() => {
    if (!heroPlayer || state.players.length < 2 || state.heroCards.length !== 2) return null;
    return {
      handId: state.handId,
      tournamentId: state.tournamentId,
      buyIn: state.buyIn,
      level: state.level,
      sb: state.sb, bb: state.bb, ante: state.ante,
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

  const exportTxt = () => {
    if (!hhText) return;
    const blob = new Blob([hhText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hand_${state.handId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const resetAll = () => {
    if (!confirm("Apagar toda a mão e começar do zero?")) return;
    localStorage.removeItem("handBuilderDraft");
    setState(initialState());
  };

  return (
    <HudLayout>
      <HudHeader />
      <div className="mx-auto max-w-[1400px] px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Hand Builder</h1>
          <p className="text-sm text-muted-foreground">
            Reconstrua manualmente uma mão (de vídeo ou outra fonte) e exporte como hand history PokerStars.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── Left: Config ─────────────────────────────────────────────── */}
          <div className="lg:col-span-2 space-y-6">
            {/* Stakes/Level */}
            <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
              <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                Torneio & Nível
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">Hand ID</span>
                  <input type="text" value={state.handId}
                    onChange={e => update("handId", e.target.value)}
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">Tournament ID</span>
                  <input type="text" value={state.tournamentId}
                    onChange={e => update("tournamentId", e.target.value)}
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">Buy-in</span>
                  <input type="text" value={state.buyIn}
                    onChange={e => update("buyIn", e.target.value)}
                    placeholder="1.00+0.10"
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">Level (romano)</span>
                  <input type="text" value={state.level}
                    onChange={e => update("level", e.target.value)}
                    placeholder="V"
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">SB</span>
                  <input type="number" value={state.sb}
                    onChange={e => update("sb", +e.target.value)}
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">BB</span>
                  <input type="number" value={state.bb}
                    onChange={e => update("bb", +e.target.value)}
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">Ante</span>
                  <input type="number" value={state.ante}
                    onChange={e => update("ante", +e.target.value)}
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums" />
                </label>
                <label className="space-y-1">
                  <span className="font-mono text-[10px] text-muted-foreground">BTN Seat</span>
                  <select value={state.buttonSeat}
                    onChange={e => update("buttonSeat", +e.target.value)}
                    className="w-full bg-background border border-border rounded px-2 py-1 font-mono">
                    {Array.from({ length: MAX_SEATS }, (_, i) => i + 1).map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            {/* Players */}
            <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                  Jogadores ({state.players.length}/{MAX_SEATS})
                </h2>
                <button onClick={addPlayer} disabled={state.players.length >= MAX_SEATS}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-primary/10 text-primary font-mono text-[10px] uppercase tracking-widest hover:bg-primary/20 transition-colors disabled:opacity-30">
                  <Plus className="size-3" /> Adicionar
                </button>
              </div>
              <div className="space-y-2">
                {state.players.length === 0 && (
                  <p className="text-xs text-muted-foreground italic">Adicione ao menos 2 jogadores (incluindo o hero).</p>
                )}
                {state.players.map(p => (
                  <div key={p.seat} className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-[10px] text-muted-foreground w-8">S{p.seat}</span>
                    <input type="text" value={p.name}
                      onChange={e => editPlayer(p.seat, { name: e.target.value })}
                      className="flex-1 bg-background border border-border rounded px-2 py-1" />
                    <input type="number" value={p.stack}
                      onChange={e => editPlayer(p.seat, { stack: +e.target.value })}
                      className="w-24 bg-background border border-border rounded px-2 py-1 font-mono tabular-nums text-right" />
                    <label className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                      <input type="radio" name="hero" checked={p.seat === state.heroSeat}
                        onChange={() => update("heroSeat", p.seat)} />
                      hero
                    </label>
                    <button onClick={() => removePlayer(p.seat)}
                      className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            {/* Hero cards */}
            {heroPlayer && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <CardPicker
                  label={`Cartas do hero (${heroPlayer.name})`}
                  selected={state.heroCards}
                  count={2}
                  disabled={usedCards}
                  onPick={cards => update("heroCards", cards)}
                />
              </section>
            )}

            {/* Actions */}
            {heroPlayer && state.players.length >= 2 && state.heroCards.length === 2 && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                    Ações · <span className="text-primary">{currentStreet}</span>
                  </h2>
                  <button onClick={removeLastAction} disabled={state.actions.length === 0}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase text-muted-foreground hover:text-foreground disabled:opacity-30">
                    <RotateCcw className="size-3" /> Desfazer
                  </button>
                </div>

                {/* Street complete? Show prompt; else show actor card. */}
                {streetComplete && pendingBoardStreet ? (
                  <div className="rounded-lg border-2 border-amber-500/40 bg-amber-500/5 p-4 text-center space-y-2">
                    <p className="text-sm font-bold text-amber-300">
                      {currentStreet === "preflop" ? "Preflop" :
                       currentStreet === "flop"    ? "Flop"     :
                       currentStreet === "turn"    ? "Turn"     : "River"} completo
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Selecione as cartas do <strong>{pendingBoardStreet === "flop" ? "flop (3 cartas)" :
                                                       pendingBoardStreet === "turn" ? "turn (1 carta)" :
                                                       "river (1 carta)"}</strong> abaixo pra continuar.
                    </p>
                  </div>
                ) : handComplete ? (
                  <div className="rounded-lg border-2 border-emerald-500/40 bg-emerald-500/5 p-4 text-center space-y-2">
                    <p className="text-sm font-bold text-emerald-300">Mão finalizada</p>
                    <p className="text-xs text-muted-foreground">
                      Marque o vencedor abaixo e exporte o hand history.
                    </p>
                  </div>
                ) : (
                  <CurrentActorCard
                    actor={currentActor}
                    positionLabel={currentActor ? positionLabel(currentActor) : ""}
                    facing={facing}
                    bb={state.bb}
                    onAddAction={(action, amount) => {
                      if (!currentActor) return;
                      addAction(action, currentActor.name, amount);
                    }}
                  />
                )}

                {/* Status table: quem está vivo, quem foldou, bets */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5 pt-2 border-t border-border/40">
                  {clockwiseFromSb.map(p => {
                    const folded = foldedPlayers.has(p.name);
                    const isCurrent = currentActor?.name === p.name;
                    const bet = maxBetThisStreet.totalByPlayer.get(p.name) ?? 0;
                    return (
                      <div key={p.seat} className={cn(
                        "flex items-center gap-1.5 px-2 py-1 rounded text-[11px] border transition-colors",
                        isCurrent ? "border-primary bg-primary/10" :
                        folded    ? "border-border/30 opacity-40 line-through" :
                                    "border-border/50"
                      )}>
                        <span className="font-mono text-[9px] text-muted-foreground w-9">{positionLabel(p)}</span>
                        <span className="font-mono flex-1 truncate">{p.name}</span>
                        {bet > 0 && <span className="font-mono text-[10px] tabular-nums text-foreground/70">{bet}</span>}
                      </div>
                    );
                  })}
                </div>

                {/* Lista de ações */}
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {state.actions.length === 0 && (
                    <p className="text-xs text-muted-foreground italic">Nenhuma ação registrada ainda.</p>
                  )}
                  {state.actions.map((a, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs font-mono">
                      <span className="text-muted-foreground w-14">[{a.street}]</span>
                      <span className="text-foreground flex-1">{a.player}</span>
                      <span className="text-primary uppercase">{a.action}</span>
                      {a.amount != null && <span className="tabular-nums text-foreground/70">{a.amount}</span>}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Board cards */}
            {state.actions.length > 0 && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                  Board
                </h2>
                <CardPicker label="Flop (3 cartas)" count={3} selected={state.board.flop}
                  disabled={usedCards}
                  onPick={cards => update("board", { ...state.board, flop: cards })} />
                {state.board.flop.length === 3 && (
                  <CardPicker label="Turn (1)" count={1} selected={state.board.turn ? [state.board.turn] : []}
                    disabled={usedCards}
                    onPick={cards => update("board", { ...state.board, turn: cards[0] || "" })} />
                )}
                {state.board.turn && (
                  <CardPicker label="River (1)" count={1} selected={state.board.river ? [state.board.river] : []}
                    disabled={usedCards}
                    onPick={cards => update("board", { ...state.board, river: cards[0] || "" })} />
                )}
              </section>
            )}

            {/* Winner */}
            {state.actions.length > 0 && (
              <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                  Resultado
                </h2>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <label className="space-y-1">
                    <span className="font-mono text-[10px] text-muted-foreground">Vencedor</span>
                    <select value={state.showWinner}
                      onChange={e => update("showWinner", e.target.value)}
                      className="w-full bg-background border border-border rounded px-2 py-1">
                      <option value="">— escolher —</option>
                      {state.players.map(p => <option key={p.seat} value={p.name}>{p.name}</option>)}
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="font-mono text-[10px] text-muted-foreground">Pote (chips)</span>
                    <input type="number" value={state.winAmount}
                      onChange={e => update("winAmount", +e.target.value)}
                      className="w-full bg-background border border-border rounded px-2 py-1 font-mono tabular-nums text-right" />
                  </label>
                </div>
              </section>
            )}
          </div>

          {/* ── Right: Preview HH + actions ──────────────────────────────── */}
          <div className="space-y-4">
            <section className="rounded-xl border border-border bg-hud-surface p-4 space-y-3 sticky top-4">
              <div className="flex items-center justify-between">
                <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                  <FileText className="inline size-3 mr-1" /> Hand History
                </h2>
                <div className="flex items-center gap-2">
                  <button onClick={exportTxt} disabled={!hhText}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-primary/10 text-primary font-mono text-[10px] uppercase tracking-widest hover:bg-primary/20 disabled:opacity-30">
                    <Download className="size-3" /> .txt
                  </button>
                  <button onClick={resetAll}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase text-muted-foreground hover:text-destructive">
                    <RotateCcw className="size-3" /> Reset
                  </button>
                </div>
              </div>
              <pre className="bg-background border border-border/50 rounded p-3 text-[10px] font-mono leading-relaxed text-foreground/80 max-h-[600px] overflow-auto whitespace-pre-wrap">
                {hhText || "(preencha os campos pra ver o HH gerado em tempo real)"}
              </pre>
              {hhText && (
                <a
                  href="/?import=builder"
                  onClick={(e) => {
                    e.preventDefault();
                    localStorage.setItem("pendingImport", hhText);
                    window.location.href = "/?import=builder";
                  }}
                  className="flex items-center justify-center gap-1 w-full px-3 py-2 rounded-md bg-primary text-primary-foreground font-mono text-[10px] uppercase tracking-widest hover:bg-primary/90"
                >
                  <Play className="size-3" /> Analisar agora
                </a>
              )}
            </section>
          </div>
        </div>
      </div>
    </HudLayout>
  );
}

// ── Sub-component: current actor card ────────────────────────────────────────

function CurrentActorCard({
  actor, positionLabel, facing, bb, onAddAction,
}: {
  actor: PlayerInput | null;
  positionLabel: string;
  facing: { invested: number; toCall: number; facingBet: boolean };
  bb: number;
  onAddAction: (action: ActionType, amount?: number) => void;
}) {
  const [amount, setAmount] = useState<number>(0);

  // Reset amount quando troca de actor
  useEffect(() => { setAmount(0); }, [actor?.name]);

  if (!actor) {
    return (
      <div className="rounded-lg bg-background border border-border/50 p-4 text-center text-sm text-muted-foreground">
        Mão finalizada (ou só 1 jogador ativo). Avance para o próximo street/board ou registre o vencedor.
      </div>
    );
  }

  const canCheck = !facing.facingBet;
  const canCall  = facing.facingBet;
  const canBet   = !facing.facingBet;
  const canRaise = facing.facingBet;

  // Sugestões inteligentes
  const callAmount = facing.facingBet ? facing.invested + facing.toCall : 0;
  const minRaiseTotal = facing.facingBet
    ? facing.invested + facing.toCall * 2  // mínimo: igualar + raise pelo mesmo tanto
    : 0;
  const defaultBet = Math.round(bb * 2.5);

  const setSmart = (action: ActionType) => {
    if (action === "call")  setAmount(callAmount);
    if (action === "bet")   setAmount(amount || defaultBet);
    if (action === "raise") setAmount(amount || minRaiseTotal);
    if (action === "allin") setAmount(actor.stack + facing.invested);
  };

  const submit = (action: ActionType) => {
    const needsAmount = action === "bet" || action === "raise" || action === "call" || action === "allin";
    let val = amount;
    if (action === "call")  val = callAmount;
    if (action === "allin") val = actor.stack + facing.invested;
    onAddAction(action, needsAmount ? val : undefined);
    setAmount(0);
  };

  return (
    <div className="rounded-lg bg-primary/5 border-2 border-primary/30 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] uppercase tracking-widest text-primary">Vez de</span>
          <span className="text-lg font-bold text-foreground">{actor.name}</span>
        </div>
        <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] font-bold uppercase tracking-wider bg-primary/15 text-primary ring-1 ring-primary/30">
          {positionLabel} · S{actor.seat}
        </span>
      </div>

      <div className="flex items-center gap-4 text-[11px] font-mono">
        <span><span className="text-muted-foreground">Stack:</span> <span className="tabular-nums text-foreground">{actor.stack}</span></span>
        {facing.invested > 0 && (
          <span><span className="text-muted-foreground">Investido nesta street:</span> <span className="tabular-nums text-foreground">{facing.invested}</span></span>
        )}
        {facing.facingBet && (
          <span><span className="text-muted-foreground">Pra pagar:</span> <span className="tabular-nums text-blue-400">{facing.toCall}</span></span>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <input type="number" value={amount || ""} onChange={e => setAmount(+e.target.value || 0)}
          placeholder={facing.facingBet ? `${minRaiseTotal} (min raise)` : `${defaultBet} (def bet)`}
          className="w-32 bg-background border border-border rounded px-2 py-1.5 text-sm font-mono tabular-nums text-right" />
        <button onClick={() => setSmart("call")}  disabled={!canCall}  className="text-[10px] font-mono uppercase text-muted-foreground hover:text-foreground disabled:opacity-30">call→</button>
        <button onClick={() => setSmart("bet")}   disabled={!canBet}   className="text-[10px] font-mono uppercase text-muted-foreground hover:text-foreground disabled:opacity-30">2.5x→</button>
        <button onClick={() => setSmart("raise")} disabled={!canRaise} className="text-[10px] font-mono uppercase text-muted-foreground hover:text-foreground disabled:opacity-30">min raise→</button>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <ActionButton action="fold"  available color="bg-zinc-500/20 text-zinc-300 hover:bg-zinc-500/30"     onClick={() => submit("fold")}>Fold</ActionButton>
        <ActionButton action="check" available={canCheck} color="bg-sky-500/20 text-sky-300 hover:bg-sky-500/30"  onClick={() => submit("check")}>Check</ActionButton>
        <ActionButton action="call"  available={canCall}  color="bg-blue-500/20 text-blue-300 hover:bg-blue-500/30" onClick={() => submit("call")}>
          Call {callAmount > 0 ? `(${callAmount})` : ""}
        </ActionButton>
        <ActionButton action="bet"   available={canBet}   color="bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30" onClick={() => submit("bet")}>Bet</ActionButton>
        <ActionButton action="raise" available={canRaise} color="bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30" onClick={() => submit("raise")}>Raise</ActionButton>
        <ActionButton action="allin" available color="bg-red-500/20 text-red-300 hover:bg-red-500/30"        onClick={() => submit("allin")}>All-in</ActionButton>
      </div>
    </div>
  );
}
