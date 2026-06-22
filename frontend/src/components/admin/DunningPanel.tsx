import { AlertTriangle, CheckCircle2, Mail, ChevronDown } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Dunning } from "@/lib/api";
import { fmt, daysSince } from "./format";
import { StatusBadge } from "./StatusBadge";

export function DunningPanel({ data, isLoading }: { data: Dunning | undefined; isLoading: boolean }) {
  const [showMore, setShowMore] = useState(false);
  const pastDue = data?.past_due ?? [];
  const failed = data?.recent_failed ?? [];
  const canceled = data?.recent_canceled ?? [];
  const dups = data?.duplicates ?? [];

  const clean = !isLoading && pastDue.length === 0 && failed.length === 0 && dups.length === 0;

  if (clean) {
    return (
      <div className="rounded-xl border border-primary/30 bg-primary/5 p-5 flex items-center gap-3">
        <CheckCircle2 className="size-5 text-primary shrink-0" />
        <div>
          <p className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary">Cobrança</p>
          <p className="text-sm text-foreground">Nenhum pagamento em risco, tudo em dia.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-destructive/30 bg-hud-surface">
      <div className="flex items-center gap-2 border-b border-destructive/30 bg-destructive/10 px-4 py-3">
        <AlertTriangle className="size-3.5 text-destructive" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-destructive">
          Cobrança em risco
        </span>
        <span className="ml-auto font-mono text-[10px] text-destructive">
          {pastDue.length} atrasado(s) · {failed.length} falha(s){dups.length ? ` · ${dups.length} duplicado(s)` : ""}
        </span>
      </div>

      <div className="divide-y divide-border">
        {pastDue.length === 0 ? (
          <p className="px-4 py-4 font-mono text-[11px] text-muted-foreground">Nenhum usuário atrasado.</p>
        ) : (
          pastDue.map((u) => {
            const overdue = daysSince(u.past_due_since ?? u.plan_expires_at);
            return (
              <div key={u.id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">@{u.username}</p>
                  <p className="truncate font-mono text-[10px] text-muted-foreground">{u.email}</p>
                </div>
                <span className="font-mono text-[10px] uppercase text-muted-foreground">{u.plan}</span>
                <StatusBadge kind="past_due" label={`${overdue}d`} />
                <a
                  href={`mailto:${u.email}`}
                  className="inline-flex items-center gap-1 font-mono text-[10px] text-primary hover:underline"
                >
                  <Mail className="size-3" /> contato
                </a>
              </div>
            );
          })
        )}
      </div>

      {(failed.length > 0 || canceled.length > 0 || dups.length > 0) && (
        <div className="border-t border-border">
          <button
            onClick={() => setShowMore((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-2.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground"
          >
            <span>Falhas recentes, cancelamentos e duplicados</span>
            <ChevronDown className={cn("size-3.5 transition-transform", showMore && "rotate-180")} />
          </button>
          {showMore && (
            <div className="space-y-4 border-t border-border px-4 py-3">
              {failed.length > 0 && (
                <div className="space-y-1">
                  <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Pagamentos falhos</p>
                  {failed.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-foreground">@{f.username} <span className="font-mono text-[10px] text-muted-foreground">· {f.gateway}</span></span>
                      <span className="font-mono tabular-nums text-destructive">{fmt(f.amount_cents)}</span>
                    </div>
                  ))}
                </div>
              )}
              {canceled.length > 0 && (
                <div className="space-y-1">
                  <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Cancelamentos recentes</p>
                  {canceled.map((c) => (
                    <div key={c.id} className="flex items-center justify-between text-xs">
                      <span className="text-foreground">@{c.username}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">{c.canceled_at ? new Date(c.canceled_at).toLocaleDateString("pt-BR") : "—"}</span>
                    </div>
                  ))}
                </div>
              )}
              {dups.length > 0 && (
                <div className="space-y-1">
                  <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">gateway_id duplicados</p>
                  {dups.map((d) => (
                    <div key={d.gateway_id} className="flex items-center justify-between text-xs">
                      <span className="truncate font-mono text-[10px] text-muted-foreground">{d.gateway_id}</span>
                      <span className="font-mono tabular-nums text-foreground">{d.n}× · {fmt(d.total_cents)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
