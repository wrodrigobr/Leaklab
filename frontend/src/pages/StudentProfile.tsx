import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound, Mail, UserX, Loader2, Check, AlertTriangle, GraduationCap } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { useAuth } from "@/lib/auth";
import { auth as authApi, student as studentApi } from "@/lib/api";
import { toast } from "sonner";

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

  const handleUnlink = async () => {
    if (!confirmUnlink) { setConfirmUnlink(true); return; }
    setUnlinkLoading(true);
    try {
      await studentApi.unlinkCoach();
      await refreshUser();
      setConfirmUnlink(false);
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

              {!confirmUnlink ? (
                <button
                  onClick={handleUnlink}
                  className="inline-flex items-center gap-2 rounded-md border border-destructive/40 px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <UserX className="size-3.5" /> Remover vínculo
                </button>
              ) : (
                <div className="space-y-2">
                  <p className="font-mono text-[11px] text-destructive flex items-center gap-1.5">
                    <AlertTriangle className="size-3.5" />
                    Confirma remoção do vínculo com <strong>{user.coach_username}</strong>?
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={handleUnlink}
                      disabled={unlinkLoading}
                      className="inline-flex items-center gap-2 rounded-md bg-destructive px-4 py-2 font-mono text-[11px] font-bold uppercase text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
                    >
                      {unlinkLoading ? <Loader2 className="size-3.5 animate-spin" /> : <UserX className="size-3.5" />}
                      Confirmar remoção
                    </button>
                    <button
                      onClick={() => setConfirmUnlink(false)}
                      className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
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
