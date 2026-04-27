import { Activity, BarChart3, Bot, GraduationCap, LayoutDashboard, LogOut, Trophy, UploadCloud, Users, UserCircle } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { useRef } from "react";
import { useAuth } from "@/lib/auth";
import { useUploadQueue } from "@/components/hud/UploadQueue";

interface HudHeaderProps {
  onUpload?: () => void;
}

const playerNavItems = [
  { label: "Dashboard",        to: "/",                icon: LayoutDashboard },
  { label: "Tournaments",      to: "/tournaments",     icon: Trophy },
  { label: "Plano de Estudos", to: "/study",           icon: GraduationCap, badge: "NEW" },
  { label: "AI Coach",         to: "/coach",           icon: Bot, badge: "ALPHA" },
  { label: "Coaches",          to: "/coaches",         icon: Users },
  { label: "Perfil",           to: "/profile",         icon: UserCircle },
];

const coachNavItems = [
  { label: "Dashboard", to: "/coach-dashboard",         icon: Users,       end: true },
  { label: "Perfil",    to: "/coach-dashboard/profile", icon: UserCircle },
];

export function HudHeader({ onUpload }: HudHeaderProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const navItems = user?.role === "coach" ? coachNavItems : playerNavItems;
  const { enqueue, panel } = useUploadQueue(onUpload);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <>
    <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-6 md:px-8">
        <div className="flex items-center gap-10">
          <a href="/" className="flex items-center gap-2.5 group" aria-label="LeakLabs home">
            <span className="relative flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-glow">
              <BarChart3 className="size-4" aria-hidden />
            </span>
            <span className="text-lg font-semibold tracking-tight uppercase">
              LeakLabs<span className="text-primary italic font-light">.ai</span>
            </span>
          </a>

          <nav className="hidden md:flex items-center gap-1" aria-label="Primary">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={"end" in item ? item.end : item.to === "/"}
                className={({ isActive }) =>
                  `relative flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium tracking-wide uppercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon className="size-3.5" aria-hidden />
                    {item.label}
                    {item.badge && (
                      <span className="ml-1 rounded-sm bg-primary/10 px-1.5 py-0.5 text-[9px] font-mono font-semibold text-primary ring-1 ring-primary/30">
                        {item.badge}
                      </span>
                    )}
                    {isActive && (
                      <span className="absolute -bottom-[17px] left-2 right-2 h-0.5 bg-primary" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {/* Compact upload button */}
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
              title="Importar torneio"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30 hover:bg-primary/20 transition-colors focus-visible:outline-none"
            >
              <UploadCloud className="size-3.5" />
              Import
            </button>
          )}

          {user?.coach_id && user.role !== "coach" && (
            <div className="hidden sm:flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 ring-1 ring-primary/30">
              <GraduationCap className="size-3 text-primary" />
              <span className="font-mono text-[10px] font-medium uppercase tracking-widest-2 text-primary">
                {user.coach_username}
              </span>
            </div>
          )}

          <div className="hidden sm:flex items-center gap-2 rounded-full bg-card px-3 py-1.5 ring-1 ring-border">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-primary opacity-75 animate-ping" />
              <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
            </span>
            <span className="font-mono text-[10px] font-medium uppercase tracking-widest-2 text-muted-foreground">
              Engine Active
            </span>
          </div>

          {user && (
            <div className="flex items-center gap-2">
              <span className="hidden sm:block font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
                {user.username}
              </span>
              <button
                onClick={handleLogout}
                className="size-9 rounded-full bg-card ring-2 ring-border hover:ring-primary/40 transition-all flex items-center justify-center text-xs font-semibold text-foreground"
                aria-label="Sair"
                title="Sair"
              >
                <LogOut className="size-4 text-muted-foreground hover:text-destructive transition-colors" aria-hidden />
              </button>
            </div>
          )}

          {!user && (
            <button
              onClick={() => navigate("/login")}
              className="size-9 rounded-full bg-card ring-2 ring-border hover:ring-primary/40 transition-all flex items-center justify-center"
              aria-label="Entrar"
            >
              <Activity className="size-4 text-primary" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </header>
    {panel}
  </>
  );
}
