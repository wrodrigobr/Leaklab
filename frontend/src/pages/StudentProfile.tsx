import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound, Mail, UserX, Loader2, Check, AlertTriangle, GraduationCap, Star, Trash2 } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { useAuth } from "@/lib/auth";
import { auth as authApi, student as studentApi, coachDashboard, CoachReview } from "@/lib/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

function StarPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)}>
          <Star className={`size-5 transition-colors ${(hover || value) >= n ? "fill-amber-400 text-amber-400" : "text-muted-foreground"}`} />
        </button>
      ))}
    </div>
  );
}

function CoachReviewWidget({ coachId }: { coachId: number }) {
  const qc = useQueryClient();
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);

  const { data: existing, isLoading } = useQuery({
    queryKey: ["my-review", coachId],
    queryFn: () => coachDashboard.getMyReview(coachId),
  });

  const save = useMutation({
    mutationFn: () => coachDashboard.submitReview({ rating, review_text: text || undefined, coach_id: coachId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-review", coachId] });
      setEditing(false);
      toast.success("Avaliação salva!");
    },
  });

  const remove = useMutation({
    mutationFn: () => coachDashboard.deleteMyReview(coachId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-review", coachId] });
      setRating(0); setText(""); setEditing(false);
      toast.success("Avaliação removida.");
    },
  });

  if (isLoading) return null;

  const startEdit = (r?: CoachReview | null) => {
    setRating(r?.rating ?? 0);
    setText(r?.review_text ?? "");
    setEditing(true);
  };

  if (existing && !editing) {
    return (
      <div className="rounded-lg border border-border bg-background p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Minha avaliação</p>
            <div className="flex gap-0.5">
              {[1,2,3,4,5].map(n => <Star key={n} className={`size-3.5 ${existing.rating >= n ? "fill-amber-400 text-amber-400" : "text-border"}`} />)}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => startEdit(existing)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground">Editar</button>
            <button onClick={() => remove.mutate()} className="font-mono text-[10px] text-destructive hover:text-destructive/80">
              <Trash2 className="size-3" />
            </button>
          </div>
        </div>
        {existing.review_text && <p className="text-xs text-muted-foreground">{existing.review_text}</p>}
      </div>
    );
  }

  if (editing || !existing) {
    return (
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-3">
        <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {existing ? "Editar avaliação" : "Avaliar meu coach"}
        </p>
        <StarPicker value={rating} onChange={setRating} />
        <textarea
          rows={2}
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Comentário opcional…"
          className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
        <div className="flex gap-2">
          <button
            onClick={() => save.mutate()}
            disabled={rating === 0 || save.isPending}
            className="flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 font-mono text-[11px] font-bold text-primary-foreground disabled:opacity-50"
          >
            {save.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />} Enviar
          </button>
          {(existing || editing) && (
            <button onClick={() => setEditing(false)} className="rounded border border-border px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
              Cancelar
            </button>
          )}
        </div>
        {!existing && !editing && (
          <button onClick={() => startEdit()} className="font-mono text-[10px] text-primary hover:underline">+ Avaliar coach</button>
        )}
      </div>
    );
  }

  return (
    <button onClick={() => startEdit()} className="font-mono text-[10px] text-primary hover:underline">
      + Avaliar meu coach
    </button>
  );
}

function Section({ icon: Icon, title, children }: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-6 space-y-4">
      <div className="flex items-center gap-2.5">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="size-4" />
        </span>
        <h2 className="text-sm font-bold uppercase tracking-widest-2 text-foreground">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

export default function StudentProfile() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();

  // ── Alterar e-mail ────────────────────────────────────────────────────────
  const [newEmail, setNewEmail]         = useState(user?.email ?? "");
  const [emailPw, setEmailPw]           = useState("");
  const [emailLoading, setEmailLoading] = useState(false);

  const handleUpdateEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.includes("@")) { toast.error("E-mail inválido"); return; }
    setEmailLoading(true);
    try {
      await authApi.updateEmail(newEmail, emailPw);
      await refreshUser();
      setEmailPw("");
      toast.success("E-mail atualizado com sucesso.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao atualizar e-mail");
    } finally {
      setEmailLoading(false);
    }
  };

  // ── Trocar senha ──────────────────────────────────────────────────────────
  const [currentPw,  setCurrentPw]  = useState("");
  const [newPw,      setNewPw]      = useState("");
  const [confirmPw,  setConfirmPw]  = useState("");
  const [pwLoading,  setPwLoading]  = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw.length < 8) { toast.error("Nova senha deve ter pelo menos 8 caracteres"); return; }
    if (newPw !== confirmPw) { toast.error("As senhas não coincidem"); return; }
    setPwLoading(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      toast.success("Senha alterada com sucesso.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao trocar senha");
    } finally {
      setPwLoading(false);
    }
  };

  // ── Desvincular coach ─────────────────────────────────────────────────────
  const [unlinkLoading, setUnlinkLoading] = useState(false);
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const [unlinkPw, setUnlinkPw] = useState("");

  const handleUnlink = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!confirmUnlink) { setConfirmUnlink(true); return; }
    if (!unlinkPw) { toast.error("Digite sua senha para confirmar"); return; }
    setUnlinkLoading(true);
    try {
      await studentApi.unlinkCoach(unlinkPw);
      await refreshUser();
      setConfirmUnlink(false);
      setUnlinkPw("");
      toast.success("Vínculo com coach removido.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao remover vínculo");
    } finally {
      setUnlinkLoading(false);
    }
  };

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-2xl px-6 py-10 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Meu Perfil</h1>
          <p className="font-mono text-[11px] text-muted-foreground mt-1">{user?.username}</p>
        </div>

        {/* Alterar e-mail */}
        <Section icon={Mail} title="Alterar E-mail">
          <form onSubmit={handleUpdateEmail} className="space-y-3">
            <Field label="Novo e-mail">
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className={inputCls}
                required
              />
            </Field>
            <Field label="Confirmar com sua senha atual">
              <input
                type="password"
                value={emailPw}
                onChange={(e) => setEmailPw(e.target.value)}
                placeholder="Sua senha atual"
                className={inputCls}
                required
              />
            </Field>
            <button
              type="submit"
              disabled={emailLoading}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {emailLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              Salvar e-mail
            </button>
          </form>
        </Section>

        {/* Trocar senha */}
        <Section icon={KeyRound} title="Trocar Senha">
          <form onSubmit={handleChangePassword} className="space-y-3">
            <Field label="Senha atual">
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                placeholder="Senha atual"
                className={inputCls}
                required
              />
            </Field>
            <Field label="Nova senha (mínimo 8 caracteres)">
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                placeholder="Nova senha"
                className={inputCls}
                required
                minLength={8}
              />
            </Field>
            <Field label="Confirmar nova senha">
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                placeholder="Repita a nova senha"
                className={inputCls}
                required
              />
            </Field>
            {newPw && confirmPw && newPw !== confirmPw && (
              <p className="font-mono text-[10px] text-destructive flex items-center gap-1">
                <AlertTriangle className="size-3" /> As senhas não coincidem
              </p>
            )}
            <button
              type="submit"
              disabled={pwLoading}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {pwLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              Trocar senha
            </button>
          </form>
        </Section>

        {/* Vínculo com coach */}
        <Section icon={GraduationCap} title="Meu Coach">
          {user?.coach_id ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
                <GraduationCap className="size-4 text-primary shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-foreground">{user.coach_username}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">Coach vinculado</p>
                </div>
              </div>
              <CoachReviewWidget coachId={user.coach_id} />

              {!confirmUnlink ? (
                <button
                  onClick={handleUnlink}
                  className="inline-flex items-center gap-2 rounded-md border border-destructive/40 px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <UserX className="size-3.5" /> Remover vínculo
                </button>
              ) : (
                <form onSubmit={handleUnlink} className="space-y-3">
                  <p className="font-mono text-[11px] text-destructive flex items-center gap-1.5">
                    <AlertTriangle className="size-3.5" />
                    Confirma remoção do vínculo com <strong>{user.coach_username}</strong>?
                  </p>
                  <Field label="Digite sua senha para confirmar">
                    <input
                      type="password"
                      value={unlinkPw}
                      onChange={(e) => setUnlinkPw(e.target.value)}
                      placeholder="Sua senha atual"
                      className={inputCls}
                      autoFocus
                      required
                    />
                  </Field>
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={unlinkLoading}
                      className="inline-flex items-center gap-2 rounded-md bg-destructive px-4 py-2 font-mono text-[11px] font-bold uppercase text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
                    >
                      {unlinkLoading ? <Loader2 className="size-3.5 animate-spin" /> : <UserX className="size-3.5" />}
                      Confirmar remoção
                    </button>
                    <button
                      type="button"
                      onClick={() => { setConfirmUnlink(false); setUnlinkPw(""); }}
                      className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Cancelar
                    </button>
                  </div>
                </form>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Nenhum coach vinculado.</p>
              <button
                onClick={() => navigate("/")}
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              >
                <GraduationCap className="size-3.5" /> Vincular um coach
              </button>
            </div>
          )}
        </Section>
      </main>
    </div>
  );
}
