import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Check, Plus, Ban, Loader2 } from "lucide-react";
import { useState } from "react";
import { coachDashboard, CoachInvite } from "@/lib/api";

// SEC-01: gerenciador de convites single-use (1 por aluno; não é mais uma chave passável).
const STATUS_META: Record<CoachInvite["status"], { label: string; cls: string }> = {
  active:   { label: "ativo",     cls: "text-primary" },
  redeemed: { label: "resgatado", cls: "text-emerald-400" },
  revoked:  { label: "revogado",  cls: "text-muted-foreground" },
  expired:  { label: "expirado",  cls: "text-amber-400" },
};

export function InviteKeyWidget() {
  const qc = useQueryClient();
  const [copied, setCopied] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["coach-invites"], queryFn: coachDashboard.listInvites });

  const create = useMutation({
    mutationFn: () => coachDashboard.createInvite(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["coach-invites"] }),
  });
  const revoke = useMutation({
    mutationFn: (id: number) => coachDashboard.revokeInvite(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["coach-invites"] }),
  });

  const copy = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(code);
    setTimeout(() => setCopied(null), 2000);
  };

  const invites = data?.invites ?? [];

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Convites</p>
        <button
          onClick={() => create.mutate()}
          disabled={create.isPending}
          className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 disabled:opacity-50 transition-colors"
        >
          {create.isPending ? <Loader2 className="size-3 animate-spin" /> : <Plus className="size-3" />} Convidar aluno
        </button>
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">
        Gere um convite por aluno. Cada código é de <b className="text-foreground">uso único</b> e expira em 30 dias — não dá pra repassar.
      </p>

      {isLoading ? (
        <p className="font-mono text-[10px] text-muted-foreground py-2">…</p>
      ) : invites.length === 0 ? (
        <p className="font-mono text-[10px] text-muted-foreground py-2">Nenhum convite ainda. Clique em "Convidar aluno".</p>
      ) : (
        <div className="space-y-1.5">
          {invites.slice(0, 8).map((inv) => {
            const m = STATUS_META[inv.status];
            return (
              <div key={inv.id} className="flex items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5">
                <code className="flex-1 min-w-0 truncate font-mono text-xs text-foreground tracking-wide">{inv.code}</code>
                {inv.status === "redeemed" && inv.used_by_username ? (
                  <span className="font-mono text-[9px] text-emerald-400 shrink-0">→ {inv.used_by_username}</span>
                ) : (
                  <span className={`font-mono text-[9px] uppercase shrink-0 ${m.cls}`}>{m.label}</span>
                )}
                {inv.status === "active" && (
                  <>
                    <button onClick={() => copy(inv.code)} title="Copiar código"
                      className="text-muted-foreground hover:text-primary transition-colors shrink-0">
                      {copied === inv.code ? <Check className="size-3.5 text-primary" /> : <Copy className="size-3.5" />}
                    </button>
                    <button onClick={() => revoke.mutate(inv.id)} title="Revogar"
                      className="text-muted-foreground hover:text-destructive transition-colors shrink-0">
                      <Ban className="size-3.5" />
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
