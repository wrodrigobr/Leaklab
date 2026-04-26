import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  Search, Star, Users, DollarSign, Globe, Filter,
  Loader2, GraduationCap, CheckCircle2, ChevronDown,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { coaches, PublicCoach, CoachDirectoryFilters } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Shared ────────────────────────────────────────────────────────────────────

const SPECIALTIES = [
  "Preflop", "Postflop", "MTT", "ICM", "Spin & Go",
  "Cash Game", "Heads Up", "Short Stack", "3bet Pots", "GTO",
];

const LANGUAGES = [
  { code: "pt", label: "Português" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
];

const SORT_OPTIONS = [
  { value: "rating",   label: "Melhor avaliado" },
  { value: "students", label: "Mais alunos" },
  { value: "price",    label: "Menor preço" },
];

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
        {r > 0 ? r.toFixed(1) : "—"} ({count})
      </span>
    </div>
  );
}

function CoachCard({ coach }: { coach: PublicCoach }) {
  const navigate = useNavigate();
  return (
    <div
      onClick={() => navigate(`/coaches/${coach.user_id}`)}
      className="rounded-xl border border-border bg-hud-surface p-5 flex flex-col gap-3 cursor-pointer hover:border-primary/50 transition-colors"
    >
      {/* Header */}
      <div className="flex gap-3 items-start">
        {coach.photo_url ? (
          <img src={coach.photo_url} alt={coach.display_name}
            className="size-12 rounded-full object-cover border border-border shrink-0" />
        ) : (
          <div className="size-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
            <GraduationCap className="size-5 text-primary" />
          </div>
        )}
        <div className="min-w-0">
          <p className="font-bold text-foreground truncate">
            {coach.display_name || coach.username}
          </p>
          {coach.stakes && (
            <p className="font-mono text-[10px] text-muted-foreground">{coach.stakes}</p>
          )}
          <StarRow rating={coach.avg_rating} count={coach.review_count} />
        </div>
      </div>

      {/* Bio */}
      {coach.bio && (
        <p className="text-xs text-muted-foreground line-clamp-2">{coach.bio}</p>
      )}

      {/* Specialties */}
      {coach.specialties.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {coach.specialties.slice(0, 4).map((s) => (
            <span key={s} className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary">
              {s}
            </span>
          ))}
          {coach.specialties.length > 4 && (
            <span className="font-mono text-[10px] text-muted-foreground">+{coach.specialties.length - 4}</span>
          )}
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center justify-between pt-1 border-t border-border">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
            <Users className="size-3" /> {coach.student_count} alunos
          </span>
          {coach.price_per_session != null && (
            <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
              <DollarSign className="size-3" /> R$ {coach.price_per_session}/sessão
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {coach.trial_available && (
            <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary">
              <CheckCircle2 className="size-2.5" /> Trial
            </span>
          )}
          {coach.languages.length > 0 && (
            <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
              <Globe className="size-3" /> {coach.languages.join("·").toUpperCase()}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Filters sidebar ───────────────────────────────────────────────────────────

function FilterPanel({
  filters, onChange,
}: {
  filters: CoachDirectoryFilters;
  onChange: (f: CoachDirectoryFilters) => void;
}) {
  const set = (key: keyof CoachDirectoryFilters, val: unknown) =>
    onChange({ ...filters, [key]: val || undefined });

  return (
    <aside className="space-y-5 shrink-0 w-52">
      <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
        <Filter className="size-3" /> Filtros
      </p>

      {/* Sort */}
      <div className="space-y-1.5">
        <p className="font-mono text-[10px] text-muted-foreground">Ordenar por</p>
        <div className="relative">
          <select
            value={filters.sort ?? "rating"}
            onChange={(e) => set("sort", e.target.value)}
            className="w-full appearance-none rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary pr-7"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
        </div>
      </div>

      {/* Specialty */}
      <div className="space-y-1.5">
        <p className="font-mono text-[10px] text-muted-foreground">Especialidade</p>
        <div className="flex flex-wrap gap-1">
          {SPECIALTIES.map((s) => (
            <button
              key={s}
              onClick={() => set("specialty", filters.specialty === s ? undefined : s)}
              className={cn(
                "rounded-full px-2 py-0.5 font-mono text-[10px] transition-colors border",
                filters.specialty === s
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:border-primary/50"
              )}
            >{s}</button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div className="space-y-1.5">
        <p className="font-mono text-[10px] text-muted-foreground">Idioma</p>
        <div className="flex flex-col gap-1">
          {LANGUAGES.map((l) => (
            <label key={l.code} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="language"
                checked={filters.language === l.code}
                onChange={() => set("language", filters.language === l.code ? undefined : l.code)}
                className="accent-primary"
              />
              <span className="text-xs">{l.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Price */}
      <div className="space-y-1.5">
        <p className="font-mono text-[10px] text-muted-foreground">Preço máx/sessão (R$)</p>
        <input
          type="number"
          min={0}
          step={10}
          value={filters.max_price ?? ""}
          onChange={(e) => set("max_price", e.target.value ? Number(e.target.value) : undefined)}
          placeholder="Sem limite"
          className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {/* Trial */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={!!filters.trial}
          onChange={(e) => set("trial", e.target.checked ? true : undefined)}
          className="accent-primary"
        />
        <span className="text-xs">Só com sessão trial</span>
      </label>

      {/* Reset */}
      {Object.keys(filters).some((k) => k !== "sort" && filters[k as keyof CoachDirectoryFilters]) && (
        <button
          onClick={() => onChange({ sort: filters.sort })}
          className="font-mono text-[10px] text-muted-foreground hover:text-foreground underline"
        >
          Limpar filtros
        </button>
      )}
    </aside>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CoachesDirectory() {
  const [filters, setFilters] = useState<CoachDirectoryFilters>({ sort: "rating" });
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["coaches-directory", filters, search],
    queryFn: () => coaches.list({ ...filters, q: search || undefined }),
    staleTime: 30_000,
  });

  const list = data?.coaches ?? [];

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-6xl px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Coaches Disponíveis</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Encontre um coach especializado nos seus spots de melhoria
          </p>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome…"
            className="w-full rounded-lg border border-border bg-hud-surface pl-9 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div className="flex gap-8">
          <FilterPanel filters={filters} onChange={setFilters} />

          {/* Grid */}
          <div className="flex-1">
            {isLoading ? (
              <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
                <Loader2 className="size-5 animate-spin" /> Carregando coaches…
              </div>
            ) : list.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <GraduationCap className="size-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Nenhum coach encontrado para os filtros selecionados.</p>
                <button
                  onClick={() => { setFilters({ sort: "rating" }); setSearch(""); }}
                  className="mt-3 font-mono text-xs text-primary hover:underline"
                >
                  Limpar filtros
                </button>
              </div>
            ) : (
              <>
                <p className="font-mono text-[10px] text-muted-foreground mb-3">
                  {list.length} coach{list.length !== 1 ? "es" : ""} encontrado{list.length !== 1 ? "s" : ""}
                </p>
                <div className="grid md:grid-cols-2 gap-4">
                  {list.map((c) => <CoachCard key={c.user_id} coach={c} />)}
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
