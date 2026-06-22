import React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

// Right slide-over for inspecting a record. pt-BR only (admin convention).
export function DetailDrawer({
  open,
  title,
  icon: Icon,
  onClose,
  children,
  width = "max-w-2xl",
}: {
  open: boolean;
  title: string;
  icon?: React.ElementType;
  onClose: () => void;
  children: React.ReactNode;
  width?: string;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-background/70 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div
        className={cn(
          "h-full w-full overflow-y-auto border-l border-border bg-hud-surface shadow-2xl",
          width
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-hud-surface/95 px-5 py-4 backdrop-blur">
          <div className="flex items-center gap-2">
            {Icon && <Icon className="size-4 text-primary" />}
            <h2 className="font-mono text-[12px] font-bold uppercase tracking-widest-2 text-foreground">{title}</h2>
          </div>
          <button onClick={onClose} className="rounded p-1 text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-4" />
          </button>
        </div>
        <div className="p-5 space-y-5">{children}</div>
      </div>
    </div>
  );
}
