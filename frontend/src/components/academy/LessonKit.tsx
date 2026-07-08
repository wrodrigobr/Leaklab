import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Check, X, ChevronRight, Lightbulb, AlertTriangle, KeyRound,
  Target, GraduationCap, BookMarked, ClipboardCheck, Radar, Sparkles, Info,
} from "lucide-react";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import type { ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";

// Baralho ATUAL do produto — os mesmos SVGs que o Replayer/PokerTableV3 usam
// (public/cards/XX.svg). code = "Ah" | "10s" | "Kd"...  → /cards/AH.svg, 10S.svg, KD.svg
function deckCardSrc(code: string): string {
  const rank = code.slice(0, -1).toUpperCase();      // "T" já vira "10" abaixo
  const suit = code.slice(-1).toUpperCase();
  return `/cards/${rank === "T" ? "10" : rank}${suit}.svg`;
}

export function DeckCard({ code, className }: { code: string; className?: string }) {
  return (
    <img
      src={deckCardSrc(code)}
      alt={code}
      className={cn("h-16 w-auto rounded-md shadow-md ring-1 ring-black/20", className)}
      draggable={false}
    />
  );
}

/**
 * LessonKit — blocos de apresentação reutilizáveis para as AULAS da Academia.
 * Mesma filosofia dos helpers do /docs, mas compartilhados entre lições para
 * consistência. Usa NOSSOS visuais (PokerTable, PlayingCard) — nada externo.
 */

// ── Seção numerada ──────────────────────────────────────────────────────────────

export function LessonSection({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-bold text-primary ring-1 ring-primary/25">
          {n}
        </span>
        <h2 className="text-lg font-bold tracking-tight text-foreground">{title}</h2>
      </div>
      <div className="space-y-4 pl-10 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

// ── Texto (aceita <strong>/<em> via html) ────────────────────────────────────────

export function Prose({ html }: { html: string }) {
  return <p dangerouslySetInnerHTML={{ __html: html }} />;
}

// ── Callout (dica / atenção / regra-chave) ───────────────────────────────────────

type Tone = "tip" | "warn" | "key" | "coach" | "curio" | "note";

export function Callout({ tone, title, children }: { tone: Tone; title: string; children: React.ReactNode }) {
  const cfg: Record<Tone, { ring: string; bg: string; text: string; Icon: React.ElementType }> = {
    tip:   { ring: "ring-sky-500/25",     bg: "bg-sky-500/8",     text: "text-sky-300",     Icon: Lightbulb },
    warn:  { ring: "ring-amber-500/25",   bg: "bg-amber-500/8",   text: "text-amber-300",   Icon: AlertTriangle },
    key:   { ring: "ring-emerald-500/25", bg: "bg-emerald-500/8", text: "text-emerald-300", Icon: KeyRound },
    coach: { ring: "ring-primary/25",     bg: "bg-primary/8",     text: "text-primary",     Icon: GraduationCap },
    curio: { ring: "ring-violet-500/25",  bg: "bg-violet-500/8",  text: "text-violet-300",  Icon: Sparkles },
    note:  { ring: "ring-border",         bg: "bg-hud-surface/60", text: "text-muted-foreground", Icon: Info },
  };
  const c = cfg[tone];
  return (
    <div className={cn("rounded-xl p-4 ring-1", c.ring, c.bg)}>
      <div className={cn("mb-1 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest", c.text)}>
        <c.Icon className="size-3.5" aria-hidden />
        {title}
      </div>
      <div className="text-sm leading-relaxed text-foreground/90">{children}</div>
    </div>
  );
}

// ── Tabela ───────────────────────────────────────────────────────────────────────

export function LessonTable({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-hud-surface">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left font-mono font-bold uppercase tracking-widest text-muted-foreground">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0">
              {row.map((cell, j) => <td key={j} className="px-3 py-2 text-foreground">{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Cena de mesa (a mesa ATUAL do produto — PokerTableV3 — com dados didáticos) ───

export function TableScene({ step, hero, heroCards, bb = 1, caption }: {
  step: ReplayStep; hero: string; heroCards: string[]; bb?: number; caption?: string;
}) {
  return (
    <figure className="space-y-2">
      <div className="w-full">
        <PokerTableV3 step={step} hero={hero} heroCards={heroCards} bb={bb} betUnit="bb" orientation="landscape" />
      </div>
      {caption && <figcaption className="text-center text-xs text-muted-foreground">{caption}</figcaption>}
    </figure>
  );
}

// ── Linha de cartas (mãos de exemplo, baralho ATUAL) ─────────────────────────────

export function CardRow({ groups, caption }: {
  groups: { cards: string[]; label: string; tone?: "good" | "bad" }[];
  caption?: string;
}) {
  return (
    <figure className="space-y-2">
      <div className="flex flex-wrap items-start justify-center gap-6 rounded-xl border border-dashed border-border bg-hud-surface/50 p-4">
        {groups.map((g, i) => (
          <div key={i} className="flex flex-col items-center gap-1.5">
            <div className="flex gap-1">
              {g.cards.map((c, j) => <DeckCard key={j} code={c} />)}
            </div>
            <span className={cn(
              "font-mono text-[10px] font-bold uppercase tracking-wider",
              g.tone === "good" ? "text-emerald-400" : g.tone === "bad" ? "text-rose-400" : "text-muted-foreground",
            )}>
              {g.label}
            </span>
          </div>
        ))}
      </div>
      {caption && <figcaption className="text-center text-xs text-muted-foreground">{caption}</figcaption>}
    </figure>
  );
}

// ── Resumo (key takeaways) ───────────────────────────────────────────────────────

export function Takeaways({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5">
      <div className="mb-3 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-emerald-300">
        <KeyRound className="size-3.5" aria-hidden />
        {title}
      </div>
      <ul className="space-y-2">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-foreground/90">
            <Check className="mt-0.5 size-4 shrink-0 text-emerald-400" aria-hidden />
            <span dangerouslySetInnerHTML={{ __html: it }} />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Objetivos de aprendizagem ────────────────────────────────────────────────────

export function Objectives({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-5">
      <div className="mb-3 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-primary">
        <Target className="size-3.5" aria-hidden /> {title}
      </div>
      <ul className="space-y-2">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-foreground/90">
            <ChevronRight className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span dangerouslySetInnerHTML={{ __html: it }} />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Comparação: recreativo × regular × profissional ─────────────────────────────

export function PlayerCompare({ title, cols, rows }: {
  title: string; cols: [string, string, string];
  rows: { label: string; rec: string; reg: string; pro: string }[];
}) {
  return (
    <figure className="space-y-2">
      <figcaption className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{title}</figcaption>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-hud-surface font-mono text-[10px] uppercase tracking-widest">
              <th className="px-3 py-2 text-left text-muted-foreground"></th>
              <th className="px-3 py-2 text-left text-rose-300">{cols[0]}</th>
              <th className="px-3 py-2 text-left text-amber-300">{cols[1]}</th>
              <th className="px-3 py-2 text-left text-emerald-300">{cols[2]}</th>
            </tr>
          </thead>
          <tbody className="align-top">
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-border/50 last:border-0">
                <td className="px-3 py-2 font-semibold text-foreground">{r.label}</td>
                <td className="px-3 py-2 text-muted-foreground">{r.rec}</td>
                <td className="px-3 py-2 text-muted-foreground">{r.reg}</td>
                <td className="px-3 py-2 text-foreground/90">{r.pro}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

// ── Erros frequentes (erro · por quê · correção) ─────────────────────────────────

export function Mistakes({ title, items }: {
  title: string; items: { mistake: string; why: string; fix: string }[];
}) {
  const { t } = useTranslation("academy");
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-rose-300">
        <AlertTriangle className="size-3.5" aria-hidden /> {title}
      </div>
      <ol className="space-y-3">
        {items.map((m, i) => (
          <li key={i} className="rounded-lg border border-rose-500/15 bg-rose-500/5 p-3">
            <p className="text-sm font-semibold text-foreground">
              <span className="text-rose-400">{i + 1}.</span> <span dangerouslySetInnerHTML={{ __html: m.mistake }} />
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              <span className="font-bold text-foreground/70">{t("lesson.why")}: </span>
              <span dangerouslySetInnerHTML={{ __html: m.why }} />
            </p>
            <p className="mt-0.5 text-xs text-emerald-300/90">
              <span className="font-bold">{t("lesson.fix")}: </span>
              <span dangerouslySetInnerHTML={{ __html: m.fix }} />
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ── Checklist antes de agir ──────────────────────────────────────────────────────

export function Checklist({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface/50 p-5">
      <div className="mb-3 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-foreground">
        <ClipboardCheck className="size-3.5" aria-hidden /> {title}
      </div>
      <ul className="space-y-2.5">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm text-foreground/90">
            <span className="mt-0.5 size-4 shrink-0 rounded border border-primary/40 bg-primary/5" aria-hidden />
            <span dangerouslySetInnerHTML={{ __html: it }} />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Glossário ────────────────────────────────────────────────────────────────────

export function Glossary({ title, terms }: { title: string; terms: { term: string; def: string }[] }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        <BookMarked className="size-3.5" aria-hidden /> {title}
      </div>
      <dl className="grid gap-2 sm:grid-cols-2">
        {terms.map((tm, i) => (
          <div key={i} className="rounded-lg border border-border/60 bg-background/40 px-3 py-2">
            <dt className="text-sm font-bold text-foreground">{tm.term}</dt>
            <dd className="mt-0.5 text-xs leading-relaxed text-muted-foreground" dangerouslySetInnerHTML={{ __html: tm.def }} />
          </div>
        ))}
      </dl>
    </div>
  );
}

// ── "Como o GrindLab identifica isso automaticamente" ────────────────────────────

export function GrindLabDetects({ title, intro, items }: { title: string; intro: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/10 to-transparent p-5">
      <div className="mb-2 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-primary">
        <Radar className="size-3.5" aria-hidden /> {title}
      </div>
      <p className="mb-3 text-sm leading-relaxed text-foreground/90" dangerouslySetInnerHTML={{ __html: intro }} />
      <ul className="space-y-2">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-foreground/90">
            <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span dangerouslySetInnerHTML={{ __html: it }} />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Verificação de conhecimento (quiz inline, client-side) ───────────────────────

export interface QuizItem { q: string; options: string[]; correct: number; explain: string; }

export function LessonQuiz({ title, items }: { title: string; items: QuizItem[] }) {
  const { t } = useTranslation("academy");
  return (
    <div className="rounded-xl border border-border bg-hud-surface/50 p-5">
      <div className="mb-4 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-primary">
        <Check className="size-3.5" aria-hidden />
        {title}
      </div>
      <div className="space-y-6">
        {items.map((it, i) => <QuizRow key={i} item={it} idx={i} checkLabel={t("lesson.check")} />)}
      </div>
    </div>
  );
}

function QuizRow({ item, idx, checkLabel }: { item: QuizItem; idx: number; checkLabel: string }) {
  const [picked, setPicked] = useState<number | null>(null);
  const answered = picked !== null;
  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-foreground">{idx + 1}. {item.q}</p>
      <div className="flex flex-col gap-2">
        {item.options.map((opt, j) => {
          const isCorrect = j === item.correct;
          const isPicked = j === picked;
          return (
            <button
              key={j}
              disabled={answered}
              onClick={() => setPicked(j)}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                !answered && "border-border hover:border-primary/40 hover:bg-hud-surface",
                answered && isCorrect && "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
                answered && isPicked && !isCorrect && "border-rose-500/40 bg-rose-500/10 text-rose-200",
                answered && !isPicked && !isCorrect && "border-border opacity-50",
              )}
            >
              {answered && isCorrect && <Check className="size-4 shrink-0 text-emerald-400" aria-hidden />}
              {answered && isPicked && !isCorrect && <X className="size-4 shrink-0 text-rose-400" aria-hidden />}
              <span>{opt}</span>
            </button>
          );
        })}
      </div>
      {answered && (
        <p className="rounded-lg bg-background/60 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          <span className="font-bold text-foreground">{checkLabel}: </span>
          <span dangerouslySetInnerHTML={{ __html: item.explain }} />
        </p>
      )}
    </div>
  );
}

// ── CTA de próximo passo ─────────────────────────────────────────────────────────

export function NextStep({ to, label, sub }: { to: string; label: string; sub: string }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between gap-3 rounded-xl border border-primary/25 bg-primary/5 px-5 py-4 transition-colors hover:bg-primary/10"
    >
      <div>
        <div className="text-sm font-bold text-foreground">{label}</div>
        <div className="text-xs text-muted-foreground">{sub}</div>
      </div>
      <ChevronRight className="size-5 shrink-0 text-primary" aria-hidden />
    </Link>
  );
}
