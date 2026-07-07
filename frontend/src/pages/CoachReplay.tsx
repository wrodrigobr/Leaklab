import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Play, Target, Loader2, ArrowRight, GraduationCap, PlayCircle } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { ProLockCard } from "@/components/hud/ProLockCard";
import { metrics, type CoachReplayHand, type CoachReplayVerdict } from "@/lib/api";
import { cn } from "@/lib/utils";

const GLYPH: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED = new Set(["h", "d"]);

/** "3d8h" → duas cartas mini coloridas. */
function MiniCards({ cards }: { cards: string }) {
  const pairs = (cards || "").match(/.{1,2}/g) ?? [];
  return (
    <div className="flex gap-1">
      {pairs.map((c, i) => {
        const red = RED.has(c[1]);
        return (
          <div key={i} className={cn(
            "flex h-10 w-7 flex-col items-center justify-center rounded bg-white font-bold shadow ring-1 ring-black/20",
            red ? "text-red-600" : "text-slate-900")}>
            <span className="text-xs leading-none">{c[0].toUpperCase()}</span>
            <span className="text-[10px] leading-none">{GLYPH[c[1]] ?? c[1]}</span>
          </div>
        );
      })}
    </div>
  );
}

const VERDICT_META: Record<CoachReplayVerdict, { label: string; dot: string; text: string; ring: string }> = {
  error:      { label: "Erro",      dot: "bg-red-400",     text: "text-red-400",     ring: "ring-red-500/25" },
  acceptable: { label: "Aceitável", dot: "bg-sky-400",     text: "text-sky-400",     ring: "ring-sky-500/25" },
  correct:    { label: "Correto",   dot: "bg-emerald-400", text: "text-emerald-400", ring: "ring-emerald-500/20" },
};

function HandRow({ code, h }: { code: string; h: CoachReplayHand }) {
  const navigate = useNavigate();
  const v = VERDICT_META[h.verdict];
  const go = () => navigate(`/replayer?t=${code}&h=${h.hand_id}&walk=1`);
  return (
    <button
      onClick={go}
      className={cn(
        "group w-full rounded-xl border border-border bg-card/40 p-4 text-left transition-colors hover:bg-card/70 ring-1",
        v.ring)}>
      <div className="flex items-center gap-4">
        <span className="w-8 shrink-0 text-center font-mono text-xs font-bold text-muted-foreground">#{h.seq}</span>
        <MiniCards cards={h.hero_cards} />
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2">
            <span className={cn("inline-flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider", v.text)}>
              <span className={cn("size-1.5 rounded-full", v.dot)} /> {v.label}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {h.street_reached_pt} · {h.position}
            </span>
          </div>
          <p className="truncate text-sm leading-snug text-foreground">{h.narration}</p>
        </div>
        {h.ev_loss_bb > 0 && (
          <span className="shrink-0 rounded-md bg-red-500/10 px-2 py-1 font-mono text-xs font-bold text-red-400">
            -{h.ev_loss_bb}bb
          </span>
        )}
        <Play className="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" aria-hidden />
      </div>
    </button>
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

  const code = data?.tournament.code ?? tid;
  const first = data?.hands?.[0];

  return (
    <HudLayout
      eyebrow="Coach Replay"
      title="Sua sessão revisada"
      description="As mãos que valem revisão, reassistidas na mesa real, com o veredito e o custo de cada decisão.">
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
          <ProLockCard feature="Coach Replay: sua sessão revisada mão a mão na mesa real" />
        )}

        {data && !data.requires_pro && (
          <>
            {/* Intro */}
            <div className="rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/[0.08] to-transparent p-6 text-center">
              <p className="font-heading text-lg font-bold text-foreground">{data.tournament.name}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Jogamos <b className="text-foreground">{data.intro.hands_total}</b> mãos.{" "}
                <b className="text-foreground">{data.intro.hands_kept}</b> valem revisão
                {data.intro.hands_skipped > 0 && (
                  <> (pulamos <b className="text-foreground">{data.intro.hands_skipped}</b> folds pré-flop óbvios)</>
                )}
                . Foram <b className="text-red-400">{data.intro.mistakes_count}</b> erros, que custaram{" "}
                <b className="text-red-400">{data.intro.ev_lost_bb}bb</b>.
              </p>
              {first && (
                <button
                  onClick={() => navigate(`/replayer?t=${code}&h=${first.hand_id}&walk=1`)}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
                  <PlayCircle className="size-4" aria-hidden /> Começar revisão
                </button>
              )}
            </div>

            {/* Playlist da sessão */}
            {data.hands.map((h) => (
              <HandRow key={h.hand_id} code={code} h={h} />
            ))}

            {data.hands.length === 0 && (
              <p className="rounded-xl border border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
                Nenhuma mão pra revisar neste torneio. Você foldou no certo a sessão toda. Bom jogo.
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
