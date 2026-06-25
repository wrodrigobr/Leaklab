import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Loader2, Users } from "lucide-react";
import { toast } from "sonner";
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

  const qc = useQueryClient();
  const [rateInput, setRateInput] = useState(
    payout?.commission_rate_bps != null ? String(payout.commission_rate_bps / 100) : ""
  );
  const [savingRate, setSavingRate] = useState(false);
  const [paying, setPaying] = useState(false);
  const saveRate = async () => {
    const v = rateInput.trim().replace(",", ".").replace("%", "");
    const bps = v === "" ? null : Math.round(parseFloat(v) * 100);
    if (bps !== null && (isNaN(bps) || bps < 0 || bps > 10000)) { toast.error("Taxa inválida (0 a 100%)."); return; }
    setSavingRate(true);
    try {
      await adminDashboard.setCoachCommissionRate(coach.id, bps);
      qc.invalidateQueries({ queryKey: ["admin-finance-coaches"] });
      toast.success(bps === null ? "Voltou pra escada padrão." : `Taxa: ${(bps / 100).toFixed(0)}%.`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao salvar.");
    } finally {
      setSavingRate(false);
    }
  };
  const payCommission = async () => {
    setPaying(true);
    try {
      const r = await adminDashboard.payCoachCommission(coach.id);
      qc.invalidateQueries({ queryKey: ["admin-finance-coaches"] });
      toast.success(`Pago: ${fmt(r.paid_cents)}.`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao pagar.");
    } finally {
      setPaying(false);
    }
  };

  return (
    <DetailDrawer open title={`Coach @${coach.username}`} icon={GraduationCap} onClose={onClose}>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Plano</p>
          <p className="mt-1 font-mono text-sm text-foreground">{coach.plan}</p>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">A pagar agora</p>
          <p className="mt-1 font-mono text-sm font-bold text-emerald-400">{payout ? fmt(payout.payable_cents) : "—"}</p>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Em carência (14d)</p>
          <p className="mt-1 font-mono text-sm text-amber-400 tabular-nums">{payout ? fmt(payout.held_cents) : "—"}</p>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Já pago</p>
          <p className="mt-1 font-mono text-sm text-muted-foreground tabular-nums">{payout ? fmt(payout.paid_cents) : "—"}</p>
        </div>
      </div>

      {payout && payout.payable_cents > 0 && (
        <button onClick={payCommission} disabled={paying}
          className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-emerald-500/90 px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-white hover:bg-emerald-500 transition-colors disabled:opacity-50">
          {paying && <Loader2 className="size-3.5 animate-spin" />} Marcar {fmt(payout.payable_cents)} como pago
        </button>
      )}

      {/* Taxa de comissão % (Parceiro Fundador). Vazio = escada padrão por volume. */}
      <div className="mt-3 rounded-lg border border-border bg-background p-3">
        <p className="font-mono text-[9px] uppercase text-muted-foreground">Taxa de comissão (%)</p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {payout?.commission_rate_bps != null
            ? <>Fixa: <span className="font-bold text-foreground">{(payout.commission_rate_bps / 100).toFixed(0)}%</span> (Parceiro Fundador)</>
            : "Escada padrão por volume: 1-9 → 15% · 10-29 → 20% · 30+ → 25%"}
        </p>
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text" inputMode="decimal" value={rateInput}
            onChange={(e) => setRateInput(e.target.value)}
            placeholder="vazio = escada"
            className="w-32 rounded-md border border-border bg-hud-surface px-2 py-1 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <span className="font-mono text-[10px] text-muted-foreground">% por aluno</span>
          <button
            onClick={saveRate}
            disabled={savingRate}
            className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {savingRate && <Loader2 className="size-3.5 animate-spin" />} Salvar
          </button>
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
  const [selected, setSelected] = useState<AdminUser | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", "coach-roster"],
    queryFn: () => adminDashboard.users({ role: "coach", limit: 200 }),
    staleTime: 30_000,
  });
  const { data: payoutData } = useQuery({
    queryKey: ["admin-finance-coaches"],
    queryFn: () => adminDashboard.coachPayouts(),
    staleTime: 30_000,
  });

  const coaches: AdminUser[] = data?.users ?? [];
  const payoutById = new Map<number, CoachPayout>();
  (payoutData?.coaches ?? []).forEach((p) => payoutById.set(p.id, p));

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
                {["Coach", "Plano", "Taxa", "A pagar", "Em carência", "Standing", ""].map((h) => (
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
                    <td className="px-4 py-3 font-mono tabular-nums text-center text-foreground">{po?.commission_rate_bps != null ? `${(po.commission_rate_bps / 100).toFixed(0)}%` : "escada"}</td>
                    <td className="px-4 py-3 font-mono tabular-nums font-bold text-emerald-400">{po && po.payable_cents > 0 ? fmt(po.payable_cents) : "—"}</td>
                    <td className="px-4 py-3 font-mono tabular-nums text-amber-400">{po && po.held_cents > 0 ? fmt(po.held_cents) : "—"}</td>
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
