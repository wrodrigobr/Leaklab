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

// Masonry de 2 COLUNAS uniformes: TODO card ocupa metade (lg:col-span-6 = 6 de 12 → 2 por
// linha). Largura uniforme é o que torna o masonry (useMasonryRows) realmente gap-free e a
// posição estável — full-width vira "barreira" que dessincroniza as colunas e reabre vãos.
// 676px é largura ótima p/ tudo (matriz 13×13, time-series, listas, radares). Se algum card
// precisar de full-width no futuro, troque pontualmente p/ lg:col-span-12 (ciente do gap).
// base=1-col, md=2-col (default span-1), lg=2-col via span-6.
export const SECTION_SPAN: Record<DashSection, string> = {
  quality:    "lg:col-span-6",
  alignment:  "lg:col-span-6",
  position:   "lg:col-span-6",
  matrix:     "lg:col-span-6",
  leakfinder: "lg:col-span-6",
  results:    "lg:col-span-6",
  bankroll:   "lg:col-span-6",
  career:     "lg:col-span-6",
  cognitive:  "lg:col-span-6",
  dna:        "lg:col-span-6",
  pressure:   "lg:col-span-6",
  icm:        "lg:col-span-6",
  leaks:      "lg:col-span-6",
  causal_map: "lg:col-span-6",
  twin:       "lg:col-span-6",
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
