import React, { useState } from "react";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type AdminSection =
  | "overview"
  | "finance"
  | "users"
  | "coaches"
  | "support"
  | "candidaturas"
  | "gto-worker"
  | "logs"
  ;

export interface NavItem {
  id: AdminSection;
  label: string;
  icon: React.ElementType;
  badge?: number;     // numeric badge (tickets / candidaturas)
  dot?: boolean;      // attention dot (teal) when actionable
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

function ItemButton({
  item,
  active,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <button
      onClick={onClick}
      className={cn(
        "group flex w-full items-center gap-2.5 rounded-md px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors",
        active
          ? "bg-primary/10 text-primary ring-1 ring-primary/20"
          : "text-muted-foreground hover:bg-hud-elevated/50 hover:text-foreground"
      )}
    >
      <Icon className={cn("size-4 shrink-0", active ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
      <span className="flex-1 text-left normal-case tracking-normal text-[12px]">{item.label}</span>
      {item.badge != null && item.badge > 0 && (
        <span className="inline-flex min-w-[18px] items-center justify-center rounded-full bg-destructive px-1.5 py-0.5 text-[9px] font-bold text-destructive-foreground tabular-nums">
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      )}
      {item.dot && (item.badge == null || item.badge === 0) && (
        <span className="size-1.5 shrink-0 rounded-full bg-primary shadow-[0_0_6px_hsl(var(--primary))]" />
      )}
    </button>
  );
}

function NavList({
  groups,
  active,
  onSelect,
}: {
  groups: NavGroup[];
  active: AdminSection;
  onSelect: (id: AdminSection) => void;
}) {
  return (
    <nav className="space-y-5">
      {groups.map((g) => (
        <div key={g.label} className="space-y-1">
          <p className="px-3 font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground/60">
            {g.label}
          </p>
          {g.items.map((it) => (
            <ItemButton key={it.id} item={it} active={active === it.id} onClick={() => onSelect(it.id)} />
          ))}
        </div>
      ))}
    </nav>
  );
}

export function AdminSidebar({
  groups,
  active,
  onSelect,
}: {
  groups: NavGroup[];
  active: AdminSection;
  onSelect: (id: AdminSection) => void;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop sticky sidebar */}
      <aside className="hidden lg:block w-56 shrink-0">
        <div className="sticky top-6">
          <NavList groups={groups} active={active} onSelect={onSelect} />
        </div>
      </aside>

      {/* Mobile trigger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden inline-flex items-center gap-2 rounded-md border border-border bg-hud-surface px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground"
      >
        <Menu className="size-4" /> Menu
      </button>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex bg-background/70 backdrop-blur-sm animate-fade-in" onClick={() => setMobileOpen(false)}>
          <div className="h-full w-64 overflow-y-auto border-r border-border bg-hud-surface p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <span className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary">Admin</span>
              <button onClick={() => setMobileOpen(false)} className="rounded p-1 text-muted-foreground hover:text-foreground">
                <X className="size-4" />
              </button>
            </div>
            <NavList
              groups={groups}
              active={active}
              onSelect={(id) => {
                onSelect(id);
                setMobileOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </>
  );
}
