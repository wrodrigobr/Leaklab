import { BankrollChart } from "@/components/hud/BankrollChart";
import { GtoPositionCard } from "@/components/hud/GtoPositionCard";
import { GtoQualityCard } from "@/components/hud/GtoQualityCard";
import { LeakFinderCard } from "@/components/hud/LeakFinderCard";
import { LeaksPanel } from "@/components/hud/LeaksPanel";
import { LeakCausalMap } from "@/components/hud/LeakCausalMap";
import { CareerGraphCard } from "@/components/hud/CareerGraphCard";
import { CognitiveFailureCard } from "@/components/hud/CognitiveFailureCard";
import { SessionContextCard } from "@/components/hud/SessionContextCard";
import { StrategicTwinCard } from "@/components/hud/StrategicTwinCard";
import { PressureProfileCard } from "@/components/hud/PressureProfileCard";
import { PlayerDnaCard } from "@/components/hud/PlayerDnaCard";
import { ResultsVsGtoCard } from "@/components/hud/ResultsVsGtoCard";
import { V2ResultsCard } from "@/components/hud/V2ResultsCard";
import { V2PressureCard } from "@/components/hud/V2PressureCard";
import { V2CognitiveCard } from "@/components/hud/V2CognitiveCard";
import { V2TwinCard } from "@/components/hud/V2TwinCard";
import { V2CausalMapCard } from "@/components/hud/V2CausalMapCard";
import { ProLockCard } from "@/components/hud/ProLockCard";
import { DashSection } from "@/hooks/useDashboardLayout";
import {
  EvolutionResponse, LeakRoiData, PressureProfile, PlayerDnaResponse, LeakGraphResponse,
  CareerProjection, CognitiveFailureData, StrategicTwinProfile, GtoPositionData, GtoQualityData,
  ResultsVsGtoData, LeakFinderData, SessionContextData,
} from "@/lib/api";

/**
 * Mapa `id do card` → JSX, para o bento do dashboard.
 *
 * Vivia dentro de `pages/Index.tsx`, fechado sobre o estado dele. Saiu para cá quando a tela de
 * DEMONSTRAÇÃO (`/demo`) passou a precisar exatamente dos mesmos cards com dados de outra origem:
 * a alternativa era copiar o mapa, e cópia de vitrine passa a mentir sozinha no dia em que um
 * card muda — sem quebrar nada, que é o pior jeito de errar.
 *
 * É função PURA dos dados: quem chama decide de onde eles vêm (API do jogador, no Index; fixture
 * congelada, na demonstração).
 */
export interface DadosDoDashboard {
  evo:               EvolutionResponse | null;
  leakRoi:           LeakRoiData[];
  leakSource:        "gto" | "heuristic" | null;
  pressureData:      PressureProfile | null;
  dnaData:           PlayerDnaResponse | null;
  leakGraph:         LeakGraphResponse | null;
  careerData:        CareerProjection | null;
  cognitiveData:     CognitiveFailureData | null;
  twinData:          StrategicTwinProfile | null;
  sessionData:       SessionContextData | null;
  gtoQualityData:    GtoQualityData | undefined;
  gtoPositionData:   GtoPositionData | undefined;
  resultsVsGtoData:  ResultsVsGtoData | undefined;
  leakFinderData:    LeakFinderData | undefined;
  pendingGto:        number;
}

interface Opcoes {
  /** Free não vê insight avançado de IA — espelha o gate do backend. */
  isFree: boolean;
  /** `t` do namespace `common`, para os rótulos do ProLockCard. */
  tc: (k: string) => string;
}

export function makeRenderCard(d: DadosDoDashboard, { isFree, tc }: Opcoes) {
  // opts.v2: no V2 as narrativas de IA já vivem no carrossel (V2AiInsightsCard) — os cards
  // completos escondem o texto duplicado e mostram só o detalhe único.
  return (id: DashSection, opts?: { v2?: boolean }) => {
    const v2 = opts?.v2 ?? false;
    switch (id) {
      case "quality":    return <GtoQualityCard data={d.gtoQualityData} pendingGto={d.pendingGto} />;
      case "position":   return <GtoPositionCard data={d.gtoPositionData} pendingGto={d.pendingGto} />;
      case "leakfinder": return <LeakFinderCard data={d.leakFinderData} />;
      case "results":    return v2 ? <V2ResultsCard data={d.resultsVsGtoData} /> : <ResultsVsGtoCard data={d.resultsVsGtoData} />;
      // Único card que busca os próprios dados. Na demonstração recebe a série pronta, senão
      // renderizaria a evolução de quem está VISITANDO (deslogado: vazia).
      case "bankroll":   return <BankrollChart data={d.evo ?? undefined} />;
      case "career":     return isFree ? <ProLockCard feature={tc("proLock.career")} v2={v2} /> : <CareerGraphCard data={d.careerData ?? { insufficient_data: true, tournament_count: 0 }} hideNarrative={v2} v2={v2} />;
      case "cognitive":  return isFree
        ? <ProLockCard feature={tc("proLock.cognitive")} v2={v2} />
        : v2
          ? <V2CognitiveCard data={d.cognitiveData ?? { insufficient_data: true, patterns: [], total_decisions: 0 }} />
          : <CognitiveFailureCard data={d.cognitiveData ?? { insufficient_data: true, patterns: [], total_decisions: 0 }} />;
      case "session":    return isFree
        ? <ProLockCard feature={tc("proLock.session")} v2={v2} />
        : <SessionContextCard data={d.sessionData ?? { insufficient_data: true, sample: 0, multitabling: [], time_of_day: [], fatigue: [] }} />;
      case "dna":        return <PlayerDnaCard data={d.dnaData} v2={v2} />;
      case "pressure":   return v2 ? <V2PressureCard data={d.pressureData} /> : <PressureProfileCard data={d.pressureData} />;
      case "leaks":      return <LeaksPanel leaks={d.leakRoi.length > 0 ? d.leakRoi : d.evo?.leaks} source={d.leakRoi.length > 0 ? d.leakSource : null} />;
      case "causal_map": return isFree
        ? <ProLockCard feature={tc("proLock.causalMap")} v2={v2} />
        : (d.leakGraph && d.leakGraph.nodes.length >= 1)
          ? v2
            ? <V2CausalMapCard nodes={d.leakGraph.nodes} edges={d.leakGraph.edges} />
            : <LeakCausalMap nodes={d.leakGraph.nodes} edges={d.leakGraph.edges} narrative={d.leakGraph.narrative} />
          : null;
      case "twin":       return isFree
        ? <ProLockCard feature={tc("proLock.twin")} v2={v2} />
        : v2
          ? <V2TwinCard data={d.twinData ?? { insufficient_data: true, total_decisions: 0 }} />
          : <StrategicTwinCard data={d.twinData ?? { insufficient_data: true, total_decisions: 0 }} />;
      default:           return null;
    }
  };
}
