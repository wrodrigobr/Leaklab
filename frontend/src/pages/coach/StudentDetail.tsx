import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Trophy } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { coachDashboard } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function StudentDetail() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);

  const { data, isLoading } = useQuery({
    queryKey: ["coach-student-history", studentId],
    queryFn: () => coachDashboard.studentHistory(studentId, 30),
    enabled: !isNaN(studentId),
  });

  const chartData = (data?.evolution ?? []).map((p) => ({
    date: p.played_at ? new Date(p.played_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) : "?",
    score: p.avg_score,
    std: p.standard_pct,
  }));

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-4xl px-6 py-8 space-y-8">
        <div className="flex items-center gap-3">
          <Link
            to="/coach-dashboard"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            Dashboard
          </Link>
        </div>

        {isLoading && (
          <p className="text-sm text-muted-foreground animate-pulse">Carregando dados do aluno…</p>
        )}

        {!isLoading && data && (
          <>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Histórico do Aluno</h1>
            </div>

            {chartData.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Evolução (30 dias)
                </p>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip
                      contentStyle={{ background: "hsl(var(--hud-surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                    />
                    <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} name="Score" />
                    <Line type="monotone" dataKey="std" stroke="hsl(var(--primary) / 0.4)" strokeWidth={1.5} dot={false} name="Standard %" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {data.leaks.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Principais Leaks
                </p>
                <div className="space-y-2">
                  {data.leaks.map((leak) => (
                    <div key={leak.spot} className="flex items-center justify-between py-1 border-b border-border/40 last:border-0">
                      <span className="text-sm text-foreground">{leak.spot}</span>
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-xs text-muted-foreground">{leak.n}x</span>
                        <span className={`font-mono text-xs font-bold ${leak.avg_score >= 70 ? "text-primary" : leak.avg_score >= 50 ? "text-amber-400" : "text-destructive"}`}>
                          {leak.avg_score.toFixed(0)} pts
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.tournaments.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Torneios Recentes
                </p>
                <div className="space-y-2">
                  {data.tournaments.slice(0, 10).map((t) => (
                    <div key={t.id} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                      <div className="flex items-center gap-2">
                        <Trophy className="size-3.5 text-muted-foreground" />
                        <span className="font-mono text-xs text-muted-foreground">{t.tournament_id}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs font-mono">
                        <span className="text-muted-foreground">{t.hands_count} mãos</span>
                        <span className={`font-bold ${(t.avg_score ?? 0) >= 70 ? "text-primary" : (t.avg_score ?? 0) >= 50 ? "text-amber-400" : "text-destructive"}`}>
                          {t.avg_score?.toFixed(1) ?? "—"} pts
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
