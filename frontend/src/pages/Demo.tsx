import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronRight, Compass, Loader2, Eye } from "lucide-react";
import { DashboardV2 } from "@/components/hud/DashboardV2";
import { makeRenderCard } from "@/components/hud/dashboardCards";
import { GuidedTour, type TourStep } from "@/components/hud/GuidedTour";
import { sample, type DashboardDemo } from "@/lib/api";

/**
 * Dashboard de DEMONSTRAÇÃO, público e sem login.
 *
 * Por que existe: o produto só diz algo depois do primeiro upload, e antes disso o dashboard é
 * vazio por construção. Quem chega da divulgação não tem como ver o que a ferramenta entrega —
 * e um tour guiado sobre a tela vazia apontaria para cards sem número, o que ensina que o
 * produto é vazio.
 *
 * Por que rota separada, e não dados de exemplo injetados no dashboard do jogador: injetar cria
 * um estado em que a tela mente sobre de quem é aquele ROI. Rota própria elimina a classe
 * inteira de bug.
 *
 * Os cards são os MESMOS do dashboard real (`DashboardV2` + `makeRenderCard`), não uma cópia:
 * cópia de vitrine passa a mentir sozinha no dia em que um card muda, sem quebrar nada.
 */
export default function Demo() {
  const { t } = useTranslation("dashboard");
  const { t: tc } = useTranslation("common");
  const [dados, setDados] = useState<DashboardDemo | null>(null);
  const [falhou, setFalhou] = useState(false);
  const [tourAberto, setTourAberto] = useState(false);

  useEffect(() => {
    let vivo = true;
    sample.dashboard()
      .then((d) => { if (vivo) setDados(d); })
      .catch(() => { if (vivo) setFalhou(true); });
    return () => { vivo = false; };
  }, []);

  if (falhou) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <p className="text-sm text-muted-foreground">{t("demo.indisponivel")}</p>
        <Link to="/" className="font-mono text-xs uppercase tracking-widest-2 text-primary hover:underline">
          {t("demo.voltar")}
        </Link>
      </div>
    );
  }

  if (!dados) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
      </div>
    );
  }

  const passos: TourStep[] = [
    { target: "proximo-passo", code: t("tour.p1code"), title: t("tour.p1title"), description: t("tour.p1desc") },
    { target: "hero",          code: t("tour.p2code"), title: t("tour.p2title"), description: t("tour.p2desc") },
    { target: "kpis",          code: t("tour.p3code"), title: t("tour.p3title"), description: t("tour.p3desc") },
    { target: "leaks",         code: t("tour.p4code"), title: t("tour.p4title"), description: t("tour.p4desc") },
    { target: "qualidade",     code: t("tour.p5code"), title: t("tour.p5title"), description: t("tour.p5desc") },
    { target: "treino",        code: t("tour.p6code"), title: t("tour.p6title"), description: t("tour.p6desc") },
  ];

  const tors = dados.tournaments.tournaments;
  const avaliados = tors.filter((x) => (x.buy_in ?? 0) > 0);
  const investido = avaliados.reduce((s, x) => s + (x.buy_in ?? 0), 0);
  const lucro = avaliados.reduce((s, x) => s + (x.profit ?? 0), 0);
  const itm = tors.filter((x) => (x.profit ?? 0) > 0).length;

  const renderCard = makeRenderCard({
    evo:              dados.evolution,
    leakRoi:          dados.leakRoi.leaks,
    leakSource:       dados.leakRoi.source,
    pressureData:     dados.pressureProfile,
    dnaData:          dados.dna,
    leakGraph:        dados.leakGraph,
    careerData:       dados.career,
    cognitiveData:    dados.cognitiveFailures,
    twinData:         dados.strategicTwin,
    sessionData:      dados.sessionContext,
    gtoQualityData:   dados.gtoQuality,
    gtoPositionData:  dados.gtoPosition,
    resultsVsGtoData: dados.resultsVsGto,
    leakFinderData:   dados.leakFinder,
    pendingGto:       0,   // demonstração nunca fica "processando"
  }, { isFree: false, tc });   // a demonstração mostra o produto COMPLETO, incl. os cards Pro

  return (
    <div className="relative">
      {/* Selo PERMANENTE, não só no topo: quem cai no meio da página por link direto ou scroll
          precisa saber de que tela se trata. Confundir isto com o próprio dado seria o pior
          desfecho possível. */}
      <div className="fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-3 border-b border-primary/30 bg-primary/10 px-4 py-2 backdrop-blur-md">
        <Eye className="size-3.5 shrink-0 text-primary" aria-hidden />
        <span className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
          {t("demo.selo")}
        </span>
        <span className="hidden text-xs text-muted-foreground sm:inline">{t("demo.explicacao")}</span>
        <button
          type="button"
          onClick={() => setTourAberto(true)}
          className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-md border border-primary/40 px-3 py-1 font-mono text-[10px] uppercase tracking-widest-2 text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
        >
          <Compass className="size-3" aria-hidden />
          {t("tour.botao")}
        </button>
        <Link
          to="/login"
          className="inline-flex shrink-0 items-center gap-1 rounded-md bg-primary px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary-foreground transition-colors hover:bg-primary-glow"
        >
          {t("demo.cta")} <ChevronRight className="size-3" aria-hidden />
        </Link>
      </div>

      <div className="pt-10">
        <DashboardV2
          onUpload={() => {}}
          evSummary={dados.evSummary}
          hasData
          renderCard={renderCard}
          gtoQuality={dados.gtoQuality}
          gtoPosition={dados.gtoPosition}
          pendingGto={0}
          showEmpty={false}
          evolution={dados.evolution}
          kpis={{
            roi:          investido > 0 ? (lucro / investido) * 100 : null,
            itmPct:       tors.length > 0 ? (itm / tors.length) * 100 : null,
            totalEvents:  tors.length,
            totalHands:   tors.reduce((s, x) => s + (x.hands_count ?? 0), 0),
            roiLowSample: avaliados.length > 0 && avaliados.length < 30,
            netProfit:    lucro,
          }}
          playerStats={dados.playerStats}
          drift={null}
          aiLocked={false}
          aiInsights={[
            dados.strategicTwin?.narrative      && { key: "twin",      title: t("v2.aiTwin"),      text: dados.strategicTwin.narrative },
            dados.cognitiveFailures?.narrative  && { key: "cognitive", title: t("v2.aiCognitive"), text: dados.cognitiveFailures.narrative },
            dados.career?.narrative             && { key: "career",    title: t("v2.aiCareer"),    text: dados.career.narrative },
            dados.leakGraph?.narrative          && { key: "causal",    title: t("v2.aiCausal"),    text: dados.leakGraph.narrative },
          ].filter(Boolean) as { key: string; title: string; text: string }[]}
        />
      </div>

      <GuidedTour steps={passos} open={tourAberto} onClose={() => setTourAberto(false)} />
    </div>
  );
}
