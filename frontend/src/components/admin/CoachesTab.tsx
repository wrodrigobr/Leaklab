import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { GraduationCap, Loader2, Users } from "lucide-react";
import { adminDashboard, AdminUser, AdminCoachStudent, CoachPayout } from "@/lib/api";
import { fmt } from "./format";
import { StatusBadge } from "./StatusBadge";
import { DetailDrawer } from "./DetailDrawer";

function CoachDetail({ coach, payout, onClose }: { coach: AdminUser; payout?: CoachPayout; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-coach-students", coach.id],
    queryFn: () => adminDashboard.coachStudents(coach.id),
    staleTime: 15_000,
  });
  const students: AdminCoachStudent[] = data?.students ?? [];

  return (
    <DetailDrawer open title={`Coach @${coach.username}`} icon={GraduationCap} onClose={onClose}>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Plano</p>
          <p className="mt-1 font-mono text-sm text-foreground">{coach.plan}</p>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Repasse atual</p>
          <p className="mt-1 font-mono text-sm font-bold text-foreground">{payout ? fmt(payout.amount_cents) : "—"}</p>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Alunos vinculados</p>
          <p className="mt-1 font-mono text-sm text-foreground tabular-nums">{payout?.total_students ?? students.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Alunos ativos</p>
          <p className="mt-1 font-mono text-sm text-primary font-bold tabular-nums">{payout?.active_students ?? "—"}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-border">
        <div className="px-4 py-2.5 border-b border-border bg-hud-elevated/40">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Alunos</span>
        </div>
        <table className="w-full text-xs text-left">
          <thead className="border-b border-border">
            <tr>
              {["Aluno", "Plano", "Pagamento", "Vínculo"].map((h) => (
                <th key={h} className="px-4 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr><td colSpan={4} className="py-8 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
            ) : students.length === 0 ? (
              <tr><td colSpan={4} className="py-8 text-center text-muted-foreground">Nenhum aluno vinculado.</td></tr>
            ) : students.map((s) => (
              <tr key={s.id} className="hover:bg-primary/5 transition-colors">
                <td className="px-4 py-2.5">
                  <p className="font-medium text-foreground">@{s.username}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{s.email}</p>
                </td>
                <td className="px-4 py-2.5 font-mono text-[10px] uppercase text-muted-foreground">{s.plan}</td>
                <td className="px-4 py-2.5"><StatusBadge kind={s.billing_standing} /></td>
                <td className="px-4 py-2.5"><StatusBadge kind={s.link_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DetailDrawer>
  );
}

export function CoachesTab() {
  const [period] = useState(() => new Date().toISOString().slice(0, 7));
  const [selected, setSelected] = useState<AdminUser | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", "coach-roster"],
    queryFn: () => adminDashboard.users({ role: "coach", limit: 200 }),
    staleTime: 30_000,
  });
  const { data: payoutData } = useQuery({
    queryKey: ["admin-finance-coaches", period],
    queryFn: () => adminDashboard.coachPayouts(period),
    staleTime: 30_000,
  });

  const coaches: AdminUser[] = data?.users ?? [];
  const payoutById = new Map<number, CoachPayout>();
  (payoutData?.payouts ?? []).forEach((p) => payoutById.set(p.id, p));

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="flex items-center gap-2 border-b border-border bg-hud-elevated/40 px-4 py-3">
          <GraduationCap className="size-3.5 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Coaches{coaches.length ? ` · ${coaches.length}` : ""}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="border-b border-border">
              <tr>
                {["Coach", "Plano", "Alunos vinculados", "Alunos ativos", "Repasse atual", "Standing", ""].map((h) => (
                  <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr><td colSpan={7} className="py-12 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
              ) : coaches.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center text-muted-foreground">Nenhum coach cadastrado.</td></tr>
              ) : coaches.map((c) => {
                const po = payoutById.get(c.id);
                return (
                  <tr key={c.id} className="cursor-pointer hover:bg-primary/5 transition-colors" onClick={() => setSelected(c)}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-foreground">{c.display_name || c.username}</p>
                      <p className="font-mono text-[10px] text-muted-foreground">@{c.username}</p>
                    </td>
                    <td className="px-4 py-3 font-mono text-muted-foreground">{c.plan}</td>
                    <td className="px-4 py-3 font-mono tabular-nums text-foreground text-center">{po?.total_students ?? "—"}</td>
                    <td className="px-4 py-3 font-mono tabular-nums text-center text-primary font-bold">{po?.active_students ?? "—"}</td>
                    <td className="px-4 py-3 font-mono tabular-nums font-bold text-foreground">{po ? (po.amount_cents > 0 ? fmt(po.amount_cents) : "Zerado") : "—"}</td>
                    <td className="px-4 py-3"><StatusBadge kind={c.billing_standing} /></td>
                    <td className="px-4 py-3 text-right">
                      <span className="inline-flex items-center gap-1 font-mono text-[10px] text-primary"><Users className="size-3" /> ver</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <CoachDetail coach={selected} payout={payoutById.get(selected.id)} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
