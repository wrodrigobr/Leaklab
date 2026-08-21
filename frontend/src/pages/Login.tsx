import { useEffect, useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { Loader2, GraduationCap, User, MailCheck, ArrowLeft } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { auth as authApi } from "@/lib/api";
import { destinoSeguro } from "@/lib/destinoAposLogin";

const Login = () => {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [role, setRole] = useState<"player" | "coach">("player");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register, verifyEmail, user } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("auth");
  const [searchParams, setSearchParams] = useSearchParams();
  const ref = searchParams.get("ref");
  const [linkedCoach, setLinkedCoach] = useState<string | null>(null);

  // Verificação de email (2FA simples): quando setado, mostra a tela do código.
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [pendingCoach, setPendingCoach] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [resent, setResent] = useState(false);

  /**
   * A tela do código vivia SÓ na memória: sair dela (trocar de app no celular basta) perdia o
   * estado e não havia como voltar. Aconteceu com um usuário real, que ficou com o código na mão
   * e sem onde digitar.
   *
   * Agora o e-mail pendente vive na URL (`?verificar=`), então recarregar e o voltar do navegador
   * devolvem a tela. E o link do e-mail traz `?codigo=`, que preenche e envia sozinho.
   */
  useEffect(() => {
    const alvoEmail = searchParams.get("verificar");
    if (!alvoEmail || pendingEmail) return;
    setPendingEmail(alvoEmail);
    setEmail(alvoEmail);
    const codigo = searchParams.get("codigo");
    if (codigo) setCode(codigo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Envio automático quando o código veio pelo link. Roda uma vez: `autoEnviado` impede que um
  // código recusado entre em laço de reenvio.
  const [autoEnviado, setAutoEnviado] = useState(false);
  useEffect(() => {
    if (autoEnviado || !pendingEmail || !code || !searchParams.get("codigo")) return;
    setAutoEnviado(true);
    // Tira o código da URL ANTES de enviar: ele não pode ficar no histórico do navegador nem
    // vazar por Referer. O `verificar` fica, porque é ele que devolve a tela num recarregamento.
    setSearchParams({ verificar: pendingEmail }, { replace: true });
    void submitCode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingEmail, code, autoEnviado]);

  // Esqueci a senha: 'email' (pede o email) | 'reset' (código + nova senha) | null.
  const [forgotMode, setForgotMode] = useState<null | "email" | "reset">(null);
  const [resetCode, setResetCode] = useState("");
  const [newPw, setNewPw] = useState("");
  const [resetDone, setResetDone] = useState(false);

  // Quem chega de /fundadores já vem decidido a criar conta: abrir no "entrar" faria a
  // pessoa procurar a aba de cadastro depois de já ter clicado num botão de candidatura.
  const candidatoFundador = searchParams.get("fundador") === "1";

  useEffect(() => {
    if (ref || candidatoFundador) setTab("register");
  }, [ref, candidatoFundador]);

  // Para onde ir depois de autenticar. O `?next=` chega dos guardas de rota e é o que faz o
  // clique de e-mail terminar NO TREINO prescrito em vez de no dashboard genérico. Validado
  // contra open redirect em `destinoSeguro` — `?next=` cru é phishing usando o nosso domínio.
  const destino = destinoSeguro(searchParams.get("next"));
  const paraOndeIr = (papel: string | null | undefined) =>
    destino ?? (papel === "coach" ? "/coach-dashboard" : "/dashboard");

  useEffect(() => {
    if (linkedCoach) return; // não redireciona antes de mostrar a confirmação de vínculo
    if (user) navigate(paraOndeIr(user.role), { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, navigate, linkedCoach, destino]);

  const routeAfterAuth = (coach: string | null) => {
    if (coach) {
      setLinkedCoach(coach);
      setTimeout(() => navigate(paraOndeIr(role), { replace: true }), 2500);
    }
    // sem coach: o useEffect(user) redireciona sozinho
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        await login(email, password);
      } else {
        if (username.includes("@")) {
          setError(t("errors.usernameEmail"));
          setLoading(false);
          return;
        }
        const res = await register(username, email, password, role, ref, candidatoFundador);
        if (res.pending) {
          setPendingCoach(res.linkedCoach ?? null);
          setPendingEmail(res.email ?? email);
          setSearchParams({ verificar: res.email ?? email }, { replace: true });
          setLoading(false);
          return;
        }
        routeAfterAuth(res.linkedCoach ?? null);
        if (res.linkedCoach) { setLoading(false); return; }
      }
    } catch (err: unknown) {
      const e2 = err as { code?: string; message?: string };
      if (e2.code === "email_unverified") {
        // conta existe mas não confirmada: cai na tela do código (backend já reenviou)
        setPendingEmail(email);
        setSearchParams({ verificar: email }, { replace: true });
        setLoading(false);
        return;
      }
      if (e2.code === "username_is_email") {
        setError(t("errors.usernameEmail"));
      } else if (e2.code === "coach_pending" || (e2.message || "").includes("Candidatura em análise")) {
        setError(t("errors.coachPending"));
      } else if (err instanceof TypeError) {
        setError(t("errors.invalidCredentials"));
      } else {
        setError(e2.message || t("errors.invalidCredentials"));
      }
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setError("");
    setLoading(true);
    try {
      const coach = await verifyEmail(pendingEmail!, code.trim());
      setPendingEmail(null);
      setSearchParams({}, { replace: true });
      routeAfterAuth(coach ?? pendingCoach ?? null);
    } catch (err: unknown) {
      const e2 = err as { code?: string; message?: string };
      const map: Record<string, string> = {
        invalid: t("verify.errInvalid"),
        expired: t("verify.errExpired"),
        too_many: t("verify.errTooMany"),
        already: t("verify.errAlready"),
      };
      setError((e2.code && map[e2.code]) || e2.message || t("verify.errInvalid"));
    } finally {
      setLoading(false);
    }
  };

  const submitForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
    } catch {
      /* silencioso: a resposta é sempre genérica, não vaza se o email existe */
    } finally {
      setLoading(false);
      setForgotMode("reset"); // sempre avança pra tela do código
    }
  };

  const submitReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.resetPassword(email, resetCode.trim(), newPw);
      setForgotMode(null);
      setResetDone(true);
      setPassword("");
      setResetCode("");
      setNewPw("");
    } catch (err: unknown) {
      const e2 = err as { code?: string; message?: string };
      const map: Record<string, string> = {
        invalid: t("forgot.errInvalid"),
        expired: t("forgot.errExpired"),
        too_many: t("forgot.errTooMany"),
        weak: t("forgot.errWeak"),
      };
      setError((e2.code && map[e2.code]) || e2.message || t("forgot.errInvalid"));
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    if (!pendingEmail) return;
    setError("");
    setResent(false);
    try {
      await authApi.resendCode(pendingEmail);
      setResent(true);
    } catch {
      /* silencioso: o endpoint nunca vaza existência de conta */
      setResent(true);
    }
  };

  /**
   * Saída VISÍVEL para quem se cadastrou e perdeu a tela do código.
   *
   * O caminho já existia — tentar entrar com a conta não confirmada devolve `email_unverified` e
   * reenvia o código — mas nada na tela dizia isso, então ninguém descobria sozinho. Era uma
   * recuperação que só acontecia por acidente.
   */
  const recuperarConfirmacao = async () => {
    const alvo = email.trim();
    if (!alvo) { setError(t("verify.recoverNoEmail")); return; }
    setError("");
    setPendingEmail(alvo);
    setSearchParams({ verificar: alvo }, { replace: true });
    try {
      await authApi.resendCode(alvo);
    } catch {
      /* silencioso: o endpoint nunca vaza existência de conta */
    }
    setResent(true);
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

        {pendingEmail ? (
          /* ── Tela de verificação por código ─────────────────────────────── */
          <div className="rounded-xl border border-border bg-hud-surface p-6 shadow-elevated">
            <div className="mb-4 flex flex-col items-center text-center">
              <span className="mb-3 inline-flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary">
                <MailCheck className="size-5" />
              </span>
              <h2 className="font-heading text-lg font-bold text-foreground">{t("verify.title")}</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("verify.sentTo")} <span className="text-foreground">{pendingEmail}</span>
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">{t("verify.validFor")}</p>
            </div>

            {/*
              O spam não é hipótese: em 20/08 as 7 contas travadas na confirmação tinham ZERO
              tentativas de digitar código — ninguém tinha recebido o e-mail. Enquanto o DNS do
              domínio não autorizar o remetente (SPF/DKIM), este aviso é o que dá saída ao
              jogador. Fica ACIMA do campo porque no rodapé ele só é lido por quem já desistiu.
            */}
            <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-200">
              <p className="font-bold">{t("verify.spamHint")}</p>
              <p className="mt-0.5 text-amber-200/80">{t("verify.spamHintAction")}</p>
            </div>

            <form onSubmit={submitCode} className="space-y-4">
              <div className="space-y-1.5">
                <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  {t("verify.codeLabel")}
                </label>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  required
                  autoFocus
                  className={`${inputClass} text-center font-mono text-lg tracking-[0.4em]`}
                />
              </div>

              {error && (
                <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {error}
                </p>
              )}
              {resent && !error && (
                <p className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
                  {t("verify.resent")}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || code.length < 6}
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
                {loading ? t("verify.submitting") : t("verify.submit")}
              </button>
            </form>

            <div className="mt-4 flex items-center justify-between text-[11px]">
              <button
                type="button"
                onClick={() => { setPendingEmail(null); setCode(""); setError(""); setResent(false); }}
                className="inline-flex items-center gap-1 font-mono uppercase tracking-widest-2 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="size-3" /> {t("verify.back")}
              </button>
              <span className="text-muted-foreground">
                {t("verify.notReceived")}{" "}
                <button type="button" onClick={resend} className="font-bold text-primary hover:underline">
                  {t("verify.resend")}
                </button>
              </span>
            </div>
          </div>
        ) : forgotMode ? (
          /* ── Esqueci a senha (email → código + nova senha) ──────────────── */
          <div className="rounded-xl border border-border bg-hud-surface p-6 shadow-elevated">
            <div className="mb-4 flex flex-col items-center text-center">
              <span className="mb-3 inline-flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary">
                <MailCheck className="size-5" />
              </span>
              <h2 className="font-heading text-lg font-bold text-foreground">{t("forgot.title")}</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {forgotMode === "email" ? t("forgot.subEmail") : t("forgot.subReset")}
              </p>
            </div>

            {forgotMode === "email" ? (
              <form onSubmit={submitForgot} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                    {t("login.email")}
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="usuario@email.com"
                    required
                    autoFocus
                    autoComplete="email"
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
                  disabled={loading || !email}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
                  {loading ? t("forgot.sending") : t("forgot.sendCode")}
                </button>
              </form>
            ) : (
              <form onSubmit={submitReset} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                    {t("verify.codeLabel")}
                  </label>
                  <input
                    value={resetCode}
                    onChange={(e) => setResetCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    placeholder="000000"
                    required
                    autoFocus
                    className={`${inputClass} text-center font-mono text-lg tracking-[0.4em]`}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                    {t("forgot.newPassword")}
                  </label>
                  <input
                    type="password"
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    placeholder="••••••••"
                    required
                    minLength={8}
                    autoComplete="new-password"
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
                  disabled={loading || resetCode.length < 6 || newPw.length < 8}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
                  {loading ? t("forgot.resetting") : t("forgot.reset")}
                </button>
              </form>
            )}

            <div className="mt-4 text-[11px]">
              <button
                type="button"
                onClick={() => { setForgotMode(null); setError(""); setResetCode(""); setNewPw(""); }}
                className="inline-flex items-center gap-1 font-mono uppercase tracking-widest-2 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="size-3" /> {t("forgot.backToLogin")}
              </button>
            </div>
          </div>
        ) : (
          /* ── Login / Cadastro ───────────────────────────────────────────── */
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

            {resetDone && (
              <p className="mb-4 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
                {t("forgot.done")}
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
                  placeholder="usuario@email.com"
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
                {tab === "login" && (
                  <div className="flex items-center justify-between gap-3">
                    {/* Saída para quem se cadastrou e perdeu a tela do código. Sem isto a
                        recuperação só acontecia por acidente, ao tentar entrar. */}
                    <button
                      type="button"
                      onClick={recuperarConfirmacao}
                      className="text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-primary"
                    >
                      {t("verify.recoverLink")}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setForgotMode("email"); setError(""); setResetDone(false); }}
                      className="shrink-0 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-primary"
                    >
                      {t("login.forgotPassword")}
                    </button>
                  </div>
                )}
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
        )}

        <p className="text-center font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
          Análise tática • GrindLab AI Engine
        </p>
      </div>
    </div>
  );
};

export default Login;
