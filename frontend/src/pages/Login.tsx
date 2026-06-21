import { useEffect, useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { Loader2, GraduationCap, User } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";

const Login = () => {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [role, setRole] = useState<"player" | "coach">("player");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("auth");
  const [searchParams] = useSearchParams();
  const ref = searchParams.get("ref");
  const [linkedCoach, setLinkedCoach] = useState<string | null>(null);

  useEffect(() => {
    // Convite de coach na URL: pré-seleciona o cadastro
    if (ref) setTab("register");
  }, [ref]);

  useEffect(() => {
    if (linkedCoach) return; // não redireciona antes de mostrar a confirmação de vínculo
    if (user) navigate(user.role === "coach" ? "/coach-dashboard" : "/dashboard", { replace: true });
  }, [user, navigate, linkedCoach]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        const coach = await register(username, email, password, role, ref);
        if (coach) {
          setLinkedCoach(coach);
          setLoading(false);
          setTimeout(() => navigate(role === "coach" ? "/coach-dashboard" : "/dashboard", { replace: true }), 2500);
          return;
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("Candidatura em análise")) {
        setError("Candidatura em análise, você receberá um email quando for aprovado.");
      } else if (err instanceof TypeError) {
        setError(t("errors.invalidCredentials"));
      } else {
        setError(msg || t("errors.invalidCredentials"));
      }
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

  return (
    <div className="min-h-dvh bg-background hud-scanline flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <img src={logoHorizontal} alt="GrindLab" className="h-14 w-auto" />
          </div>
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest-2">
            Tactical Tournament Intelligence
          </p>
        </div>

        <div className="rounded-xl border border-border bg-hud-surface p-6 shadow-elevated">
          <div className="flex mb-6 border-b border-border">
            {(["login", "register"] as const).map((tabKey) => (
              <button
                key={tabKey}
                type="button"
                onClick={() => { setTab(tabKey); setError(""); }}
                className={`flex-1 pb-3 font-mono text-xs font-bold uppercase tracking-widest-2 transition-colors ${
                  tab === tabKey
                    ? "text-primary border-b-2 border-primary -mb-px"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tabKey === "login" ? t("login.submit") : t("register.submit")}
              </button>
            ))}
          </div>

          {linkedCoach && (
            <p className="mb-4 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
              {t("referral.linkedTo", { coach: linkedCoach })}
            </p>
          )}

          <form onSubmit={submit} className="space-y-4">
            {tab === "register" && ref && !linkedCoach && (
              <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
                {t("referral.detected")}
              </p>
            )}
            {tab === "register" && (
              <>
                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                    {t("register.username")}
                  </label>
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="phpro"
                    required
                    autoComplete="username"
                    className={inputClass}
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                    Tipo de conta
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setRole("player")}
                      className={`flex items-center justify-center gap-2 h-10 rounded-md border text-xs font-mono font-bold uppercase tracking-widest-2 transition-all ${
                        role === "player"
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                      }`}
                    >
                      <User className="size-3.5" /> Jogador
                    </button>
                    <Link
                      to="/coach-apply"
                      className="flex items-center justify-center gap-2 h-10 rounded-md border border-border bg-background text-xs font-mono font-bold uppercase tracking-widest-2 text-muted-foreground hover:border-primary/50 hover:text-foreground transition-all"
                    >
                      <GraduationCap className="size-3.5" /> Coach →
                    </Link>
                  </div>
                  <p className="font-mono text-[9px] text-muted-foreground">
                    Coaches precisam enviar candidatura para aprovação.
                  </p>
                </div>
              </>
            )}

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                {t("login.email")}
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="coach@pokergrindlab.com"
                required
                autoComplete="email"
                className={inputClass}
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                {t("login.password")}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                autoComplete={tab === "login" ? "current-password" : "new-password"}
                className={inputClass}
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
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
              {loading
                ? (tab === "login" ? t("login.submitting") : t("register.submitting"))
                : (tab === "login" ? t("login.submit") : t("register.submit"))}
            </button>
          </form>
        </div>

        <p className="text-center font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
          Análise tática • GrindLab AI Engine
        </p>
      </div>
    </div>
  );
};

export default Login;
