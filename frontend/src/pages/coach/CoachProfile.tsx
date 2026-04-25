import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { HudHeader } from "@/components/hud/HudHeader";
import { coachDashboard, CoachProfile as CoachProfileType } from "@/lib/api";

const inputClass =
  "h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

const textareaClass =
  "w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none";

export default function CoachProfile() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["coach-profile"],
    queryFn: coachDashboard.getProfile,
  });

  const [form, setForm] = useState<Partial<CoachProfileType>>({});

  const mutation = useMutation({
    mutationFn: (data: Partial<CoachProfileType>) => coachDashboard.saveProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["coach-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const value = (key: keyof CoachProfileType) =>
    (form[key] as string | undefined) ?? (profile?.[key] as string | undefined) ?? "";

  const set = (key: keyof CoachProfileType) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-2xl px-6 py-8 space-y-8">
        <div className="flex items-center gap-3">
          <Link
            to="/coach-dashboard"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            Dashboard
          </Link>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-foreground">Perfil do Professor</h1>
          <p className="text-sm text-muted-foreground mt-1">Informações exibidas para seus alunos</p>
        </div>

        {isLoading && <p className="text-sm text-muted-foreground animate-pulse">Carregando…</p>}

        {!isLoading && (
          <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-hud-surface p-6 space-y-5">
            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Nome de exibição
              </label>
              <input value={value("display_name")} onChange={set("display_name")} placeholder="Prof. Rodrigo" className={inputClass} />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Bio
              </label>
              <textarea
                value={value("bio")}
                onChange={set("bio")}
                placeholder="Especialista em MTT, ex-jogador profissional…"
                rows={3}
                className={textareaClass}
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                E-mail de contato
              </label>
              <input value={value("contact_email") as string} onChange={set("contact_email")} type="email" placeholder="coach@exemplo.com" className={inputClass} />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Link (Discord / Telegram / WhatsApp)
              </label>
              <input value={value("contact_link") as string} onChange={set("contact_link")} placeholder="https://t.me/seuusuario" className={inputClass} />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Especialidades (separadas por vírgula)
              </label>
              <input
                value={
                  form.specialties != null
                    ? (form.specialties as string[]).join(", ")
                    : (profile?.specialties ?? []).join(", ")
                }
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    specialties: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                  }))
                }
                placeholder="MTT, ICM, Bubble Play"
                className={inputClass}
              />
            </div>

            <button
              type="submit"
              disabled={mutation.isPending}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : saved ? (
                "Salvo!"
              ) : (
                <>
                  <Save className="size-4" />
                  Salvar perfil
                </>
              )}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
