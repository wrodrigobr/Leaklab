import { useMemo, useState } from "react";
import { CalendarDays, List, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";
import { FinanceCalendar } from "@/lib/api";
import { fmt } from "./format";

type DayEvent = {
  kind: "inflow" | "outflow";
  label: string;
  amount_cents?: number;
  sub?: string;
};

const WEEKDAYS = ["D", "S", "T", "Q", "Q", "S", "S"];

function dayOfMonth(iso: string): number {
  const d = new Date(iso);
  return d.getDate();
}

export function PaymentCalendar({ data, month }: { data: FinanceCalendar | undefined; month: string }) {
  const [view, setView] = useState<"grid" | "list">("grid");
  const [selected, setSelected] = useState<number | null>(null);

  const [year, monthIdx] = useMemo(() => {
    const [y, m] = month.split("-").map(Number);
    return [y, m - 1];
  }, [month]);

  const daysInMonth = useMemo(() => new Date(year, monthIdx + 1, 0).getDate(), [year, monthIdx]);
  const firstWeekday = useMemo(() => new Date(year, monthIdx, 1).getDay(), [year, monthIdx]);

  // day-of-month -> events
  const byDay = useMemo(() => {
    const map: Record<number, DayEvent[]> = {};
    const push = (day: number, ev: DayEvent) => {
      if (day < 1 || day > daysInMonth) return;
      (map[day] ??= []).push(ev);
    };
    (data?.renewals_in ?? []).forEach((r) =>
      push(dayOfMonth(r.date), { kind: "inflow", label: `@${r.username}`, sub: `renovação ${r.plan}` })
    );
    (data?.payouts_out ?? []).forEach((p) =>
      push(dayOfMonth(p.date), { kind: "outflow", label: `repasse @${p.coach}`, amount_cents: p.amount_cents, sub: p.status })
    );
    (data?.expenses_due ?? []).forEach((e) =>
      push(e.due_day, { kind: "outflow", label: e.vendor || e.category, amount_cents: e.amount_cents, sub: e.category })
    );
    return map;
  }, [data, daysInMonth]);

  const linear = useMemo(() => {
    const rows: Array<{ day: number; ev: DayEvent }> = [];
    Object.keys(byDay)
      .map(Number)
      .sort((a, b) => a - b)
      .forEach((day) => byDay[day].forEach((ev) => rows.push({ day, ev })));
    return rows;
  }, [byDay]);

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays className="size-3.5 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Calendário de pagamentos</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setView("grid")}
            className={cn("rounded p-1.5", view === "grid" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}
          >
            <LayoutGrid className="size-3.5" />
          </button>
          <button
            onClick={() => setView("list")}
            className={cn("rounded p-1.5", view === "list" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}
          >
            <List className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 font-mono text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1"><span className="text-primary">●</span> entrada (renovação)</span>
        <span className="inline-flex items-center gap-1"><span className="text-amber-400">◆</span> saída (repasse / despesa)</span>
      </div>

      {view === "grid" ? (
        <div className="space-y-1">
          <div className="grid grid-cols-7 gap-1">
            {WEEKDAYS.map((w, i) => (
              <div key={i} className="text-center font-mono text-[9px] uppercase text-muted-foreground/60">{w}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {cells.map((d, i) => {
              if (d === null) return <div key={i} />;
              const evts = byDay[d] ?? [];
              const hasIn = evts.some((e) => e.kind === "inflow");
              const hasOut = evts.some((e) => e.kind === "outflow");
              return (
                <button
                  key={i}
                  onClick={() => setSelected(selected === d ? null : d)}
                  className={cn(
                    "relative aspect-square rounded-md border p-1 text-left transition-colors",
                    evts.length ? "border-border bg-background hover:bg-primary/5" : "border-border/40 bg-background/40",
                    selected === d && "ring-1 ring-primary"
                  )}
                >
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{d}</span>
                  <span className="absolute bottom-1 left-1 flex gap-0.5 text-[8px] leading-none">
                    {hasIn && <span className="text-primary">●</span>}
                    {hasOut && <span className="text-amber-400">◆</span>}
                  </span>
                </button>
              );
            })}
          </div>

          {selected != null && (byDay[selected]?.length ?? 0) > 0 && (
            <div className="mt-2 rounded-lg border border-border bg-background p-3 space-y-1.5">
              <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Dia {selected}</p>
              {byDay[selected].map((ev, i) => (
                <div key={i} className="flex items-center justify-between gap-2 text-xs">
                  <span className="flex items-center gap-1.5 text-foreground">
                    <span className={ev.kind === "inflow" ? "text-primary" : "text-amber-400"}>{ev.kind === "inflow" ? "●" : "◆"}</span>
                    {ev.label}
                    {ev.sub && <span className="font-mono text-[10px] text-muted-foreground">· {ev.sub}</span>}
                  </span>
                  {ev.amount_cents != null && (
                    <span className="font-mono tabular-nums text-foreground">{fmt(ev.amount_cents)}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-1 max-h-[280px] overflow-y-auto">
          {linear.length === 0 ? (
            <p className="py-6 text-center font-mono text-[11px] text-muted-foreground">Nenhum evento neste mês.</p>
          ) : (
            linear.map(({ day, ev }, i) => (
              <div key={i} className="flex items-center justify-between gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-xs">
                <span className="flex items-center gap-2 text-foreground">
                  <span className="w-6 font-mono tabular-nums text-muted-foreground">{day}</span>
                  <span className={ev.kind === "inflow" ? "text-primary" : "text-amber-400"}>{ev.kind === "inflow" ? "●" : "◆"}</span>
                  {ev.label}
                  {ev.sub && <span className="font-mono text-[10px] text-muted-foreground">· {ev.sub}</span>}
                </span>
                {ev.amount_cents != null && (
                  <span className="font-mono tabular-nums text-foreground">{fmt(ev.amount_cents)}</span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
