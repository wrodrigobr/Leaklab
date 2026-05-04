import { Activity, BarChart3, Bot, Dumbbell, GraduationCap, Globe, LayoutDashboard, Shield, Swords, Trophy, UploadCloud, Users, UserCircle, MessageSquare, X } from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useUploadQueue } from "@/components/hud/UploadQueue";
import { AccountMenu } from "@/components/hud/AccountMenu";
import { CoachMessagesPanel } from "@/components/hud/CoachMessagesPanel";
import { playerMessages } from "@/lib/api";

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
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    if (!chatOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setChatOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chatOpen]);

  const playerNavItems: NavItem[] = [
    { label: t("nav.dashboard"),   mobileLabel: t("nav.dashboard"),   to: "/dashboard",   icon: LayoutDashboard },
    { label: t("nav.tournaments"), mobileLabel: t("nav.tournaments"), to: "/tournaments", icon: Trophy },
    { label: t("nav.study"),       mobileLabel: t("nav.study"),       to: "/study",       icon: GraduationCap },
    {
      label: t("nav.training"), mobileLabel: t("nav.training"),
      to: "/training",
      icon: Dumbbell,
      activePaths: ["/training", "/ghost", "/sparring"],
    },
    { label: t("nav.coach"),   mobileLabel: t("nav.coach"),   to: "/coach",   icon: Bot },
    { label: t("nav.coaches"), mobileLabel: t("nav.coaches"), to: "/coaches", icon: Users },
  ];

  const coachNavItems: NavItem[] = [
    { label: t("nav.coachDashboard"), mobileLabel: t("nav.coachDashboard"), to: "/coach-dashboard",         icon: Users,       end: true },
    { label: t("nav.profile"),        mobileLabel: t("nav.profile"),        to: "/coach-dashboard/profile", icon: UserCircle },
  ];

  const adminNavItems: NavItem[] = [
    { label: t("nav.admin"), mobileLabel: t("nav.admin"), to: "/admin", icon: Shield, end: true },
  ];

  const navItems = (
    user?.role === "admin" ? adminNavItems :
    user?.role === "coach" ? coachNavItems :
    playerNavItems
  );

  const { enqueue, panel } = useUploadQueue(onUpload);

  const { data: unreadData } = useQuery({
    queryKey: ["player-messages-unread"],
    queryFn: playerMessages.unreadCount,
    refetchInterval: 60_000,
    enabled: user?.role === "player" && !!user?.coach_id,
  });
  const unreadCount = unreadData?.unread ?? 0;

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-6 md:gap-10">
            <a href="/dashboard" className="flex items-center gap-2 md:gap-2.5 group" aria-label="LeakLabs home">
              <span className="relative flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-glow">
                <BarChart3 className="size-4" aria-hidden />
              </span>
              <span className="text-base md:text-lg font-semibold tracking-tight uppercase">
                LeakLabs<span className="text-primary italic font-light">.ai</span>
              </span>
            </a>

            <nav className="hidden md:flex items-center gap-1" aria-label="Primary">
              {navItems.map((item) => {
                const activePaths = item.activePaths ?? [item.to];
                const isActive = activePaths.some((p) => location.pathname === p);
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end ?? item.to === "/"}
                    className={() =>
                      `relative flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium tracking-wide uppercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
                      }`
                    }
                  >
                    <item.icon className="size-3.5" aria-hidden />
                    {item.label}
                    {isActive && (
                      <span className="absolute -bottom-[17px] left-2 right-2 h-0.5 bg-primary" />
                    )}
                  </NavLink>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2 md:gap-3">
            <input
              ref={inputRef}
              type="file"
              accept=".txt"
              multiple
              className="hidden"
              onChange={(e) => { if (e.target.files?.length) enqueue(e.target.files); e.target.value = ""; }}
            />
            {user?.role !== "coach" && (
              <button
                onClick={() => inputRef.current?.click()}
                title={t("actions.import")}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 transition-colors focus-visible:outline-none"
              >
                <UploadCloud className="size-3.5" />
                {t("actions.import")}
              </button>
            )}

            {user?.role === "player" && user?.coach_id && (
              <button
                onClick={() => setChatOpen((o) => !o)}
                title={t("coachMessages")}
                className="relative flex items-center justify-center size-8 rounded-full bg-card ring-1 ring-border hover:ring-primary/40 transition-all"
              >
                <MessageSquare className="size-3.5 text-muted-foreground" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 flex size-4 items-center justify-center rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </button>
            )}

            <LanguageSwitcher />

            {user && <AccountMenu />}
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
          className="fixed bottom-0 left-0 right-0 z-50 md:hidden border-t border-border bg-background/95 backdrop-blur-md"
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
                    `flex flex-col items-center gap-0.5 flex-1 rounded-lg px-1 py-2 min-w-0 transition-colors ${
                      isActive ? "text-primary" : "text-muted-foreground"
                    }`
                  }
                >
                  <item.icon className="size-5 shrink-0" aria-hidden />
                  <span className="font-mono text-[8px] uppercase tracking-wide truncate w-full text-center leading-none mt-0.5">
                    {item.mobileLabel}
                  </span>
                </NavLink>
              );
            })}
          </div>
        </nav>
      )}

      {/* ── Mobile FAB — import ───────────────────────────────────────────────── */}
      {user && user.role !== "coach" && (
        <button
          onClick={() => inputRef.current?.click()}
          className="fixed bottom-[72px] right-4 z-50 md:hidden size-12 rounded-full bg-primary text-primary-foreground shadow-glow flex items-center justify-center hover:bg-primary/90 active:scale-95 transition-all"
          aria-label={t("actions.import")}
        >
          <UploadCloud className="size-5" aria-hidden />
        </button>
      )}

      {panel}

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
