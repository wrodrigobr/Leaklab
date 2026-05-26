import { useCallback, useEffect, useRef, useState } from "react";
import { preferences } from "@/lib/api";

export type MainSection = "quality_row" | "bankroll_row" | "street_row" | "dna_row" | "drill_row" | "insight_row";
export type SidebarSection = "leaks" | "causal_map" | "level" | "twin" | "pressure" | "icm";

export interface DashboardLayout {
  main: MainSection[];
  sidebar: SidebarSection[];
}

export const DEFAULT_LAYOUT: DashboardLayout = {
  // Main 8/12: cards GTO em bloco contíguo + evolução ampla.
  // Sidebar 4/12: ação (leaks) no topo, contexto comportamental (pressure/ICM)
  // e perfil estratégico (twin/causal) abaixo.
  main: ["quality_row", "street_row", "bankroll_row", "insight_row", "dna_row"],
  sidebar: ["leaks", "pressure", "icm", "twin", "causal_map", "level"],
};

export function useDashboardLayout() {
  const [layout, setLayout] = useState<DashboardLayout>(DEFAULT_LAYOUT);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    preferences.get()
      .then((prefs) => {
        const saved = prefs.dashboard_layout as DashboardLayout | null;
        if (saved?.main && saved?.sidebar) {
          // Merge: keep user's order, append any new sections from DEFAULT_LAYOUT
          const mergedSidebar = [
            ...saved.sidebar.filter((s) => (DEFAULT_LAYOUT.sidebar as string[]).includes(s)),
            ...DEFAULT_LAYOUT.sidebar.filter((s) => !(saved.sidebar as string[]).includes(s)),
          ] as SidebarSection[];
          const mergedMain = [
            ...saved.main.filter((s) => (DEFAULT_LAYOUT.main as string[]).includes(s)),
            ...DEFAULT_LAYOUT.main.filter((s) => !(saved.main as string[]).includes(s)),
          ] as MainSection[];
          setLayout({ main: mergedMain, sidebar: mergedSidebar });
        }
      })
      .catch(() => {});
  }, []);

  const persist = useCallback((next: DashboardLayout) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      preferences.save(next).catch(() => {});
    }, 800);
  }, []);

  const updateMain = useCallback((newMain: MainSection[]) => {
    setLayout((prev) => {
      const next = { ...prev, main: newMain };
      persist(next);
      return next;
    });
  }, [persist]);

  const updateSidebar = useCallback((newSidebar: SidebarSection[]) => {
    setLayout((prev) => {
      const next = { ...prev, sidebar: newSidebar };
      persist(next);
      return next;
    });
  }, [persist]);

  const reset = useCallback(() => {
    setLayout(DEFAULT_LAYOUT);
    preferences.save(DEFAULT_LAYOUT).catch(() => {});
  }, []);

  return { layout, updateMain, updateSidebar, reset };
}
