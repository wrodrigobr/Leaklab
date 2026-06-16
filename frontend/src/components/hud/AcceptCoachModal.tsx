import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X, Loader2, GraduationCap } from "lucide-react";
import { student } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Props {
  onClose: () => void;
}

export function AcceptCoachModal({ onClose }: Props) {
  const { refreshUser } = useAuth();
  const [key, setKey] = useState("");
  const [success, setSuccess] = useState<string | null>(null);

  const mutation = useMutation({
    // SEC-01: convite single-use (INV-…) usa o resgate; chave legada (COACH-…) usa o link.
    mutationFn: () => {
      const code = key.trim();
      return code.toUpperCase().startsWith("INV-") ? student.redeemInvite(code) : student.linkCoach(code);
    },
    onSuccess: async (data) => {
      setSuccess(`Vinculado ao coach ${data.coach.username}!`);
      await refreshUser();
      setTimeout(onClose, 2000);
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-hud-surface p-6 shadow-elevated space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GraduationCap className="size-5 text-primary" />
            <h2 className="font-semibold text-foreground">Vincular Coach</h2>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-4" />
          </button>
        </div>

        <p className="text-sm text-muted-foreground">
          Insira a chave de convite fornecida pelo seu coach para compartilhar seu histórico com ele.
        </p>

        {success ? (
          <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary text-center">
            {success}
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Código do convite
              </label>
              <input
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="INV-XXXXXXXX"
                className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm font-mono text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>

            {mutation.isError && (
              <p className="text-xs text-destructive">
                {mutation.error instanceof Error ? mutation.error.message : "Erro ao vincular"}
              </p>
            )}

            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !key.trim()}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow disabled:opacity-50"
            >
              {mutation.isPending && <Loader2 className="size-4 animate-spin" />}
              Vincular
            </button>
          </>
        )}
      </div>
    </div>
  );
}
