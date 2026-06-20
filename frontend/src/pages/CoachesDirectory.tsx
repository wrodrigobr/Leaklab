import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Search, Star, Users, DollarSign, Globe, SlidersHorizontal,
  Loader2, GraduationCap, CheckCircle2, ChevronDown, ArrowUpRight, X,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { coaches, PublicCoach, CoachDirectoryFilters } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Shared ────────────────────────────────────────────────────────────────────

// Foco MTT: só especialidades de torneio (sem SNG/Cash Game).
const SPECIALTIES = [
  "Preflop", "Postflop", "ICM", "Final Table", "Bubble",
  "PKO", "Short Stack", "3bet Pots", "Heads Up", "GTO",
];

const LANGUAGES = [
  { code: "pt", label: "Português" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
];

const SORT_KEYS = ["rating", "students", "price"] as const;

function StarRow({ rating, count }: { rating: number | null; count: number }) {
  const r = rating ?? 0;
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <Star
            key={n}
            className={cn("size-3", r >= n ? "fill-amber-400 text-amber-400" : "text-border")}
          />
        ))}
      </div>
      <span className="font-mono text-[10px] text-muted-foreground">
        {r > 0 ? r.toFixed(1) : "0.0"} ({count})
      </span>
    </div>
  );
}

// ── Coach card ────────────────────────────────────────────────────────────────

function CoachCard({ coach }: { coach: PublicCoach }) {
  const navigate = useNavigate();
  const { t } = useTranslation("coaches");
  return (
    <button
      type="button"
      onClick={() => navigate(`/coaches/${coach.user_id}`)}
      className={cn(
        "group relative flex flex-col gap-3 overflow-hidden rounded-2xl border border-border",
        "bg-gradient-to-b from-hud-surface to-hud-surface/40 p-5 text-left",
        "transition-all duration-200 hover:-translate-y-1 hover:border-primary/60",
        "hover:shadow-[0_0_0_1px_rgba(45,212,191,0.35),0_18px_40px_-20px_rgba(45,212,191,0.45)]",
        "focus:outline-none focus-visible:border-primary/60"
      )}
    >
      {/* glow accent */}
      <div className="pointer-events-none absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      {/* Header */}
      <div className="flex items-start gap-3">
        {coach.photo_url ? (
          <img
            src={coach.photo_url}
            alt={coach.display_name}
            className="size-14 shrink-0 rounded-2xl border border-border object-cover"
          />
        ) : (
          <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10">
            <GraduationCap className="size-6 text-primary" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-heading text-base font-bold text-foreground">
            {coach.display_name || coach.username}
          </p>
          {coach.stakes && (
            <p className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {coach.stakes}
            </p>
          )}
          <div className="mt-1">
            <StarRow rating={coach.avg_rating} count={coach.review_count} />
          </div>
        </div>
        <ArrowUpRight className="size-4 shrink-0 text-muted-foreground transition-all group-hover:text-primary group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
      </div>

      {/* Bio */}
      {coach.bio && (
        <p className="line-clamp-2 min-h-[2lh] text-xs leading-relaxed text-muted-foreground">
          {coach.bio}
        </p>
      )}

      {/* Specialties */}
      {coach.specialties.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {coach.specialties.slice(0, 3).map((s) => (
            <span
              key={s}
              className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary"
            >
              {s}
            </span>
          ))}
          {coach.specialties.length > 3 && (
            <span className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
              +{coach.specialties.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Footer stats */}
      <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-3">
        <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
          <Users className="size-3 text-primary/70" />
          {t("card.studentsCount", { count: coach.student_count })}
        </span>
        {coach.price_per_session != null && (
          <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
            <DollarSign className="size-3 text-primary/70" />
            R$ {coach.price_per_session}{t("card.ratePerHour")}
          </span>
        )}
        {coach.languages.length > 0 && (
          <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
            <Globe className="size-3 text-primary/70" />
            {coach.languages.join(" · ").toUpperCase()}
          </span>
        )}
        {coach.trial_available && (
          <span className="ml-auto flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-medium text-primary">
            <CheckCircle2 className="size-2.5" /> {t("filters.trial")}
          </span>
        )}
      </div>
    </button>
  );
}

// ── Secondary filters popover (price + trial) ──────────────────────────────────

function MoreFiltersPopover({
  filters, set,
}: {
  filters: CoachDirectoryFilters;
  set: (key: keyof CoachDirectoryFilters, val: unknown) => void;
}) {
  const { t } = useTranslation("coaches");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const count = (filters.max_price != null ? 1 : 0) + (filters.trial ? 1 : 0);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition-colors",
          count > 0 || open
            ? "border-primary/50 bg-primary/10 text-foreground"
            : "border-border bg-hud-surface text-muted-foreground hover:border-primary/40"
        )}
      >
        <SlidersHorizontal className="size-4" />
        <span className="hidden sm:inline">{t("filters.more")}</span>
        {count > 0 && (
          <span className="flex size-4 items-center justify-center rounded-full bg-primary font-mono text-[10px] text-primary-foreground">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-64 space-y-4 rounded-2xl border border-border bg-hud-surface p-4 shadow-xl">
          <div className="space-y-1.5">
            <label className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {t("filters.maxPrice")}
            </label>
            <input
              type="number"
              min={0}
              step={10}
              value={filters.max_price ?? ""}
              onChange={(e) => set("max_price", e.target.value ? Number(e.target.value) : undefined)}
              placeholder={t("filters.noLimit")}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <label className="flex cursor-pointer items-center justify-between gap-2">
            <span className="text-sm text-foreground">{t("filters.trialOnly")}</span>
            <input
              type="checkbox"
              checked={!!filters.trial}
              onChange={(e) => set("trial", e.target.checked ? true : undefined)}
              className="size-4 accent-primary"
            />
          </label>
        </div>
      )}
    </div>
  );
}

// ── Sort dropdown ──────────────────────────────────────────────────────────────

function SortSelect({
  value, onChange,
}: {
  value: CoachDirectoryFilters["sort"];
  onChange: (v: CoachDirectoryFilters["sort"]) => void;
}) {
  const { t } = useTranslation("coaches");
  return (
    <div className="relative shrink-0">
      <select
        value={value ?? "rating"}
        onChange={(e) => onChange(e.target.value as CoachDirectoryFilters["sort"])}
        className="h-full w-full appearance-none rounded-xl border border-border bg-hud-surface py-2.5 pl-3 pr-9 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary sm:text-sm"
      >
        {SORT_KEYS.map((k) => (
          <option key={k} value={k}>{t(`sort.${k}`)}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CoachesDirectory() {
  const { t } = useTranslation("coaches");
  const [filters, setFilters] = useState<CoachDirectoryFilters>({ sort: "rating" });
  const [search, setSearch] = useState("");

  const set = (key: keyof CoachDirectoryFilters, val: unknown) =>
    setFilters((f) => ({ ...f, [key]: (val ?? undefined) as never }));

  const activeFilterCount = Object.keys(filters).filter(
    (k) => k !== "sort" && filters[k as keyof CoachDirectoryFilters] != null
  ).length + (search ? 1 : 0);

  const { data, isLoading } = useQuery({
    queryKey: ["coaches-directory", filters, search],
    queryFn: () => coaches.list({ ...filters, q: search || undefined }),
    staleTime: 30_000,
  });

  const list = data?.coaches ?? [];

  const clearAll = () => {
    setFilters({ sort: "rating" });
    setSearch("");
  };

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {/* Title */}
        <div className="mb-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
            {t("directory.eyebrow")}
          </p>
          <h1 className="mt-1 font-heading text-3xl font-bold text-foreground sm:text-4xl">
            {t("directory.title")}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {t("directory.description")}
          </p>
        </div>

        {/* Sticky toolbar */}
        <div className="sticky top-2 z-10 mb-6 rounded-2xl border border-border bg-hud-surface/80 p-3 backdrop-blur supports-[backdrop-filter]:bg-hud-surface/60">
          {/* Row 1: search + sort + more */}
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("filters.search")}
                className="w-full rounded-xl border border-border bg-background py-2.5 pl-9 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="flex gap-2">
              <SortSelect value={filters.sort} onChange={(v) => set("sort", v)} />
              <MoreFiltersPopover filters={filters} set={set} />
            </div>
          </div>

          {/* Row 2: specialty chips (scrollable) */}
          <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {SPECIALTIES.map((s) => {
              const active = filters.specialty === s;
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => set("specialty", active ? undefined : s)}
                  className={cn(
                    "shrink-0 rounded-full border px-3 py-1 font-mono text-[11px] transition-colors",
                    active
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                  )}
                >
                  {s}
                </button>
              );
            })}
          </div>

          {/* Row 3: language toggles */}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {t("filters.language")}:
            </span>
            {LANGUAGES.map((l) => {
              const active = filters.language === l.code;
              return (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => set("language", active ? undefined : l.code)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 text-[11px] transition-colors",
                    active
                      ? "border-primary/60 bg-primary/15 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  )}
                >
                  {l.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Results bar */}
        <div className="mb-4 flex items-center justify-between gap-3">
          <p className="font-mono text-xs text-muted-foreground">
            {isLoading ? "…" : t("directory.resultsCount", { count: list.length })}
          </p>
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className="flex items-center gap-1 rounded-full border border-border px-2.5 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
            >
              <X className="size-3" /> {t("filters.clearAll")}
            </button>
          )}
        </div>

        {/* Grid / states */}
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" /> {t("directory.loading")}
          </div>
        ) : list.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-hud-surface/40 py-24 text-center text-muted-foreground">
            <GraduationCap className="mx-auto mb-3 size-10 opacity-30" />
            <p className="font-heading text-base font-bold text-foreground">{t("empty.title")}</p>
            <p className="mx-auto mt-1 max-w-sm text-sm">{t("empty.description")}</p>
            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={clearAll}
                className="mt-4 font-mono text-xs text-primary hover:underline"
              >
                {t("filters.clearAll")}
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {list.map((c) => <CoachCard key={c.user_id} coach={c} />)}
          </div>
        )}
      </main>
    </div>
  );
}
