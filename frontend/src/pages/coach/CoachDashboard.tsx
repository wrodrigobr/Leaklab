import { useQuery } from "@tanstack/react-query";
import { Users, TrendingUp, Award, Activity } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { InviteKeyWidget } from "@/components/coach/InviteKeyWidget";
import { StudentRow } from "@/components/coach/StudentRow";
import { coachDashboard } from "@/lib/api";

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: React.ElementType }) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-1">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-3.5" />
        <span className="font-mono text-[10px] uppercase tracking-widest-2">{label}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
    </div>
  );
}

export default function CoachDashboard() {
  const { data: studentsData, isLoading: loadingStudents } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });

  const { data: impact, isLoading: loadingImpact } = useQuery({
    queryKey: ["coach-impact"],
    queryFn: () => coachDashboard.impact(30),
  });

  const students = studentsData?.students ?? [];
  const summary = impact?.summary;

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-5xl px-6 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard do Professor</h1>
          <p className="text-sm text-muted-foreground mt-1">Acompanhe a evolução dos seus alunos</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Alunos"
            value={loadingImpact ? "…" : (summary?.total_students ?? 0)}
            icon={Users}
          />
          <StatCard
            label="Ativos (30d)"
            value={loadingImpact ? "…" : (summary?.active_students ?? 0)}
            icon={Activity}
          />
          <StatCard
            label="Melhoria Média"
            value={loadingImpact ? "…" : summary?.avg_improvement_pct != null ? `${summary.avg_improvement_pct.toFixed(1)}%` : "—"}
            icon={TrendingUp}
          />
          <StatCard
            label="Melhor Aluno"
            value={loadingImpact ? "…" : (summary?.best_student ?? "—")}
            icon={Award}
          />
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-3">
            <h2 className="font-mono text-xs font-bold uppercase tracking-widest-2 text-muted-foreground">
              Alunos
            </h2>
            {loadingStudents && (
              <p className="text-sm text-muted-foreground animate-pulse">Carregando…</p>
            )}
            {!loadingStudents && students.length === 0 && (
              <div className="rounded-xl border border-dashed border-border p-8 text-center space-y-2">
                <p className="text-sm text-muted-foreground">Nenhum aluno vinculado ainda.</p>
                <p className="text-xs text-muted-foreground">Compartilhe sua chave de convite para que alunos possam se vincular.</p>
              </div>
            )}
            <div className="space-y-2">
              {students.map((s) => (
                <StudentRow key={s.id} student={s} />
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="font-mono text-xs font-bold uppercase tracking-widest-2 text-muted-foreground">
              Convite
            </h2>
            <InviteKeyWidget />

            {impact?.top_leaks && impact.top_leaks.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Leaks em comum
                </p>
                <div className="space-y-2">
                  {impact.top_leaks.slice(0, 5).map((leak) => (
                    <div key={leak.spot} className="flex items-center justify-between">
                      <span className="text-xs text-foreground truncate max-w-[140px]">{leak.spot}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">{leak.n}x</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
