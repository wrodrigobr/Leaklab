import { useCallback, useEffect, useRef, useState } from "react";
import { preferences } from "@/lib/api";

// Bento: lista ÚNICA de cards (achatada). Cada card tem um span por tamanho de conteúdo
// (ver SECTION_SPAN). Substitui o antigo modelo de 2 colunas {main, sidebar}.
export type DashSection =
  | "quality" | "alignment" | "position" | "matrix" | "leakfinder" | "results"
  | "bankroll" | "career" | "cognitive" | "dna"
  | "pressure" | "icm" | "leaks" | "causal_map" | "twin";

export const DEFAULT_SECTIONS: DashSection[] = [
  // Status / análise GTO
  "quality", "alignment", "position",
  "matrix", "leakfinder", "results",
  // Resultado / evolução
  "bankroll", "career", "cognitive",
  // Perfil / risco
  "dna", "pressure", "icm", "leaks", "causal_map", "twin",
];

// Span por tipo de conteúdo (12 cols no lg). base=1-col (full), md=2-col (full p/ largos),
// lg=bento. Os largos (gráficos/matriz/leakfinder) ocupam md:2; os compactos, md:1.
export const SECTION_SPAN: Record<DashSection, string> = {
  quality:    "lg:col-span-4",                  // score GTO
  alignment:  "lg:col-span-4",                  // breakdown
  position:   "lg:col-span-4",                  // breakdown
  matrix:     "md:col-span-2 lg:col-span-6",    // matriz 2D
  leakfinder: "md:col-span-2 lg:col-span-6",    // carro-chefe (lista) — span-6
  results:    "md:col-span-2 lg:col-span-6",    // comparação
  bankroll:   "md:col-span-2 lg:col-span-8",    // time-series
  career:     "md:col-span-2 lg:col-span-8",    // time-series
  cognitive:  "md:col-span-2 lg:col-span-6",    // comparação
  dna:        "lg:col-span-4",                  // radar
  pressure:   "lg:col-span-4",                  // radar
  icm:        "lg:col-span-4",                  // lista
  leaks:      "lg:col-span-4",                  // lista
  causal_map: "md:col-span-2 lg:col-span-8",    // grafo/mapa
  twin:       "lg:col-span-4",                  // lista
};

interface SavedLayout {
  sections?: DashSection[];
}

export function useDashboardLayout() {
  const [sections, setSections] = useState<DashSection[]>(DEFAULT_SECTIONS);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    preferences.get()
      .then((prefs) => {
        const saved = prefs.dashboard_layout as SavedLayout | null;
        // Só aceita o NOVO formato (sections). Layouts antigos {main,sidebar} caem no
        // default do bento (migração silenciosa do redesenho).
        if (saved?.sections && Array.isArray(saved.sections)) {
          const valid = saved.sections.filter((s) => (DEFAULT_SECTIONS as string[]).includes(s));
          // mantém a ordem do usuário + anexa qualquer card novo do DEFAULT
          const merged = [
            ...valid,
            ...DEFAULT_SECTIONS.filter((s) => !valid.includes(s)),
          ] as DashSection[];
          setSections(merged);
        }
      })
      .catch(() => {});
  }, []);

  const persist = useCallback((next: DashSection[]) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      preferences.save({ sections: next }).catch(() => {});
    }, 800);
  }, []);

  const updateSections = useCallback((next: DashSection[]) => {
    setSections(next);
    persist(next);
  }, [persist]);

  const reset = useCallback(() => {
    setSections(DEFAULT_SECTIONS);
    preferences.save({ sections: DEFAULT_SECTIONS }).catch(() => {});
  }, []);

  return { sections, updateSections, reset };
}
