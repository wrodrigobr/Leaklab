import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Users, TrendingUp, Award, Activity, AlertTriangle,
  Play, Filter, ChevronDown, ChevronUp, LayoutDashboard,
  UserCircle, Star, Loader2, Check, X, Plus, Trash2,
  Youtube, Twitch, Twitter, Globe, DollarSign, Clock, Languages,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { InviteKeyWidget } from "@/components/coach/InviteKeyWidget";
import { StudentRow } from "@/components/coach/StudentRow";
import { coachDashboard, MultiStudentDecision, CommonLeak, CoachProfile, BiggestResult, CoachReview, ReviewStats } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── shared ────────────────────────────────────────────────────────────────────

const SCORE_COLOR = (s: number) =>
  s >= 80 ? "text-primary" : s >= 60 ? "text-amber-400" : "text-destructive";

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: React.ElementType }) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-1">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-3.5" />
        <span className="font-mono text-[10px] uppercase tracking-widest-2">{label}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
    </div>
  );
}

// ── Tab: Alunos ────────────────────────────────────────────────────────────────

function AlunosTab() {
  const { data: studentsData, isLoading } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });
  const { data: impact } = useQuery({
    queryKey: ["coach-impact"],
    queryFn: () => coachDashboard.impact(30),
  });

  const students = studentsData?.students ?? [];

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-2 space-y-3">
        {isLoading && <p className="text-sm text-muted-foreground animate-pulse">Carregando…</p>}
        {!isLoading && students.length === 0 && (
          <div className="rounded-xl border border-dashed border-border p-8 text-center space-y-2">
            <p className="text-sm text-muted-foreground">Nenhum aluno vinculado ainda.</p>
            <p className="text-xs text-muted-foreground">Compartilhe sua chave de convite para que alunos possam se vincular.</p>
          </div>
        )}
        <div className="space-y-2">
          {students.map((s) => <StudentRow key={s.id} student={s} />)}
        </div>
      </div>

      <div className="space-y-4">
        <InviteKeyWidget />

        {impact?.top_leaks && impact.top_leaks.length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              Leaks em comum
            </p>
            <div className="space-y-2">
              {impact.top_leaks.slice(0, 5).map((leak) => (
                <div key={leak.spot} className="flex items-center justify-between">
                  <span className="text-xs text-foreground truncate max-w-[140px]">{leak.spot}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{leak.n}x</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: Atenção Urgente (BACK-003) ───────────────────────────────────────────

const STREETS = ["preflop", "flop", "turn", "river"];
const LABELS: { value: string; label: string }[] = [
  { value: "clear_mistake", label: "Erro claro" },
  { value: "small_mistake", label: "Erro pequeno" },
];

function UrgentTab() {
  const navigate = useNavigate();
  const { data: studentsData } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });

  const [studentFilter, setStudentFilter] = useState<number | undefined>();
  const [streetFilter, setStreetFilter]   = useState<string | undefined>();
  const [labelFilter, setLabelFilter]     = useState<string | undefined>();

  const { data, isLoading } = useQuery({
    queryKey: ["coach-all-worst", studentFilter, streetFilter, labelFilter],
    queryFn: () => coachDashboard.allWorstDecisions({
      n: 30,
      student_id: studentFilter,
      street: streetFilter,
      label: labelFilter,
    }),
  });

  const students = studentsData?.students ?? [];
  const decisions: MultiStudentDecision[] = data?.decisions ?? [];

  const FilterBtn = ({
    active, onClick, children,
  }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      className={cn(
        "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors",
        active
          ? "bg-primary/10 text-primary ring-1 ring-primary/30"
          : "text-muted-foreground hover:bg-secondary hover:text-foreground"
      )}
    >
      {children}
    </button>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Filter className="size-3.5 text-muted-foreground shrink-0" />

        {/* Student filter */}
        <FilterBtn active={!studentFilter} onClick={() => setStudentFilter(undefined)}>Todos</FilterBtn>
        {students.map((s) => (
          <FilterBtn key={s.id} active={studentFilter === s.id} onClick={() => setStudentFilter(s.id)}>
            {s.username}
          </FilterBtn>
        ))}

        <span className="text-border mx-1">|</span>

        {/* Street filter */}
        <FilterBtn active={!streetFilter} onClick={() => setStreetFilter(undefined)}>Todas streets</FilterBtn>
        {STREETS.map((st) => (
          <FilterBtn key={st} active={streetFilter === st} onClick={() => setStreetFilter(st)}>
            {st}
          </FilterBtn>
        ))}

        <span className="text-border mx-1">|</span>

        {/* Label filter */}
        <FilterBtn active={!labelFilter} onClick={() => setLabelFilter(undefined)}>Todos erros</FilterBtn>
        {LABELS.map((l) => (
          <FilterBtn key={l.value} active={labelFilter === l.value} onClick={() => setLabelFilter(l.value)}>
            {l.label}
          </FilterBtn>
        ))}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse py-6">Carregando decisões…</p>}

      {!isLoading && decisions.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Nenhuma decisão crítica encontrada com os filtros atuais.
        </p>
      )}

      {decisions.length > 0 && (
        <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-background/50">
                {["Aluno", "Street", "Jogou", "Correto", "Score", "Label", ""].map((h, i) => (
                  <th key={i} className="px-4 py-2.5 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {decisions.map((d) => (
                <tr key={d.id} className="border-b border-border/40 last:border-0 hover:bg-primary/5 transition-colors">
                  <td className="px-4 py-2.5 text-xs font-medium text-foreground">{d.username}</td>
                  <td className="px-4 py-2.5 font-mono text-xs capitalize text-muted-foreground">{d.street}</td>
                  <td className="px-4 py-2.5 text-xs text-destructive font-medium">{d.action_taken}</td>
                  <td className="px-4 py-2.5 text-xs text-primary font-medium">{d.best_action}</td>
                  <td className={`px-4 py-2.5 font-mono text-xs font-bold ${SCORE_COLOR(d.score)}`}>{d.score}</td>
                  <td className="px-4 py-2.5">
                    <span className={cn(
                      "font-mono text-[10px] font-bold px-2 py-0.5 rounded",
                      d.label === "clear_mistake"
                        ? "bg-destructive/10 text-destructive ring-1 ring-destructive/30"
                        : "bg-amber-400/10 text-amber-400 ring-1 ring-amber-400/30"
                    )}>
                      {d.label === "clear_mistake" ? "Claro" : "Pequeno"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => navigate(`/replayer?t=${d.tournament_id}&h=${d.hand_id}&student=${d.student_id}`)}
                      className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors"
                    >
                      <Play className="size-3" /> Replay
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Leaks Sistêmicos (BACK-004) ──────────────────────────────────────────

function LeakRow({ leak }: { leak: CommonLeak }) {
  const [expanded, setExpanded] = useState(false);
  const multi = leak.num_students > 1;

  return (
    <div className="rounded-lg border border-border bg-hud-surface overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-primary/5 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {multi && (
            <span className="shrink-0 rounded-sm bg-destructive/10 text-destructive font-mono text-[10px] font-bold px-2 py-0.5 ring-1 ring-destructive/30">
              {leak.num_students} alunos
            </span>
          )}
          <span className="text-sm font-medium text-foreground truncate">{leak.spot}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-3">
          <span className="font-mono text-[10px] text-muted-foreground">{leak.total_n}x total</span>
          <span className={`font-mono text-sm font-bold ${SCORE_COLOR(leak.avg_score)}`}>
            {leak.avg_score.toFixed(1)} pts
          </span>
          {expanded ? <ChevronUp className="size-3.5 text-muted-foreground" /> : <ChevronDown className="size-3.5 text-muted-foreground" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border bg-background/50 px-4 py-3 space-y-2">
          <p className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground mb-2">
            Alunos afetados
          </p>
          {leak.students.map((s) => (
            <div key={s.id} className="flex items-center justify-between text-xs">
              <span className="text-foreground font-medium">{s.username}</span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[10px] text-muted-foreground">{s.n}x</span>
                <span className={`font-mono text-xs font-bold ${SCORE_COLOR(s.avg_score)}`}>
                  {s.avg_score} pts
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LeaksTab() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ["coach-common-leaks", days],
    queryFn: () => coachDashboard.commonLeaks(days),
  });

  const leaks = data?.leaks ?? [];
  const systemic = leaks.filter((l) => l.num_students > 1);
  const individual = leaks.filter((l) => l.num_students === 1);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Período:</span>
        {[30, 60, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={cn(
              "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors",
              days === d
                ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            )}
          >
            {d}d
          </button>
        ))}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse py-6">Analisando leaks…</p>}

      {!isLoading && leaks.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Nenhum leak encontrado no período selecionado.
        </p>
      )}

      {systemic.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-destructive">
            Leaks sistêmicos — afetam múltiplos alunos
          </p>
          {systemic.map((l) => <LeakRow key={l.spot} leak={l} />)}
        </div>
      )}

      {individual.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Leaks individuais
          </p>
          {individual.map((l) => <LeakRow key={l.spot} leak={l} />)}
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

// ── Tab: Perfil Público ───────────────────────────────────────────────────────

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

function StarRating({ value, onChange }: { value: number; onChange?: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange?.(n)}
          onMouseEnter={() => onChange && setHover(n)}
          onMouseLeave={() => onChange && setHover(0)}
          className={cn("transition-colors", onChange ? "cursor-pointer" : "cursor-default")}
        >
          <Star
            className={cn("size-4", (hover || value) >= n ? "fill-amber-400 text-amber-400" : "text-muted-foreground")}
          />
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

function ProfileTab() {
  const qc = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ["coach-profile"],
    queryFn: () => coachDashboard.getProfile(),
  });

  const [form, setForm] = useState<Partial<CoachProfile>>({});
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

  if (isLoading) return <div className="flex items-center gap-2 text-muted-foreground py-8"><Loader2 className="size-4 animate-spin" />Carregando…</div>;

  const p = { ...profile, ...form } as CoachProfile;
  const langs: string[] = p.languages ?? ["pt"];
  const results: BiggestResult[] = p.biggest_results ?? [];

  const set = (key: keyof CoachProfile, val: unknown) =>
    setForm((f) => ({ ...f, [key]: val }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-xs font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-2">
          <UserCircle className="size-3.5" /> Perfil Público
        </h3>
        {!editing ? (
          <button onClick={() => setEditing(true)} className="font-mono text-[11px] border border-border px-3 py-1.5 rounded text-muted-foreground hover:text-foreground">
            Editar
          </button>
        ) : (
          <div className="flex gap-2">
            <button onClick={() => { setEditing(false); setForm({}); }} className="font-mono text-[11px] border border-border px-3 py-1.5 rounded text-muted-foreground">
              Cancelar
            </button>
            <button
              onClick={() => save.mutate()}
              disabled={save.isPending}
              className="flex items-center gap-1.5 font-mono text-[11px] bg-primary text-primary-foreground px-3 py-1.5 rounded disabled:opacity-50"
            >
              {save.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />} Salvar
            </button>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Nome e bio */}
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

        {/* URL da foto */}
        <Field label="Foto (URL)" editing={editing}>
          {editing
            ? <input value={p.photo_url ?? ""} onChange={e => set("photo_url", e.target.value)} placeholder="https://…" className={inputCls} />
            : p.photo_url ? <img src={p.photo_url} alt="foto" className="size-12 rounded-full object-cover border border-border" /> : <em className="text-muted-foreground text-sm">—</em>}
        </Field>

        {/* Anos de experiência */}
        <Field label="Anos de experiência" editing={editing}>
          {editing
            ? <input type="number" min={0} max={40} value={p.experience_years ?? ""} onChange={e => set("experience_years", e.target.value ? Number(e.target.value) : null)} className={inputCls} />
            : <span>{p.experience_years != null ? `${p.experience_years} anos` : <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        {/* Stakes */}
        <Field label="Stakes jogados" editing={editing}>
          {editing
            ? <input value={p.stakes ?? ""} onChange={e => set("stakes", e.target.value)} placeholder='ex: MTT $5–$50' className={inputCls} />
            : <span>{p.stakes || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        {/* Estilo de coaching */}
        <Field label="Método de coaching" editing={editing}>
          {editing
            ? <select value={p.coaching_style ?? ""} onChange={e => set("coaching_style", e.target.value)} className={inputCls}>
                <option value="">Selecionar…</option>
                {COACHING_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            : <span>{p.coaching_style || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        {/* Idiomas */}
        <Field label="Idiomas" editing={editing}>
          {editing
            ? <div className="flex flex-wrap gap-2">
                {LANGUAGE_OPTIONS.map(l => (
                  <label key={l.code} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={langs.includes(l.code)}
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

        {/* Disponibilidade */}
        <Field label="Disponibilidade" editing={editing}>
          {editing
            ? <input value={p.availability ?? ""} onChange={e => set("availability", e.target.value)} placeholder='ex: seg/qua/sex tarde' className={inputCls} />
            : <span className="flex items-center gap-1.5"><Clock className="size-3 text-muted-foreground" />{p.availability || <em className="text-muted-foreground">—</em>}</span>}
        </Field>

        {/* Preços */}
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

        {/* Trial */}
        <Field label="Sessão de avaliação gratuita?" editing={editing}>
          {editing
            ? <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={!!p.trial_available} onChange={e => set("trial_available", e.target.checked)} className="accent-primary" />
                <span className="text-sm">Sim, ofereço sessão de avaliação</span>
              </label>
            : <span>{p.trial_available ? "✓ Disponível" : "Não disponível"}</span>}
        </Field>

        {/* Redes sociais */}
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
                className="p-1.5 rounded bg-primary text-primary-foreground"><Check className="size-3.5" /></button>
              <button onClick={() => { setAddingResult(false); setNewResult({}); }} className="p-1.5 rounded border border-border text-muted-foreground"><X className="size-3.5" /></button>
            </div>
          </div>
        )}
        {results.length === 0 && !addingResult && <p className="text-sm text-muted-foreground italic">Nenhum resultado cadastrado.</p>}
        <div className="space-y-1">
          {results.map((r, i) => (
            <div key={i} className="flex items-center justify-between rounded border border-border bg-card px-3 py-2">
              <div>
                <span className="font-mono text-xs font-bold text-foreground">{r.name}</span>
                <span className="font-mono text-xs text-muted-foreground ml-2">{r.prize} · {r.year}</span>
              </div>
              {editing && (
                <button onClick={() => set("biggest_results", results.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-destructive"><Trash2 className="size-3.5" /></button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Visibilidade */}
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

// ── Tab: Avaliações ───────────────────────────────────────────────────────────

function AvaliacoesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["coach-reviews"],
    queryFn: () => coachDashboard.getReviews(20),
  });

  const stats: ReviewStats | undefined = data?.stats;
  const reviews: CoachReview[] = data?.reviews ?? [];

  return (
    <div className="space-y-6">
      {/* Aggregate */}
      <div className="rounded-xl border border-border bg-card p-5">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground text-sm"><Loader2 className="size-4 animate-spin" />Carregando…</div>
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
                <RatingBar key={n} label={String(n)} n={(stats as any)?.[`r${n}`] ?? 0} total={stats?.total ?? 0} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* List */}
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

// ── shared form helpers ───────────────────────────────────────────────────────

const inputCls = "w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary";

function Field({ label, children, editing }: { label: string; children: React.ReactNode; editing: boolean }) {
  return (
    <div className={cn("space-y-1", editing ? "" : "")}>
      <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{label}</p>
      <div className="text-sm text-foreground">{children}</div>
    </div>
  );
}

// ── Tabs definition ───────────────────────────────────────────────────────────

type Tab = "alunos" | "urgente" | "leaks" | "perfil" | "avaliacoes";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "alunos",    label: "Alunos",            icon: Users },
  { id: "urgente",   label: "Atenção Urgente",    icon: AlertTriangle },
  { id: "leaks",     label: "Leaks Sistêmicos",   icon: LayoutDashboard },
  { id: "perfil",    label: "Perfil Público",      icon: UserCircle },
  { id: "avaliacoes", label: "Avaliações",         icon: Star },
];

export default function CoachDashboard() {
  const [tab, setTab] = useState<Tab>("alunos");

  const { data: impact, isLoading: loadingImpact } = useQuery({
    queryKey: ["coach-impact"],
    queryFn: () => coachDashboard.impact(30),
  });

  const summary = impact?.summary;

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-5xl px-6 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard do Professor</h1>
          <p className="text-sm text-muted-foreground mt-1">Acompanhe a evolução dos seus alunos</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Alunos"        value={loadingImpact ? "…" : (summary?.total_students ?? 0)}  icon={Users} />
          <StatCard label="Ativos (30d)"  value={loadingImpact ? "…" : (summary?.active_students ?? 0)} icon={Activity} />
          <StatCard
            label="Melhoria Média"
            value={loadingImpact ? "…" : summary?.avg_improvement_pct != null ? `${summary.avg_improvement_pct.toFixed(1)}%` : "—"}
            icon={TrendingUp}
          />
          <StatCard
            label="Melhor Aluno"
            value={loadingImpact ? "…" : (summary?.best_student ?? "—")}
            icon={Award}
          />
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border gap-0">
          {TABS.map((t) => (
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

        {tab === "alunos"     && <AlunosTab />}
        {tab === "urgente"    && <UrgentTab />}
        {tab === "leaks"      && <LeaksTab />}
        {tab === "perfil"     && <ProfileTab />}
        {tab === "avaliacoes" && <AvaliacoesTab />}
      </main>
    </div>
  );
}
