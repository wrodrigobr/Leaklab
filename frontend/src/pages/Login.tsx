import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Loader2, GraduationCap, User } from "lucide-react";
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

  useEffect(() => {
    if (user) navigate(user.role === "coach" ? "/coach-dashboard" : "/dashboard", { replace: true });
  }, [user, navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        await register(username, email, password, role);
      }
      // redirect handled by useEffect above via user state update
    } catch (err: unknown) {
      if (err instanceof TypeError) {
        setError("Não foi possível conectar ao servidor. Tente novamente.");
      } else {
        setError(err instanceof Error ? err.message : "Erro desconhecido");
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
            <span className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow">
              <BarChart3 className="size-6" aria-hidden />
            </span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            PokerLeaks<span className="text-primary italic font-light">.os</span>
          </h1>
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest-2">
            Tactical Tournament Intelligence
          </p>
        </div>

        <div className="rounded-xl border border-border bg-hud-surface p-6 shadow-elevated">
          <div className="flex mb-6 border-b border-border">
            {(["login", "register"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => {
                  setTab(t);
                  setError("");
                }}
                className={`flex-1 pb-3 font-mono text-xs font-bold uppercase tracking-widest-2 transition-colors ${
                  tab === t
                    ? "text-primary border-b-2 border-primary -mb-px"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t === "login" ? "Entrar" : "Criar conta"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {tab === "register" && (
              <>
                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                    Nickname
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
                    {(["player", "coach"] as const).map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => setRole(r)}
                        className={`flex items-center justify-center gap-2 h-10 rounded-md border text-xs font-mono font-bold uppercase tracking-widest-2 transition-all ${
                          role === r
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                        }`}
                      >
                        {r === "player" ? (
                          <User className="size-3.5" />
                        ) : (
                          <GraduationCap className="size-3.5" />
                        )}
                        {r === "player" ? "Jogador" : "Professor"}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                E-mail
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="coach@pokerleaks.com"
                required
                autoComplete="email"
                className={inputClass}
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                Senha
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
              {tab === "login" ? "Entrar" : "Criar conta"}
            </button>
          </form>
        </div>

        <p className="text-center font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
          Análise tática • LeakLabs AI Engine
        </p>
      </div>
    </div>
  );
};

export default Login;
