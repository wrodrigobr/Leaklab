import { Menu as MenuIcon, Lock, Activity, Bot, Dumbbell, GraduationCap, Globe, LayoutDashboard, Medal, Shield, Swords, Trophy, UploadCloud, Users, UserCircle, MessageSquare, LifeBuoy, X } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useUploadQueue } from "@/components/hud/UploadQueue";
import { AccountMenu } from "@/components/hud/AccountMenu";
import { CoachMessagesPanel } from "@/components/hud/CoachMessagesPanel";
import { SupportModal } from "@/components/hud/SupportModal";
import { NotificationBell } from "@/components/hud/NotificationBell";
import { playerMessages, support, coaches, training, subscription } from "@/lib/api";
import { GRUPOS, ITEM_COACH } from "./navGrupos";
import { MenuDeGrupo } from "./MenuDeGrupo";
import { FolhaDeMenu } from "./FolhaDeMenu";

interface HudHeaderProps {
  onUpload?: () => void;
}

type NavItem = {
  label: string;
  mobileLabel: string;
  to: string;
  icon: React.ElementType;
  end?: boolean;
  activePaths?: string[];
  dot?: boolean;          // selo de pendência (ex.: lição do dia não feita)
};

const LANGUAGES = [
  { code: "pt-BR", label: "PT", flag: "🇧🇷" },
  { code: "en",    label: "EN", flag: "🇺🇸" },
  { code: "es",    label: "ES", flag: "🇪🇸" },
] as const;

function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const current = LANGUAGES.find((l) => i18n.language.startsWith(l.code.split("-")[0]) && (l.code === "pt-BR" ? i18n.language.startsWith("pt") : true))
    ?? LANGUAGES.find((l) => i18n.language.startsWith(l.code.split("-")[0]))
    ?? LANGUAGES[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-md bg-card px-2.5 py-1.5 ring-1 ring-border text-muted-foreground hover:text-foreground transition-colors focus-visible:outline-none"
        aria-label="Change language"
      >
        <Globe className="size-3" aria-hidden />
        <span className="font-mono text-[10px] font-bold uppercase tracking-wide">{current.label}</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-50 min-w-[80px] rounded-lg border border-border bg-card shadow-elevated overflow-hidden">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => { i18n.changeLanguage(lang.code); setOpen(false); }}
                className={`flex w-full items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-wide transition-colors hover:bg-primary/10 ${
                  lang.code === current.code ? "text-primary" : "text-muted-foreground"
                }`}
              >
                <span>{lang.flag}</span>
                <span>{lang.label}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function HudHeader({ onUpload }: HudHeaderProps) {
  const { user } = useAuth();
  const { t } = useTranslation("common");
  const navigate = useNavigate();
  const location = useLocation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [chatOpen, setChatOpen]       = useState(false);
  const [supportOpen, setSupportOpen] = useState(false);

  useEffect(() => {
    if (!chatOpen && !supportOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setChatOpen(false); setSupportOpen(false); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chatOpen, supportOpen]);

  // Deep-link da notificação de mensagem do coach (?chat=1) → abre o drawer e limpa o param.
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("chat") === "1" && user?.role === "player" && user?.coach_id) {
      setChatOpen(true);
      params.delete("chat");
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
    }
  }, [location.search, location.pathname, user?.role, user?.coach_id, navigate]);

  // Marketplace de coaches só aparece se houver coach cadastrado — sem coaches, esconde o item
  // (ganha espaço na nav). Endpoint público + cache do react-query (sem re-fetch a cada nav).
  const { data: coachDir } = useQuery({
    queryKey: ["public-coaches-exist"],
    queryFn: () => coaches.list({ limit: 1 }),
    staleTime: 5 * 60 * 1000,
  });
  const hasCoaches = (coachDir?.coaches?.length ?? 0) > 0;

  // Nudge da lição do dia: selo no item "Treino" quando a lição de hoje está pendente (fuso local).
  // Declarado ANTES de playerNavItems (que usa lessonPending no 'dot') — senão dá TDZ.
  const { data: dailyStatus } = useQuery({
    queryKey: ["training-daily-status"],
    queryFn: training.dailyStatus,
    refetchInterval: 300_000,
    enabled: user?.role === "player",
  });
  const lessonPending = !!dailyStatus?.lesson_pending;

  // ── As capacidades vem do BACKEND, nao de uma lista no front (28/08) ────────────────────
  //
  // `/subscription/status` devolve `limits` com `ghost`, `leak_targeted`, `ai_coach_chat`. O menu
  // pergunta a ele onde vai cadeado. Recriar aqui a regra de "o que e Pro" seria a segunda fonte
  // de verdade sobre o plano -- o padrao que este projeto passou o dia inteiro consertando: o
  // preco estava escrito a mao em seis lugares.
  //
  // 5 minutos de cache: plano nao muda a cada clique, e um cadeado que pisca e pior que nenhum.
  const { data: quota } = useQuery({
    queryKey: ["subscription-status"],
    queryFn: subscription.status,
    staleTime: 300_000,
    enabled: user?.role === "player",
  });
  const capacidades = quota?.limits as
    Record<string, boolean | number | null | undefined> | undefined;

  // A barra antiga tinha 11 links para 47 rotas de jogador. Os grupos vivem em `navGrupos.ts`;
  // aqui fica so a decisao de QUEM ve o que. Ver o cabecalho daquele arquivo.
  const [folhaAberta, setFolhaAberta] = useState(false);
  const ocultarNoMenu = hasCoaches ? [] : ["/coaches"];

  // A barra inferior do mobile mostra a RAIZ de cada grupo, derivada da mesma lista. Cinco botoes
  // nao cabem 47 rotas, e o painel com subitens nao cabe numa barra de icones -- mas duas
  // declaracoes do que existe divergiriam no primeiro item novo (regra 5).
  // ── A barra do celular guarda os DESTINOS DIARIOS, nao as raizes dos grupos ────────────
  //
  // A 1a versao derivava a barra dos GRUPOS: quatro botoes apontando para as raizes. Medido, isso
  // TIROU acesso -- Torneios perdeu o toque direto, o AI Coach sumiu da barra -- e nao devolveu
  // nada, porque os subitens so existiam no painel do desktop. O dono perguntou se no celular nao
  // era melhor manter como estava, e estava certo.
  //
  // Reverter tambem nao resolveria: as 47 rotas seguem invisiveis no celular. A saida e barra +
  // folha -- aqui ficam os quatro de uso diario, e o botao "Menu" abre `FolhaDeMenu` com o
  // produto inteiro e os mesmos cadeados.
  const playerNavItems: NavItem[] = [
    { label: t("nav.dashboard"),   mobileLabel: t("nav.dashboard"),   to: "/dashboard",   icon: LayoutDashboard },
    { label: t("nav.tournaments"), mobileLabel: t("nav.tournaments"), to: "/tournaments", icon: Trophy },
    { label: t("nav.training"),    mobileLabel: t("nav.training"),    to: "/training",    icon: Dumbbell,
      dot: lessonPending, activePaths: ["/training", "/leak-trainer", "/ghost", "/grind"] },
    { label: t("nav.coach"),       mobileLabel: t("nav.coach"),       to: "/coach",       icon: Bot },
  ];


  const coachNavItems: NavItem[] = [
    { label: t("nav.coachDashboard"), mobileLabel: t("nav.coachDashboard"), to: "/coach-dashboard",         icon: Users,       end: true },
    { label: t("nav.profile"),        mobileLabel: t("nav.profile"),        to: "/coach-dashboard/profile", icon: UserCircle },
  ];

  const adminNavItems: NavItem[] = [
    { label: t("nav.admin"), mobileLabel: t("nav.admin"), to: "/admin", icon: Shield, end: true },
  ];

  // COACH-02 P2: o coach é dual-role. Switch de workspace (persistido) alterna entre
  // o command center ("Modo Coach") e a conta de aluno ("Minha conta").
  const isCoach = user?.role === "coach";
  const isAdmin = user?.role === "admin";
  const dualRole = isCoach || isAdmin;   // coach e admin têm conta de jogador também
  const commandRoute = isAdmin ? "/admin" : "/coach-dashboard";
  // "coach" = lado de comando (coach-dashboard / admin); "player" = conta de aluno.
  const [workspace, setWorkspace] = useState<"coach" | "player">(() =>
    (typeof window !== "undefined" && localStorage.getItem("coachWorkspace") === "player") ? "player" : "coach"
  );
  const switchWorkspace = (w: "coach" | "player") => {
    setWorkspace(w);
    try { localStorage.setItem("coachWorkspace", w); } catch { /* ignore */ }
    navigate(w === "coach" ? commandRoute : "/dashboard");
  };
  const inPlayerWorkspace = dualRole && workspace === "player";
  const canUpload = user?.role === "player" || inPlayerWorkspace;

  // Grupos so no espaco de JOGADOR: coach e admin tem meia duzia de telas cada, e dar
  // painel a eles seria enfeite. Declarado AQUI, depois de isAdmin/isCoach/inPlayerWorkspace
  // -- as tres nascem algumas linhas acima e usa-las antes da TDZ.
  // O menu de grupos e do espaco de JOGADOR. Admin e coach tem meia duzia de telas cada.
  //
  // A 1a versao excluia o admin por completo -- e o DONO e admin, entao ele nunca viu o menu que
  // acabara de pedir. "Nao esta funcionando" era isso: nao havia o que abrir. O admin so perde os
  // grupos quando esta de fato no espaco de admin; no dashboard de jogador ele e jogador.
  const mostraGrupos = !isCoach || inPlayerWorkspace;

  const navItems = (
    inPlayerWorkspace ? playerNavItems :
    isAdmin ? adminNavItems :
    isCoach ? coachNavItems :
    playerNavItems
  );

  const { enqueue } = useUploadQueue();   // fila global (painel renderizado no App, sobrevive à navegação)

  const { data: unreadData } = useQuery({
    queryKey: ["player-messages-unread"],
    queryFn: playerMessages.unreadCount,
    refetchInterval: 60_000,
    enabled: user?.role === "player" && !!user?.coach_id,
  });
  const unreadCount = unreadData?.unread ?? 0;

  const { data: supportRepliesData } = useQuery({
    queryKey: ["my-support-unread"],
    queryFn: support.myUnreadCount,
    refetchInterval: 120_000,
    enabled: !!user && user.role !== "admin",
  });
  const supportReplies = supportRepliesData?.replied ?? 0;

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-md pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-3 px-4 md:px-8">
          <div className="flex min-w-0 items-center gap-6 md:gap-10">
            <a href="/dashboard" className="flex shrink-0 items-center group" aria-label="GrindLab home">
              <img src={logoHorizontal} alt="GrindLab" className="h-12 w-auto" />
            </a>

            {/* Nav no topo só a partir de lg (1024): abaixo disso (incl. celular deitado, 768–1024)
                o nav fica FIXO embaixo (md→lg evita o scroll lateral cramped do header). */}
            <nav
              /* ── Sem `overflow-x-auto` (28/08) ────────────────────────────────────────
                 Ele existia para rolar 11 links. Com 5 grupos nao e mais preciso, e ele
                 QUEBRAVA o menu: `overflow: auto` cria contexto de recorte, entao o painel do
                 grupo -- que e filho absoluto -- era cortado fora da barra. O painel existia no
                 DOM, mas o mouse nunca chegava nele: o container recebia `mouseleave` e fechava.
                 Medido: `elementFromPoint` 2px abaixo do titulo devolvia uma DIV do cabecalho.
                 `flex-wrap` cobre o caso de a barra nao caber, sem recortar nada. */
              className="hidden lg:flex flex-wrap items-center gap-1 min-w-0"
              aria-label="Primary"
            >
              {/* ── Jogador ve GRUPOS; coach e admin seguem com a barra simples ─────────
                  O menu com painel existe porque o produto de jogador tem 47 rotas e a barra
                  oferecia 11. Coach e admin tem meia duzia de telas cada: dar painel a eles seria
                  enfeite. */}
              {mostraGrupos
                ? (
                  <>
                    {GRUPOS.map((g) => (
                      <MenuDeGrupo key={g.to} grupo={g} capacidades={capacidades}
                                   ocultar={ocultarNoMenu} />
                    ))}
                    <NavLink
                      to={ITEM_COACH.to}
                      className={() =>
                        `relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition-colors ${
                          location.pathname.startsWith("/coach") && !location.pathname.startsWith("/coaches")
                            ? "text-primary" : "text-muted-foreground hover:text-foreground"
                        }`
                      }
                    >
                      <Bot className="size-3.5" aria-hidden />
                      {t(ITEM_COACH.chave)}
                      {capacidades && capacidades[ITEM_COACH.exige!] === false && (
                        <Lock className="size-2.5 text-primary" aria-hidden />
                      )}
                    </NavLink>
                  </>
                )
                : navItems.map((item) => {

                const activePaths = item.activePaths ?? [item.to];
                // Por PREFIXO (costura 14): /academy/math acende Estudos, /training-v2 acende
                // Treinos. Fronteira de segmento ("/" ou fim) evita /coach casar /coaches.
                const isActive = activePaths.some((p) =>
                  location.pathname === p || location.pathname.startsWith(p + "/"));
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    /* Âncora do tour: só o item de treino. `data-tour` é NOME, não seletor — se o
                       item sair do menu, o passo se auto-pula em vez de apontar para o vazio. */
                    data-tour={item.to === "/training" ? "treino" : undefined}
                    end={item.end ?? item.to === "/"}
                    className={() =>
                      `relative flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium tracking-wide uppercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
                      }`
                    }
                  >
                    <item.icon className="size-3.5" aria-hidden />
                    {item.label}
                    {item.dot && (
                      <span className="absolute right-0.5 top-0.5 size-1.5 rounded-full bg-amber-400 ring-2 ring-background" aria-hidden />
                    )}
                    {isActive && (
                      <span className="absolute -bottom-[17px] left-2 right-2 h-0.5 bg-primary" />
                    )}
                  </NavLink>
                );
              })}
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-2 md:gap-3">
            <input
              ref={inputRef}
              type="file"
              accept=".txt"
              multiple
              className="hidden"
              onChange={(e) => { if (e.target.files?.length) enqueue(e.target.files); e.target.value = ""; }}
            />
            {canUpload && (
              <button
                onClick={() => inputRef.current?.click()}
                title={t("actions.import")}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 transition-colors focus-visible:outline-none"
              >
                <UploadCloud className="size-3.5" />
                {/* faixa md–lg é apertada (nav rolável): label só ≥lg, ícone basta antes */}
                <span className="hidden lg:inline">{t("actions.import")}</span>
              </button>
            )}

            {/* Inbox unificado: notificações + atalhos de conversa (chat coach + suporte)
                num único sino. Antes eram dois ícones (Mensagens + Notificações). */}
            {user && (() => {
              const isAdmin = user.role === "admin";
              const hasCoachChat = user.role === "player" && !!user.coach_id;
              const convUnread = isAdmin ? 0 : ((hasCoachChat ? unreadCount : 0) + supportReplies);
              const renderActions = isAdmin ? undefined : (close: () => void) => (
                <>
                  {hasCoachChat && (
                    <button
                      onClick={() => { close(); setChatOpen(true); }}
                      className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-xs text-foreground hover:bg-primary/10 transition-colors"
                    >
                      <MessageSquare className="size-3.5 text-primary shrink-0" />
                      <span className="flex-1">{t("coachMessages")}</span>
                      {unreadCount > 0 && (
                        <span className="flex size-4 items-center justify-center rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground">
                          {unreadCount > 9 ? "9+" : unreadCount}
                        </span>
                      )}
                    </button>
                  )}
                  <button
                    onClick={() => { close(); setSupportOpen(true); }}
                    className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-xs text-foreground hover:bg-primary/10 transition-colors"
                  >
                    <LifeBuoy className="size-3.5 text-primary shrink-0" />
                    <span className="flex-1">{t("messages.support")}</span>
                    {supportReplies > 0 && (
                      <span className="flex size-4 items-center justify-center rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground">
                        {supportReplies > 9 ? "9+" : supportReplies}
                      </span>
                    )}
                  </button>
                </>
              );
              return <NotificationBell renderActions={renderActions} extraUnread={convUnread} />;
            })()}

            <LanguageSwitcher />

            {user && <AccountMenu workspace={dualRole ? workspace : undefined} onSwitchWorkspace={dualRole ? switchWorkspace : undefined} />}
            {!user && (
              <button
                onClick={() => navigate("/login")}
                className="size-9 rounded-full bg-card ring-2 ring-border hover:ring-primary/40 transition-all flex items-center justify-center"
                aria-label="Sign in"
              >
                <Activity className="size-4 text-primary" aria-hidden />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── Mobile bottom nav ─────────────────────────────────────────────────── */}
      {user && (
        <nav
          className="fixed bottom-0 left-0 right-0 z-50 lg:hidden border-t border-border bg-background/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]"
          aria-label="Mobile navigation"
        >
          <div className="flex justify-around px-1 py-1">
            {navItems.map((item) => {
              const activePaths = item.activePaths ?? [item.to];
              const isActive = activePaths.some((p) => location.pathname === p);
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end ?? item.to === "/"}
                  className={() =>
                    `relative flex flex-col items-center gap-0.5 flex-1 rounded-lg px-1 py-2 min-w-0 transition-colors ${
                      isActive ? "text-primary" : "text-muted-foreground"
                    }`
                  }
                >
                  <item.icon className="size-5 shrink-0" aria-hidden />
                  {item.dot && (
                    <span className="absolute right-[22%] top-1 size-1.5 rounded-full bg-amber-400 ring-2 ring-background" aria-hidden />
                  )}
                  <span className="font-mono text-[8px] uppercase tracking-wide truncate w-full text-center leading-none mt-0.5">
                    {item.mobileLabel}
                  </span>
                </NavLink>
              );
            })}
            {/* O 5o botao: abre o produto INTEIRO. Sem ele o celular fica com quatro destinos e
                as outras 43 rotas invisiveis -- foi o que a 1a versao do menu causou. */}
            {mostraGrupos && (
              <button
                type="button"
                onClick={() => setFolhaAberta(true)}
                aria-label={t("nav.menu")}
                className="relative flex flex-1 flex-col items-center justify-center rounded-md px-1 py-1.5 text-muted-foreground transition-colors active:text-primary"
              >
                <MenuIcon className="size-5 shrink-0" aria-hidden />
                <span className="mt-0.5 w-full truncate text-center font-mono text-[8px] uppercase leading-none tracking-wide">
                  {t("nav.menu")}
                </span>
              </button>
            )}
          </div>
        </nav>
      )}

      {mostraGrupos && (
        <FolhaDeMenu
          aberta={folhaAberta}
          aoFechar={() => setFolhaAberta(false)}
          capacidades={capacidades}
          ocultar={ocultarNoMenu}
        />
      )}

      {/* ── Mobile FAB — import ───────────────────────────────────────────────── */}
      {user && canUpload && (
        <button
          onClick={() => inputRef.current?.click()}
          className="fixed bottom-[72px] right-4 z-50 lg:hidden size-12 rounded-full bg-primary text-primary-foreground shadow-glow flex items-center justify-center hover:bg-primary/90 active:scale-95 transition-all"
          aria-label={t("actions.import")}
        >
          <UploadCloud className="size-5" aria-hidden />
        </button>
      )}

      {/* ── Support modal ─────────────────────────────────────────────────────── */}
      {supportOpen && (
        <SupportModal
          onClose={() => setSupportOpen(false)}
          initialTab={supportReplies > 0 ? "inbox" : "new"}
        />
      )}

      {/* ── Coach chat drawer ─────────────────────────────────────────────────── */}
      {chatOpen && user?.role === "player" && user?.coach_id && (
        <>
          <div
            className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
            onClick={() => setChatOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 z-[61] flex w-full flex-col sm:w-96 bg-background border-l border-border shadow-2xl">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <div className="flex items-center gap-2">
                <GraduationCap className="size-4 text-primary" />
                <span className="font-mono text-[11px] font-bold uppercase tracking-widest text-foreground">
                  {user.coach_username ? `Coach ${user.coach_username}` : t("coachMessages")}
                </span>
              </div>
              <button
                onClick={() => setChatOpen(false)}
                className="rounded-md p-1.5 hover:bg-muted transition-colors"
                aria-label="Fechar"
              >
                <X className="size-4 text-muted-foreground" />
              </button>
            </div>
            <CoachMessagesPanel
              coachUsername={user.coach_username ?? undefined}
              drawer
            />
          </div>
        </>
      )}
    </>
  );
}
