import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UserCircle, Star, Loader2, Check, X, Plus, Trash2,
  Youtube, Twitch, Twitter, Instagram, Globe, DollarSign, Clock,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import {
  coachDashboard, CoachProfile as CoachProfileType,
  BiggestResult, CoachReview, ReviewStats,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Shared helpers ─────────────────────────────────────────────────────────────

const inputCls = "w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary";

const LANGUAGE_OPTIONS = [
  { code: "pt", label: "Português" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
];

const COACHING_STYLES = [
  "Revisão de Hand History",
  "Sessão ao vivo",
  "Análise escrita",
  "Teoria + prática",
  "Solver study",
];

function Field({ label, children, editing }: { label: string; children: React.ReactNode; editing: boolean }) {
  return (
    <div className="space-y-1">
      <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{label}</p>
      <div className="text-sm text-foreground">{children}</div>
    </div>
  );
}

function StarRating({ value, onChange }: { value: number; onChange?: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n} type="button"
          onClick={() => onChange?.(n)}
          onMouseEnter={() => onChange && setHover(n)}
          onMouseLeave={() => onChange && setHover(0)}
          className={cn("transition-colors", onChange ? "cursor-pointer" : "cursor-default")}
        >
          <Star className={cn("size-4", (hover || value) >= n ? "fill-amber-400 text-amber-400" : "text-muted-foreground")} />
        </button>
      ))}
    </div>
  );
}

function RatingBar({ label, n, total }: { label: string; n: number; total: number }) {
  const pct = total > 0 ? Math.round((n / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="font-mono w-4 text-right text-muted-foreground">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        <div className="h-full bg-amber-400 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono w-6 text-muted-foreground">{n}</span>
    </div>
  );
}

// ── Tab: Perfil ────────────────────────────────────────────────────────────────

function ProfileSection() {
  const qc = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ["coach-profile"],
    queryFn: () => coachDashboard.getProfile(),
  });

  const [form, setForm] = useState<Partial<CoachProfileType>>({});
  const [editing, setEditing] = useState(false);
  const [newResult, setNewResult] = useState<Partial<BiggestResult>>({});
  const [addingResult, setAddingResult] = useState(false);

  const save = useMutation({
    mutationFn: () => coachDashboard.saveProfile({ ...profile, ...form }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["coach-profile"] });
      setEditing(false);
      setForm({});
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-8">
        <Loader2 className="size-4 animate-spin" /> Carregando…
      </div>
    );
  }

  const p = { ...profile, ...form } as CoachProfileType;
  const langs: string[] = p.languages ?? ["pt"];
  const results: BiggestResult[] = p.biggest_results ?? [];

  const set = (key: keyof CoachProfileType, val: unknown) =>
    setForm((f) => ({ ...f, [key]: val }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-2">
          <UserCircle className="size-3.5" /> Perfil Público
        </p>
        {!editing ? (
          <button onClick={() => setEditing(true)}
            className="font-mono text-[11px] border border-border px-3 py-1.5 rounded text-muted-foreground hover:text-foreground">
            Editar
          </button>
        ) : (
          <div className="flex gap-2">
            <button onClick={() => { setEditing(false); setForm({}); }}
              className="font-mono text-[11px] border border-border px-3 py-1.5 rounded text-muted-foreground">
              Cancelar
            </button>
            <button onClick={() => save.mutate()} disabled={save.isPending}
              className="flex items-center gap-1.5 font-mono text-[11px] bg-primary text-primary-foreground px-3 py-1.5 rounded disabled:opacity-50">
              {save.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />} Salvar
            </button>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3 md:col-span-2">
          <Field label="Nome exibido" editing={editing}>
            {editing
              ? <input value={p.display_name ?? ""} onChange={e => set("display_name", e.target.value)} className={inputCls} />
              : <span>{p.display_name || <em className="text-muted-foreground">—</em>}</span>}
          </Field>
          <Field label="Bio" editing={editing}>
            {editing
              ? <textarea rows={3} value={p.bio ?? ""} onChange={e => set("bio", e.target.value)} className={inputCls + " resize-none"} />
              : <span className="text-sm whitespace-pre-wrap">{p.bio || <em className="text-muted-foreground">—</em>}</span>}
          </Field>
        </div>

        <Field label="Foto (URL)" editing={editing}>
          {editing
            ? <input value={p.photo_url ?? ""} onChange={e => set("photo_url", e.target.value)} placeholder="https://…" className={inputCls} />
            : p.photo_url ? <img src={p.photo_url} alt="foto" className="size-12 rounded-full object-cover border border-border" /> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>

        <Field label="Anos de experiência" editing={editing}>
          {editing
            ? <input type="number" min={0} max={40} value={p.experience_years ?? ""} onChange={e => set("experience_years", e.target.value ? Number(e.target.value) : null)} className={inputCls} />
            : <span>{p.experience_years != null ? `${p.experience_years} anos` : <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Stakes jogados" editing={editing}>
          {editing
            ? <input value={p.stakes ?? ""} onChange={e => set("stakes", e.target.value)} placeholder="ex: MTT $5–$50" className={inputCls} />
            : <span>{p.stakes || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Método de coaching" editing={editing}>
          {editing
            ? <select value={p.coaching_style ?? ""} onChange={e => set("coaching_style", e.target.value)} className={inputCls}>
                <option value="">Selecionar…</option>
                {COACHING_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            : <span>{p.coaching_style || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Idiomas" editing={editing}>
          {editing
            ? <div className="flex flex-wrap gap-2">
                {LANGUAGE_OPTIONS.map(l => (
                  <label key={l.code} className="flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" checked={langs.includes(l.code)}
                      onChange={e => {
                        const next = e.target.checked ? [...langs, l.code] : langs.filter(x => x !== l.code);
                        set("languages", next);
                      }}
                      className="accent-primary"
                    />
                    <span className="text-xs">{l.label}</span>
                  </label>
                ))}
              </div>
            : <span>{langs.map(c => LANGUAGE_OPTIONS.find(l => l.code === c)?.label ?? c).join(", ") || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Disponibilidade" editing={editing}>
          {editing
            ? <input value={p.availability ?? ""} onChange={e => set("availability", e.target.value)} placeholder="ex: seg/qua/sex tarde" className={inputCls} />
            : <span className="flex items-center gap-1.5"><Clock className="size-3 text-muted-foreground" />{p.availability || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Preço por sessão (R$)" editing={editing}>
          {editing
            ? <input type="number" min={0} value={p.price_per_session ?? ""} onChange={e => set("price_per_session", e.target.value ? Number(e.target.value) : null)} className={inputCls} />
            : <span className="flex items-center gap-1"><DollarSign className="size-3 text-muted-foreground" />{p.price_per_session != null ? `R$ ${p.price_per_session}` : <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Pacote mensal (R$)" editing={editing}>
          {editing
            ? <input type="number" min={0} value={p.price_monthly ?? ""} onChange={e => set("price_monthly", e.target.value ? Number(e.target.value) : null)} className={inputCls} />
            : <span className="flex items-center gap-1"><DollarSign className="size-3 text-muted-foreground" />{p.price_monthly != null ? `R$ ${p.price_monthly}` : <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        <Field label="Sessão de avaliação gratuita?" editing={editing}>
          {editing
            ? <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={!!p.trial_available} onChange={e => set("trial_available", e.target.checked)} className="accent-primary" />
                <span className="text-sm">Sim, ofereço sessão de avaliação</span>
              </label>
            : <span>{p.trial_available ? "✓ Disponível" : "Não disponível"}</span>}
        </Field>

        <Field label="YouTube" editing={editing}>
          {editing
            ? <input value={p.social_youtube ?? ""} onChange={e => set("social_youtube", e.target.value)} placeholder="https://youtube.com/@…" className={inputCls} />
            : p.social_youtube ? <a href={p.social_youtube} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-primary text-sm"><Youtube className="size-3.5" />{p.social_youtube}</a> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>

        <Field label="Twitch" editing={editing}>
          {editing
            ? <input value={p.social_twitch ?? ""} onChange={e => set("social_twitch", e.target.value)} placeholder="https://twitch.tv/…" className={inputCls} />
            : p.social_twitch ? <a href={p.social_twitch} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-primary text-sm"><Twitch className="size-3.5" />{p.social_twitch}</a> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>

        <Field label="Twitter / X" editing={editing}>
          {editing
            ? <input value={p.social_twitter ?? ""} onChange={e => set("social_twitter", e.target.value)} placeholder="https://x.com/…" className={inputCls} />
            : p.social_twitter ? <a href={p.social_twitter} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-primary text-sm"><Twitter className="size-3.5" />{p.social_twitter}</a> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>

        <Field label="Instagram" editing={editing}>
          {editing
            ? <input value={p.social_instagram ?? ""} onChange={e => set("social_instagram", e.target.value)} placeholder="https://instagram.com/…" className={inputCls} />
            : p.social_instagram ? <a href={p.social_instagram} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-primary text-sm"><Instagram className="size-3.5" />{p.social_instagram}</a> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>

        <Field label="Email / Link de contato" editing={editing}>
          {editing
            ? <input value={p.contact_email ?? ""} onChange={e => set("contact_email", e.target.value)} className={inputCls} />
            : p.contact_email ? <a href={`mailto:${p.contact_email}`} className="flex items-center gap-1.5 text-primary text-sm"><Globe className="size-3.5" />{p.contact_email}</a> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>
      </div>

      {/* Maiores resultados */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Maiores Resultados</p>
          {editing && (
            <button onClick={() => setAddingResult(true)} className="flex items-center gap-1 font-mono text-[10px] text-primary">
              <Plus className="size-3" /> Adicionar
            </button>
          )}
        </div>
        {addingResult && editing && (
          <div className="flex gap-2 items-end flex-wrap p-3 border border-border rounded bg-card">
            <div className="space-y-1">
              <label className="font-mono text-[10px] text-muted-foreground">Torneio</label>
              <input className={inputCls + " w-40"} placeholder="BSOP Main Event" value={newResult.name ?? ""} onChange={e => setNewResult(r => ({ ...r, name: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <label className="font-mono text-[10px] text-muted-foreground">Prêmio</label>
              <input className={inputCls + " w-24"} placeholder="R$ 15.000" value={newResult.prize ?? ""} onChange={e => setNewResult(r => ({ ...r, prize: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <label className="font-mono text-[10px] text-muted-foreground">Ano</label>
              <input type="number" className={inputCls + " w-20"} placeholder="2024" value={newResult.year ?? ""} onChange={e => setNewResult(r => ({ ...r, year: Number(e.target.value) }))} />
            </div>
            <div className="flex gap-1">
              <button
                onClick={() => {
                  if (newResult.name && newResult.prize && newResult.year) {
                    set("biggest_results", [...results, newResult as BiggestResult]);
                    setNewResult({});
                    setAddingResult(false);
                  }
                }}
                className="p-1.5 rounded bg-primary text-primary-foreground">
                <Check className="size-3.5" />
              </button>
              <button onClick={() => { setAddingResult(false); setNewResult({}); }} className="p-1.5 rounded border border-border text-muted-foreground">
                <X className="size-3.5" />
              </button>
            </div>
          </div>
        )}
        {results.length === 0 && !addingResult && (
          <p className="text-sm text-muted-foreground italic">Nenhum resultado cadastrado.</p>
        )}
        <div className="space-y-1">
          {results.map((r, i) => (
            <div key={i} className="flex items-center justify-between rounded border border-border bg-card px-3 py-2">
              <div>
                <span className="font-mono text-xs font-bold text-foreground">{r.name}</span>
                <span className="font-mono text-xs text-muted-foreground ml-2">{r.prize} · {r.year}</span>
              </div>
              {editing && (
                <button onClick={() => set("biggest_results", results.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-destructive">
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {editing && (
        <Field label="Visível no diretório público?" editing={true}>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={!!p.is_public} onChange={e => set("is_public", e.target.checked)} className="accent-primary" />
            <span className="text-sm">Aparecer no diretório de coaches</span>
          </label>
        </Field>
      )}
    </div>
  );
}

// ── Tab: Avaliações ────────────────────────────────────────────────────────────

function AvaliacoesSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["coach-reviews"],
    queryFn: () => coachDashboard.getReviews(20),
  });

  const stats: ReviewStats | undefined = data?.stats;
  const reviews: CoachReview[] = data?.reviews ?? [];

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-card p-5">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="size-4 animate-spin" /> Carregando…
          </div>
        ) : (stats?.total ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">Nenhuma avaliação recebida ainda.</p>
        ) : (
          <div className="flex gap-8 items-center">
            <div className="text-center">
              <p className="text-5xl font-bold text-foreground">{stats?.avg_rating?.toFixed(1) ?? "—"}</p>
              <StarRating value={Math.round(stats?.avg_rating ?? 0)} />
              <p className="font-mono text-[10px] text-muted-foreground mt-1">{stats?.total} avaliações</p>
            </div>
            <div className="flex-1 space-y-1">
              {([5, 4, 3, 2, 1] as const).map(n => (
                <RatingBar key={n} label={String(n)} n={(stats as Record<string, number>)?.[`r${n}`] ?? 0} total={stats?.total ?? 0} />
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {reviews.map(r => (
          <div key={r.id} className="rounded border border-border bg-card px-4 py-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-foreground">{r.username}</span>
                <StarRating value={r.rating} />
              </div>
              <span className="font-mono text-[10px] text-muted-foreground">{r.updated_at?.slice(0, 10)}</span>
            </div>
            {r.review_text && <p className="text-sm text-muted-foreground">{r.review_text}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "perfil" | "avaliacoes";

export default function CoachProfile() {
  const [tab, setTab] = useState<Tab>("perfil");

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-3xl px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Meu Perfil</h1>
          <p className="text-sm text-muted-foreground mt-1">Configure como você aparece no diretório público</p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border gap-0">
          {([
            { id: "perfil",     label: "Perfil Público",  icon: UserCircle },
            { id: "avaliacoes", label: "Avaliações",       icon: Star },
          ] as { id: Tab; label: string; icon: React.ElementType }[]).map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors",
                tab === t.id
                  ? "text-primary border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-border bg-hud-surface p-6">
          {tab === "perfil"     && <ProfileSection />}
          {tab === "avaliacoes" && <AvaliacoesSection />}
        </div>
      </main>
    </div>
  );
}
