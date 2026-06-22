import { cn } from "@/lib/utils";

// Single source of truth for status pill colors across the admin panel.
// Kills the inline color drift that existed between finance / users / coaches / tickets.

type Tone = "emerald" | "amber" | "red" | "muted";

const TONE_CLS: Record<Tone, string> = {
  emerald: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  amber:   "border-amber-500/40 bg-amber-500/10 text-amber-400",
  red:     "border-destructive/40 bg-destructive/10 text-destructive",
  muted:   "border-border bg-hud-elevated/50 text-muted-foreground",
};

// kind -> { tone, default label (pt-BR) }
const KIND_MAP: Record<string, { tone: Tone; label: string }> = {
  // emerald
  paid:      { tone: "emerald", label: "Pago" },
  active:    { tone: "emerald", label: "Ativo" },
  approved:  { tone: "emerald", label: "Aprovado" },
  paying:    { tone: "emerald", label: "Em dia" },
  "em dia":  { tone: "emerald", label: "Em dia" },
  done:      { tone: "emerald", label: "Concluído" },
  // amber
  pending:   { tone: "amber", label: "Pendente" },
  past_due:  { tone: "amber", label: "Atrasado" },
  idle:      { tone: "amber", label: "Ocioso" },
  forecast:  { tone: "amber", label: "Previsto" },
  due:       { tone: "amber", label: "A vencer" },
  // red
  failed:    { tone: "red", label: "Falhou" },
  canceled:  { tone: "red", label: "Cancelado" },
  open:      { tone: "red", label: "Aberto" },
  error:     { tone: "red", label: "Erro" },
  rejected:  { tone: "red", label: "Rejeitado" },
  // muted
  perk:      { tone: "muted", label: "Cortesia" },
  free:      { tone: "muted", label: "Free" },
  na:        { tone: "muted", label: "N/A" },
};

export function StatusBadge({
  kind,
  label,
  className,
}: {
  kind?: string | null;
  label?: string;
  className?: string;
}) {
  const key = (kind ?? "na").toString().toLowerCase();
  const meta = KIND_MAP[key] ?? { tone: "muted" as Tone, label: kind ?? "—" };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider border",
        TONE_CLS[meta.tone],
        className
      )}
    >
      {label ?? meta.label}
    </span>
  );
}
