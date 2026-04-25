import { useQuery } from "@tanstack/react-query";
import { Copy, Check } from "lucide-react";
import { useState } from "react";
import { coachDashboard } from "@/lib/api";

export function InviteKeyWidget() {
  const [copied, setCopied] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["coach-invite-key"],
    queryFn: coachDashboard.inviteKey,
  });

  const copy = () => {
    if (!data?.invite_key) return;
    navigator.clipboard.writeText(data.invite_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-2">
      <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
        Chave de convite
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 rounded-md bg-background border border-border px-3 py-2 font-mono text-sm text-foreground tracking-widest">
          {isLoading ? "…" : (data?.invite_key ?? "—")}
        </code>
        <button
          onClick={copy}
          disabled={isLoading || !data?.invite_key}
          className="flex size-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors disabled:opacity-40"
          title="Copiar chave"
        >
          {copied ? <Check className="size-4 text-primary" /> : <Copy className="size-4" />}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Compartilhe esta chave com seus alunos para que possam se vincular ao seu perfil.
      </p>
    </div>
  );
}
