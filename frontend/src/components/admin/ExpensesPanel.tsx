import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, Loader2, X, Check, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { adminDashboard, Expense, ExpenseInput, ExpenseRecurrence, ExpenseStatus } from "@/lib/api";
import { fmt } from "./format";
import { StatusBadge } from "./StatusBadge";

const CATEGORIES = ["infra", "llm", "solver", "domain", "gateway_fee", "ads", "other"];
const RECURRENCE: { value: ExpenseRecurrence; label: string }[] = [
  { value: "monthly", label: "Mensal" },
  { value: "annual", label: "Anual" },
  { value: "one_off", label: "Avulsa" },
];
const STATUS: { value: ExpenseStatus; label: string }[] = [
  { value: "forecast", label: "Previsto" },
  { value: "due", label: "A vencer" },
  { value: "paid", label: "Pago" },
];

const EMPTY: ExpenseInput = {
  category: "infra",
  amount_cents: 0,
  vendor: "",
  recurrence: "monthly",
  due_day: 1,
  status: "forecast",
  note: "",
  currency: "BRL",
};

function reaisToCents(v: string): number {
  const n = parseFloat(v.replace(/\./g, "").replace(",", "."));
  return Number.isNaN(n) ? 0 : Math.round(n * 100);
}

export function ExpensesPanel() {
  const qc = useQueryClient();
  const [form, setForm] = useState<ExpenseInput | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [amountStr, setAmountStr] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-expenses"],
    queryFn: adminDashboard.expenses,
    staleTime: 30_000,
  });
  const expenses: Expense[] = data?.expenses ?? [];

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-expenses"] });
    qc.invalidateQueries({ queryKey: ["admin-finance-cockpit"] });
  };

  const createMut = useMutation({
    mutationFn: (d: ExpenseInput) => adminDashboard.createExpense(d),
    onSuccess: () => { toast.success("Despesa criada"); invalidate(); closeForm(); },
    onError: (e: Error) => toast.error(e.message),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: number; d: Partial<ExpenseInput> }) => adminDashboard.updateExpense(id, d),
    onSuccess: () => { toast.success("Despesa atualizada"); invalidate(); closeForm(); },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => adminDashboard.deleteExpense(id),
    onSuccess: () => { toast.success("Despesa removida"); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const openNew = () => { setForm({ ...EMPTY }); setEditId(null); setAmountStr(""); };
  const openEdit = (e: Expense) => {
    setForm({
      category: e.category,
      amount_cents: e.amount_cents,
      vendor: e.vendor ?? "",
      recurrence: e.recurrence,
      due_day: e.due_day ?? undefined,
      status: e.status,
      note: e.note ?? "",
      currency: e.currency,
    });
    setEditId(e.id);
    setAmountStr((e.amount_cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }));
  };
  const closeForm = () => { setForm(null); setEditId(null); setAmountStr(""); };

  const submit = () => {
    if (!form) return;
    const payload = { ...form, amount_cents: reaisToCents(amountStr) };
    if (payload.amount_cents <= 0) { toast.error("Valor inválido"); return; }
    if (editId != null) updateMut.mutate({ id: editId, d: payload });
    else createMut.mutate(payload);
  };

  const saving = createMut.isPending || updateMut.isPending;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
      <div className="flex items-center gap-2 border-b border-border bg-hud-elevated/40 px-4 py-3">
        <Wallet className="size-3.5 text-primary" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Despesas (custos reais)</span>
        <button
          onClick={form ? closeForm : openNew}
          className="ml-auto inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/20 transition-colors"
        >
          {form ? <><X className="size-3" /> Fechar</> : <><Plus className="size-3" /> Nova despesa</>}
        </button>
      </div>

      {form && (
        <div className="border-b border-border bg-background/40 p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="space-y-1">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Categoria</span>
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="h-8 w-full rounded-md border border-border bg-background px-2 font-mono text-[11px] text-foreground focus:outline-none focus:border-primary">
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="space-y-1">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Vendor</span>
            <input value={form.vendor ?? ""} onChange={(e) => setForm({ ...form, vendor: e.target.value })}
              placeholder="ex: Hetzner"
              className="h-8 w-full rounded-md border border-border bg-background px-2 text-[11px] text-foreground focus:outline-none focus:border-primary" />
          </label>
          <label className="space-y-1">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Valor (R$)</span>
            <input value={amountStr} onChange={(e) => setAmountStr(e.target.value)} inputMode="decimal" placeholder="0,00"
              className="h-8 w-full rounded-md border border-border bg-background px-2 font-mono text-[11px] text-foreground focus:outline-none focus:border-primary" />
          </label>
          <label className="space-y-1">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Recorrência</span>
            <select value={form.recurrence} onChange={(e) => setForm({ ...form, recurrence: e.target.value as ExpenseRecurrence })}
              className="h-8 w-full rounded-md border border-border bg-background px-2 font-mono text-[11px] text-foreground focus:outline-none focus:border-primary">
              {RECURRENCE.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </label>
          <label className="space-y-1">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Dia de venc.</span>
            <input type="number" min={1} max={31} value={form.due_day ?? ""} onChange={(e) => setForm({ ...form, due_day: e.target.value ? Number(e.target.value) : undefined })}
              className="h-8 w-full rounded-md border border-border bg-background px-2 font-mono text-[11px] text-foreground focus:outline-none focus:border-primary" />
          </label>
          <label className="space-y-1">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Status</span>
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as ExpenseStatus })}
              className="h-8 w-full rounded-md border border-border bg-background px-2 font-mono text-[11px] text-foreground focus:outline-none focus:border-primary">
              {STATUS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <label className="space-y-1 col-span-2">
            <span className="font-mono text-[9px] uppercase text-muted-foreground">Observação</span>
            <input value={form.note ?? ""} onChange={(e) => setForm({ ...form, note: e.target.value })}
              className="h-8 w-full rounded-md border border-border bg-background px-2 text-[11px] text-foreground focus:outline-none focus:border-primary" />
          </label>
          <div className="col-span-2 md:col-span-4 flex justify-end">
            <button onClick={submit} disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground disabled:opacity-50 hover:bg-primary-glow transition-colors">
              {saving ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
              {editId != null ? "Salvar" : "Adicionar"}
            </button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="border-b border-border">
            <tr>
              {["Categoria", "Vendor", "Valor", "Recorrência", "Venc.", "Status", ""].map((h) => (
                <th key={h} className="px-4 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr><td colSpan={7} className="py-10 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
            ) : expenses.length === 0 ? (
              <tr><td colSpan={7} className="py-10 text-center text-muted-foreground">Nenhuma despesa cadastrada.</td></tr>
            ) : expenses.map((e) => (
              <tr key={e.id} className={cn("hover:bg-primary/5 transition-colors", !e.active && "opacity-50")}>
                <td className="px-4 py-2.5 font-mono text-[11px] uppercase text-foreground">{e.category}</td>
                <td className="px-4 py-2.5 text-foreground">{e.vendor || "—"}</td>
                <td className="px-4 py-2.5 font-mono tabular-nums font-bold text-foreground">{fmt(e.amount_cents)}</td>
                <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground">
                  {RECURRENCE.find((r) => r.value === e.recurrence)?.label ?? e.recurrence}
                </td>
                <td className="px-4 py-2.5 font-mono tabular-nums text-muted-foreground">{e.due_day ?? "—"}</td>
                <td className="px-4 py-2.5"><StatusBadge kind={e.status} /></td>
                <td className="px-4 py-2.5 text-right whitespace-nowrap">
                  <button onClick={() => openEdit(e)} className="rounded p-1 text-muted-foreground hover:text-primary transition-colors">
                    <Pencil className="size-3.5" />
                  </button>
                  <button onClick={() => { if (confirm(`Remover despesa ${e.category}?`)) deleteMut.mutate(e.id); }}
                    className="rounded p-1 text-muted-foreground/40 hover:text-destructive transition-colors">
                    <Trash2 className="size-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
