import { useEffect, useState } from "react";
import {
  BookOpen,
  Video,
  GraduationCap,
  Target,
  Dumbbell,
  BarChart2,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { cn } from "@/lib/utils";
import { study, StudyPlanResponse, StudyCard } from "@/lib/api";

// ── Meta tables ───────────────────────────────────────────────────────────────

const NIVEL_META: Record<string, { label: string; cls: string }> = {
  iniciante:     { label: "Iniciante",     cls: "bg-destructive/10 text-destructive ring-1 ring-destructive/30" },
  intermediario: { label: "Intermediário", cls: "bg-warning/10 text-warning ring-1 ring-warning/30" },
  avancado:      { label: "Avançado",      cls: "bg-primary/10 text-primary ring-1 ring-primary/30" },
};

const PRIORITY_BORDER: Record<string, string> = {
  p1: "border-destructive/50",
  p2: "border-destructive/30",
  p3: "border-warning/50",
  p4: "border-warning/30",
  p5: "border-border",
  p6: "border-border",
};

const PRIORITY_BADGE: Record<string, string> = {
  p1: "bg-destructive/10 text-destructive ring-1 ring-destructive/30",
  p2: "bg-destructive/10 text-destructive ring-1 ring-destructive/20",
  p3: "bg-warning/10 text-warning ring-1 ring-warning/30",
  p4: "bg-warning/10 text-warning ring-1 ring-warning/20",
  p5: "bg-muted/40 text-muted-foreground ring-1 ring-border",
  p6: "bg-muted/40 text-muted-foreground ring-1 ring-border",
};

const SUIT_COLOR: Record<string, string> = {
  "♠": "text-foreground",
  "♣": "text-foreground",
  "♥": "text-[hsl(var(--card-suit-red))]",
  "♦": "text-[hsl(var(--card-suit-red))]",
};

// ── StudyCardPanel ─────────────────────────────────────────────────────────────

function StudyCardPanel({ card, index }: { card: StudyCard; index: number }) {
  const [resourcesOpen, setResourcesOpen] = useState(false);

  const prio  = card.prioridade?.toLowerCase() ?? `p${index + 1}`;
  const label = prio.toUpperCase();
  const suitColor = SUIT_COLOR[card.icone] ?? "text-muted-foreground";
  const hasResources =
    card.recursos &&
    (card.recursos.livros?.length > 0 ||
      card.recursos.videos?.length > 0 ||
      card.recursos.curso);

  return (
    <article
      className={cn(
        "flex flex-col gap-4 rounded-xl border bg-hud-surface p-5 transition-colors",
        PRIORITY_BORDER[prio] ?? "border-border"
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "mt-0.5 shrink-0 rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2",
            PRIORITY_BADGE[prio] ?? PRIORITY_BADGE["p6"]
          )}
        >
          {label}
        </span>
        <div className="flex items-start gap-2 min-w-0">
          <span className={cn("text-lg leading-none shrink-0 select-none", suitColor)}>
            {card.icone}
          </span>
          <h3 className="font-mono text-sm font-bold text-foreground leading-snug">
            {card.titulo}
          </h3>
        </div>
      </div>

      {/* Diagnóstico */}
      {card.diagnostico && (
        <p className="text-xs leading-relaxed text-muted-foreground border-l-2 border-border pl-3">
          {card.diagnostico}
        </p>
      )}

      {/* Conceitos */}
      {card.conceitos?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {card.conceitos.map((c, i) => (
            <span
              key={i}
              className="rounded-sm bg-secondary px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
            >
              {c}
            </span>
          ))}
        </div>
      )}

      {/* Exercício */}
      {card.exercicio && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 space-y-1">
          <div className="flex items-center gap-1.5">
            <Dumbbell className="size-3 text-primary" aria-hidden />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
              Exercício
            </span>
          </div>
          <p className="text-xs leading-relaxed text-foreground">{card.exercicio}</p>
        </div>
      )}

      {/* Métrica */}
      {card.metrica && (
        <div className="flex items-start gap-1.5">
          <Target className="size-3 shrink-0 mt-0.5 text-muted-foreground" aria-hidden />
          <p className="text-xs text-muted-foreground leading-relaxed">
            <span className="font-semibold text-foreground">Meta:</span> {card.metrica}
          </p>
        </div>
      )}

      {/* Recursos (collapsible) */}
      {hasResources && (
        <div className="border-t border-border pt-3">
          <button
            onClick={() => setResourcesOpen((o) => !o)}
            className="flex w-full items-center justify-between gap-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className="flex items-center gap-1.5">
              <BarChart2 className="size-3" aria-hidden />
              Recursos de estudo
            </span>
            {resourcesOpen
              ? <ChevronUp className="size-3" />
              : <ChevronDown className="size-3" />}
          </button>

          {resourcesOpen && (
            <div className="mt-3 space-y-2.5">
              {card.recursos.livros?.length > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="size-3 text-muted-foreground" aria-hidden />
                    <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Livros</span>
                  </div>
                  <ul className="space-y-0.5 pl-5">
                    {card.recursos.livros.map((l, i) => (
                      <li key={i} className="text-xs text-foreground list-disc">{l}</li>
                    ))}
                  </ul>
                </div>
              )}
              {card.recursos.videos?.length > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5">
                    <Video className="size-3 text-muted-foreground" aria-hidden />
                    <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Vídeos</span>
                  </div>
                  <ul className="space-y-0.5 pl-5">
                    {card.recursos.videos.map((v, i) => (
                      <li key={i} className="text-xs text-foreground list-disc">{v}</li>
                    ))}
                  </ul>
                </div>
              )}
              {card.recursos.curso && (
                <div className="flex items-start gap-1.5">
                  <GraduationCap className="size-3 shrink-0 mt-0.5 text-muted-foreground" aria-hidden />
                  <p className="text-xs text-foreground">{card.recursos.curso}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

const DAYS_OPTIONS = [30, 60, 90] as const;
type Days = (typeof DAYS_OPTIONS)[number];

const StudyPlan = () => {
  const [plan, setPlan]       = useState<StudyPlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [days, setDays]       = useState<Days>(90);

  const fetchPlan = (d: Days) => {
    setLoading(true);
    setError("");
    study
      .plan(d)
      .then((data) => {
        if (data.error && !data.cards?.length) {
          setError(data.error);
        } else {
          setPlan(data);
        }
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Erro ao gerar plano de estudos")
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchPlan(days);
  }, [days]);

  const nivelMeta = plan ? (NIVEL_META[plan.nivel] ?? NIVEL_META["intermediario"]) : null;

  return (
    <HudLayout
      eyebrow="Plano de Estudos"
      title="Seu roadmap de melhoria"
      description="Análise dos seus leaks reais + plano de estudo personalizado gerado pelo Coach IA."
    >
      {/* Controls bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Período</span>
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => { setDays(d); }}
              className={cn(
                "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                days === d
                  ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {d}d
            </button>
          ))}
        </div>

        <button
          onClick={() => fetchPlan(days)}
          disabled={loading}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-secondary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground hover:border-primary/30 disabled:opacity-50"
        >
          <RefreshCw className={cn("size-3.5", loading && "animate-spin")} aria-hidden />
          Regenerar plano
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
          <Loader2 className="size-6 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">
            Coach IA analisando seus leaks…
          </span>
          <p className="text-xs text-center max-w-xs">
            Isso pode levar alguns segundos na primeira vez.
          </p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <AlertCircle className="size-6 text-destructive" />
          <p className="text-sm text-destructive text-center max-w-sm">{error}</p>
          <p className="text-xs text-muted-foreground text-center max-w-xs">
            Importe pelo menos um torneio para que o Coach IA possa gerar seu plano personalizado.
          </p>
        </div>
      )}

      {/* Plan */}
      {!loading && !error && plan && (
        <>
          {/* Summary header */}
          <section className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              {nivelMeta && (
                <span className={cn("rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2", nivelMeta.cls)}>
                  Nível: {nivelMeta.label}
                </span>
              )}
              <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
                {plan.cards.length} módulos de estudo · {days} dias de dados
              </span>
            </div>
            {plan.resumo && (
              <p className="text-sm leading-relaxed text-foreground">{plan.resumo}</p>
            )}
          </section>

          {/* Cards grid */}
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {plan.cards.map((card, i) => (
              <StudyCardPanel key={i} card={card} index={i} />
            ))}
          </section>
        </>
      )}
    </HudLayout>
  );
};

export default StudyPlan;
