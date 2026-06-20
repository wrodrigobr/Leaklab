import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, UserCircle, X } from "lucide-react";
import { profile, DemographicProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

const GAME_TYPES = [
  { value: "mtt",   label: "MTT" },
  { value: "cash",  label: "Cash Game" },
  { value: "spin",  label: "Spin & Go" },
  { value: "mixed", label: "Misto" },
];
const BUYIN_RANGES = [
  { value: "micro", label: "Micro (< $5)" },
  { value: "low",   label: "Low ($5–$30)" },
  { value: "mid",   label: "Mid ($30–$200)" },
  { value: "high",  label: "High (> $200)" },
];

const CORE_FIELDS: (keyof DemographicProfile)[] = [
  "birth_year", "country", "poker_experience_years", "main_game_type", "usual_buyin_range",
];

function filledCount(d: DemographicProfile): number {
  return CORE_FIELDS.filter((k) => d[k] != null && d[k] !== "").length;
}

export function ProfileCompletionCard() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const dismissed = typeof window !== "undefined" && localStorage.getItem("profile_card_dismissed") === "1";
  const [hidden, setHidden] = useState(dismissed);
  const [open, setOpen]     = useState(false);

  const { data: demo, isLoading } = useQuery({
    queryKey: ["player-profile"],
    queryFn:  profile.get,
    enabled:  !hidden && !user?.profile_completed_at,
  });

  const mutation = useMutation({
    mutationFn: profile.update,
    onSuccess: (updated) => {
      qc.setQueryData(["player-profile"], updated);
      if (updated.profile_completed_at) {
        qc.invalidateQueries({ queryKey: ["me"] });
        toast.success("Perfil completo! Obrigado.");
        setOpen(false);
      } else {
        toast.success("Dados salvos.");
      }
    },
    onError: () => toast.error("Erro ao salvar perfil."),
  });

  const [form, setForm] = useState<Partial<DemographicProfile>>({});
  const set = (k: keyof DemographicProfile) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value === "" ? null : e.target.value }));

  if (hidden || user?.profile_completed_at || isLoading) return null;
  if (!demo) return null;

  const filled = filledCount({ ...demo, ...form });
  const pct    = Math.round((filled / CORE_FIELDS.length) * 100);

  const dismiss = () => {
    localStorage.setItem("profile_card_dismissed", "1");
    setHidden(true);
  };

  const save = () => {
    const payload: Partial<DemographicProfile> = {};
    for (const k of CORE_FIELDS) {
      const val = form[k] ?? demo[k];
      if (val != null) (payload as Record<string, unknown>)[k as string] = val;
    }
    // include optional fields
    if (form.state_province !== undefined) payload.state_province = form.state_province;
    if (form.city           !== undefined) payload.city           = form.city;
    mutation.mutate(payload);
  };

  const inputClass = "h-9 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none";
  const selectClass = inputClass;
  const labelClass  = "font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground";

  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 shadow-sm">
      <div className="flex items-center justify-between px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 text-sm font-semibold text-foreground"
        >
          <UserCircle className="size-4 text-primary" />
          Complete seu perfil
          <span className="font-mono text-xs text-muted-foreground">({pct}%)</span>
          {open ? <ChevronUp className="size-3.5 text-muted-foreground" /> : <ChevronDown className="size-3.5 text-muted-foreground" />}
        </button>
        <div className="flex items-center gap-3">
          <div className="w-24 h-1.5 rounded-full bg-border overflow-hidden">
            <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
          </div>
          <button type="button" onClick={dismiss} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-border/50 pt-3">
          <p className="font-mono text-[10px] text-muted-foreground">
            Dados usados apenas para benchmarks agregados e anonimizados, nunca compartilhados individualmente.
          </p>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <label className={labelClass}>Ano de nascimento</label>
              <input
                type="number" min="1940" max="2010"
                defaultValue={demo.birth_year ?? ""}
                onChange={set("birth_year")}
                placeholder="1990"
                className={inputClass}
              />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>País</label>
              <input
                defaultValue={demo.country ?? ""}
                onChange={set("country")}
                placeholder="Brasil"
                className={inputClass}
              />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Estado</label>
              <input
                defaultValue={demo.state_province ?? ""}
                onChange={set("state_province")}
                placeholder="SP"
                className={inputClass}
              />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Cidade</label>
              <input
                defaultValue={demo.city ?? ""}
                onChange={set("city")}
                placeholder="São Paulo"
                className={inputClass}
              />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Anos no poker</label>
              <input
                type="number" min="0" max="30"
                defaultValue={demo.poker_experience_years ?? ""}
                onChange={set("poker_experience_years")}
                placeholder="3"
                className={inputClass}
              />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>Jogo principal</label>
              <select
                defaultValue={demo.main_game_type ?? ""}
                onChange={set("main_game_type")}
                className={selectClass}
              >
                <option value="">Selecione</option>
                {GAME_TYPES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </div>
            <div className="space-y-1 sm:col-span-1">
              <label className={labelClass}>Faixa de buy-in</label>
              <select
                defaultValue={demo.usual_buyin_range ?? ""}
                onChange={set("usual_buyin_range")}
                className={selectClass}
              >
                <option value="">Selecione</option>
                {BUYIN_RANGES.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
              </select>
            </div>
          </div>

          <div className="flex gap-2 justify-end">
            <button type="button" onClick={dismiss} className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5">
              Não mostrar mais
            </button>
            <button
              type="button"
              onClick={save}
              disabled={mutation.isPending}
              className="h-8 px-4 rounded-md bg-primary font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary-foreground disabled:opacity-50"
            >
              {mutation.isPending ? "Salvando…" : "Salvar"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
