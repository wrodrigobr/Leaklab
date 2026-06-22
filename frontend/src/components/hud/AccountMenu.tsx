import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, LogOut, UserCircle, Zap, Users, LayoutDashboard, CreditCard } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { subscription } from "@/lib/api";
import { toast } from "sonner";
import { CheckoutModal } from "./CheckoutModal";

const PLAN_LABEL: Record<string, string> = {
  free:  "Freemium",
  pro:   "Pro",
  coach: "Coach",
};

const PLAN_COLOR: Record<string, string> = {
  free:  "text-muted-foreground bg-muted/40 border-border",
  pro:   "text-primary bg-primary/10 border-primary/30",
  coach: "text-violet-400 bg-violet-400/10 border-violet-400/30",
};

function UsageBar({ used, limit, label }: { used: number; limit: number | null; label: string }) {
  if (limit === null) {
    return (
      <div className="flex items-center justify-between font-mono text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span className="text-primary">ilimitado</span>
      </div>
    );
  }
  const pct    = Math.min(100, Math.round((used / limit) * 100));
  const danger = pct >= 100;
  const warn   = pct >= 80;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between font-mono text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span className={cn(danger ? "text-destructive" : warn ? "text-amber-400" : "")}>
          {used}/{limit}
        </span>
      </div>
      <div className="h-1 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", danger ? "bg-destructive" : warn ? "bg-amber-400" : "bg-primary")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface AccountMenuProps {
  /** COACH-02: workspace ativo (só coaches) + handler de troca, vindos do HudHeader. */
  workspace?: "coach" | "player";
  onSwitchWorkspace?: (w: "coach" | "player") => void;
}

export function AccountMenu({ workspace, onSwitchWorkspace }: AccountMenuProps = {}) {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [checkoutPlan, setCheckoutPlan] = useState<"pro" | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const openPortal = async () => {
    setPortalLoading(true);
    // Abre a aba já no gesto do clique (senão o browser bloqueia como popup);
    // o destino é preenchido quando a URL do portal volta da API.
    const tab = window.open("", "_blank");
    try {
      const { url } = await subscription.portal();
      if (tab) {
        tab.opener = null;          // segurança (equiv. noopener), mantendo a referência
        tab.location.href = url;    // Billing Portal hospedado do Stripe (nova aba)
      } else {
        window.open(url, "_blank", "noopener,noreferrer");  // fallback se a aba foi bloqueada
      }
    } catch (e) {
      tab?.close();
      toast.error(e instanceof Error ? e.message : "Não foi possível abrir o portal.");
    } finally {
      setPortalLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const keyHandler = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", keyHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", keyHandler);
    };
  }, [open]);

  if (!user) return null;

  const plan      = user.plan ?? "free";
  const planLabel = PLAN_LABEL[plan] ?? plan;
  const planColor = PLAN_COLOR[plan] ?? PLAN_COLOR.free;
  const limits    = user.plan_limits ?? { tournaments: 3, ai_calls: 10 };
  const isPlayer  = user.role !== "coach";

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div ref={ref} className="relative">
      {/* Trigger */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full bg-card px-3 py-1.5 ring-1 ring-border hover:ring-primary/40 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Menu da conta"
        aria-expanded={open}
      >
        <span className="font-mono text-[10px] font-medium uppercase tracking-widest-2 text-foreground hidden sm:block">
          {user.username}
        </span>
        <span className={cn("rounded-full border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider hidden sm:block", planColor)}>
          {planLabel}
        </span>
        <ChevronDown className={cn("size-3 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-64 rounded-xl border border-border bg-hud-surface shadow-elevated z-50 overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border space-y-1">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-sm text-foreground">{user.username}</p>
              <span className={cn("rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider", planColor)}>
                {planLabel}
              </span>
            </div>
            <p className="font-mono text-[10px] text-muted-foreground">{user.email}</p>
          </div>

          {/* Quota — só para jogadores */}
          {isPlayer && (
            <div className="px-4 py-3 border-b border-border space-y-2.5">
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Uso este mês</p>
              <UsageBar used={user.tournaments_used ?? 0} limit={limits.tournaments} label="Torneios" />
              <UsageBar used={user.ai_calls_used ?? 0}   limit={limits.ai_calls}    label="Análises GrindLab" />
              {plan === "free" && (
                <button
                  onClick={() => { setOpen(false); setCheckoutPlan("pro"); }}
                  className="flex items-center justify-center gap-1 w-full rounded-md bg-primary py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:opacity-90 transition-opacity"
                >
                  <Zap className="size-3" /> Upgrade para Pro R$99
                </button>
              )}
              {plan === "pro" && (
                <button
                  onClick={openPortal}
                  disabled={portalLoading}
                  className="flex items-center justify-center gap-1.5 w-full rounded-md border border-border py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors disabled:opacity-50"
                >
                  <CreditCard className="size-3" /> {portalLoading ? "Abrindo…" : "Gerenciar assinatura"}
                </button>
              )}
            </div>
          )}

          {/* Workspace: dual-role (coach e admin têm conta de jogador também) */}
          {(user.role === "coach" || user.role === "admin") && workspace && onSwitchWorkspace && (
            <div className="px-4 py-3 border-b border-border space-y-1.5">
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Workspace</p>
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  onClick={() => { setOpen(false); onSwitchWorkspace("coach"); }}
                  className={cn("flex items-center justify-center gap-1.5 rounded-md py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors",
                    workspace === "coach" ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "bg-muted/30 text-muted-foreground hover:text-foreground")}
                >
                  <Users className="size-3" /> {user.role === "admin" ? "Admin" : "Coach"}
                </button>
                <button
                  onClick={() => { setOpen(false); onSwitchWorkspace("player"); }}
                  className={cn("flex items-center justify-center gap-1.5 rounded-md py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors",
                    workspace === "player" ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "bg-muted/30 text-muted-foreground hover:text-foreground")}
                >
                  <LayoutDashboard className="size-3" /> Minha conta
                </button>
              </div>
            </div>
          )}

          {/* Links */}
          <div className="py-1">
            <button
              onClick={() => { setOpen(false); navigate(user.role === "coach" ? "/coach-dashboard/profile" : "/profile"); }}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
            >
              <UserCircle className="size-4" /> Ver perfil
            </button>
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-colors"
            >
              <LogOut className="size-4" /> Sair
            </button>
          </div>
        </div>
      )}

      {checkoutPlan && (
        <CheckoutModal
          plan={checkoutPlan}
          onClose={() => setCheckoutPlan(null)}
          onSuccess={async () => {
            setCheckoutPlan(null);
            await refreshUser();
          }}
        />
      )}
    </div>
  );
}
