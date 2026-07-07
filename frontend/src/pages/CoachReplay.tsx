import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, Play, Target, Loader2, ArrowRight, GraduationCap } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { ProLockCard } from "@/components/hud/ProLockCard";
import { metrics, type CoachReplayMistake } from "@/lib/api";
import { cn } from "@/lib/utils";

const GLYPH: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED = new Set(["h", "d"]);

/** "3d8h" → duas cartas mini coloridas. */
function MiniCards({ cards }: { cards: string }) {
  const pairs = (cards || "").match(/.{1,2}/g) ?? [];
  return (
    <div className="flex gap-1.5">
      {pairs.map((c, i) => {
        const red = RED.has(c[1]);
        return (
          <div key={i} className={cn(
            "flex h-12 w-9 flex-col items-center justify-center rounded-md bg-white font-bold shadow ring-1 ring-black/20",
            red ? "text-red-600" : "text-slate-900")}>
            <span className="text-sm leading-none">{c[0].toUpperCase()}</span>
            <span className="text-xs leading-none">{GLYPH[c[1]] ?? c[1]}</span>
          </div>
        );
      })}
    </div>
  );
}

function MistakeCard({ tid, m, idx }: { tid: string; m: CoachReplayMistake; idx: number }) {
  const navigate = useNavigate();
  // barra de EV proporcional (visual): ~12px por bb, cap 100%
  const evPct = Math.min(100, Math.abs(m.ev_loss_bb) * 12);
  return (
    <div className="rounded-2xl border border-border bg-card/40 p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="font-mono text-[11px] font-bold uppercase tracking-widest text-amber-400">Erro #{idx + 1}</span>
        <span className="font-mono text-[11px] text-muted-foreground">{m.street_pt} · {m.position}</span>
      </div>

      <div className="flex items-center gap-4">
        <MiniCards cards={m.hero_cards} />
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-snug text-foreground">{m.coach_note}</p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <span className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">EV perdido</span>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted/30">
          <div className="h-full rounded-full bg-red-400" style={{ width: `${evPct}%` }} />
        </div>
        <span className="w-16 shrink-0 text-right font-mono text-sm font-bold text-red-400">{m.ev_loss_bb}bb</span>
      </div>

      <button
        onClick={() => navigate(`/replayer?t=${tid}&h=${m.hand_id}`)}
        className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
        <Play className="size-4" aria-hidden /> Rever na mesa
      </button>
    </div>
  );
}

export default function CoachReplay() {
  const { tid = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["coach-replay", tid],
    queryFn: () => metrics.coachReplay(tid),
    enabled: !!tid,
  });

  return (
    <HudLayout eyebrow="Coach Replay" title="Sua sessão revisada" description="Seus erros mais caros do torneio, reassistidos na mesa real.">
      <div className="mx-auto max-w-2xl space-y-4">
        {isLoading && (
          <div className="flex justify-center py-16"><Loader2 className="size-7 animate-spin text-muted-foreground" /></div>
        )}

        {error && (
          <p className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center text-sm text-muted-foreground">
            Não foi possível carregar o Coach Replay deste torneio.
          </p>
        )}

        {data?.requires_pro && (
          <ProLockCard feature="Coach Replay: seus erros mais caros revisados na mesa" />
        )}

        {data && !data.requires_pro && (
          <>
            {/* Intro */}
            <div className="rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/[0.08] to-transparent p-6 text-center">
              <p className="font-heading text-lg font-bold text-foreground">{data.tournament.name}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Analisamos <b className="text-foreground">{data.intro.hands_analyzed}</b> mãos e achamos os{" "}
                <b className="text-amber-400">{data.intro.mistakes_shown}</b> erros mais caros, que custaram{" "}
                <b className="text-red-400">{data.intro.ev_lost_bb}bb</b> no total.
              </p>
            </div>

            {/* Erros mais caros */}
            {data.mistakes.map((m, i) => (
              <MistakeCard key={m.hand_id + m.street} tid={data.tournament.code ?? tid} m={m} idx={i} />
            ))}

            {data.mistakes.length === 0 && (
              <p className="rounded-xl border border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
                Nenhum erro crítico neste torneio. Bom jogo.
              </p>
            )}

            {/* Plano de estudo */}
            {data.plan.length > 0 && (
              <div className="rounded-2xl border border-border bg-card/40 p-6">
                <h2 className="mb-3 flex items-center gap-2 font-heading text-base font-bold text-foreground">
                  <Target className="size-4 text-primary" aria-hidden /> Seu plano de estudo
                </h2>
                <div className="space-y-2">
                  {data.plan.map((p) => (
                    <div key={p.week} className="flex items-center gap-3">
                      <span className="w-24 shrink-0 font-mono text-xs font-bold uppercase text-amber-400">Semana {p.week}</span>
                      <span className="text-sm text-foreground">{p.focus}</span>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => navigate("/leak-trainer")}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
                  <GraduationCap className="size-4" aria-hidden /> Treinar no GrindLab
                  <ArrowRight className="size-4" aria-hidden />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </HudLayout>
  );
}
