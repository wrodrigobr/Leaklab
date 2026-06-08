import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GraduationCap, Loader2, CheckCircle2, ArrowLeft } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import { coachApplyApi } from "@/lib/api";

const inputClass =
  "h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

const textareaClass =
  "w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none";

export default function CoachApply() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [done, setDone]       = useState(false);

  const [form, setForm] = useState({
    username:         "",
    email:            "",
    password:         "",
    instagram_handle: "",
    bio:              "",
    specialties:      "",
    experience_years: "",
    biggest_results:  "",
  });

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await coachApplyApi.apply({
        username:         form.username,
        email:            form.email,
        password:         form.password,
        instagram_handle: form.instagram_handle || undefined,
        bio:              form.bio,
        specialties:      form.specialties || undefined,
        experience_years: form.experience_years ? Number(form.experience_years) : undefined,
        biggest_results:  form.biggest_results || undefined,
      });
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao enviar candidatura");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-dvh bg-background hud-scanline flex items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-6 text-center">
          <CheckCircle2 className="size-16 text-primary mx-auto" />
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-foreground">Candidatura enviada!</h1>
            <p className="text-sm text-muted-foreground">
              Recebemos sua candidatura. Nossa equipe vai analisar e você receberá um email com a decisão.
            </p>
          </div>
          <button
            onClick={() => navigate("/login")}
            className="w-full h-10 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground"
          >
            Voltar ao Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-background hud-scanline flex items-start justify-center p-4 py-12">
      <div className="w-full max-w-lg space-y-8">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <img src={logoHorizontal} alt="GrindLab" className="h-10 w-auto" />
          </div>
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest-2">
            Candidatura de Coach
          </p>
        </div>

        <div className="rounded-xl border border-border bg-hud-surface p-6 shadow-elevated space-y-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <GraduationCap className="size-4 text-primary" />
            <span>Preencha o formulário — nossa equipe analisará sua candidatura em até 3 dias úteis.</span>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Usuário *
                </label>
                <input value={form.username} onChange={set("username")} placeholder="seunome" required className={inputClass} />
              </div>
              <div className="space-y-1.5">
                <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  @Instagram
                </label>
                <input value={form.instagram_handle} onChange={set("instagram_handle")} placeholder="@seu_perfil" className={inputClass} />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Email *
              </label>
              <input type="email" value={form.email} onChange={set("email")} placeholder="coach@email.com" required className={inputClass} />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Senha * (mín. 8 caracteres)
              </label>
              <input type="password" value={form.password} onChange={set("password")} placeholder="••••••••" required minLength={8} className={inputClass} />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Bio / Apresentação * <span className="normal-case font-normal">(mín. 30 caracteres)</span>
              </label>
              <textarea
                value={form.bio} onChange={set("bio")} required rows={3}
                placeholder="Descreva sua experiência como jogador e coach de poker..."
                className={textareaClass}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Especialidades
                </label>
                <input value={form.specialties} onChange={set("specialties")} placeholder="MTT, ICM, Spin&Go..." className={inputClass} />
              </div>
              <div className="space-y-1.5">
                <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Anos de experiência
                </label>
                <input type="number" min="0" max="30" value={form.experience_years} onChange={set("experience_years")} placeholder="5" className={inputClass} />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Maiores resultados
              </label>
              <textarea
                value={form.biggest_results} onChange={set("biggest_results")} rows={2}
                placeholder="Ex: Final table WSOP Online 2023, ROI +140% em 500 MTTs..."
                className={textareaClass}
              />
            </div>

            {error && (
              <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground disabled:opacity-50"
            >
              {loading && <Loader2 className="size-4 animate-spin" />}
              {loading ? "Enviando…" : "Enviar candidatura"}
            </button>
          </form>
        </div>

        <div className="text-center">
          <Link to="/login" className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="size-3" /> Voltar ao login
          </Link>
        </div>
      </div>
    </div>
  );
}
