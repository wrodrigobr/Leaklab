import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft, GraduationCap, PenLine, X, Check, Trash2, LayoutGrid, FlaskConical, Clock, Eye, EyeOff, Info, Maximize2, Minimize2, Lock, Users, RotateCw, Sparkles, Filter } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import { useMutation } from "@tanstack/react-query";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
import { CompartilharMao } from "@/components/hud/CompartilharMao";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { useTableOrientation } from "@/hooks/use-table-orientation";
import { useIsLandscapeMobile } from "@/hooks/use-is-landscape-mobile";
import { RangePanel } from "@/components/replayer/RangePanel";
import { GtoStrategyPanel } from "@/components/replayer/GtoStrategyPanel";
import { DecisionCard, type DecisionSourceVariant } from "@/components/replayer/DecisionCard";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { SidePanels } from "@/components/replayer/SidePanels";
import { parseCard, parseCards, fmtAction } from "@/components/replayer/replayerFormat";
import { cn } from "@/lib/utils";
import { computeEffectiveGtoLabel } from "@/lib/gtoUtils";
import { livePlayers as computeLivePlayers, isMultiwayPot, isPpMuted, idealActionSource, verdictStrategy, verdictLevel, clampVerdict, type VerdictLevel } from "@/lib/cardLogic";
import { filterHandIds, parseResultFilter, type HandResultFilter } from "@/lib/handFilter";
import { selectWhy } from "@/lib/replayWhy";

import { VerdictPill } from "@/components/replayer/VerdictPill";
import { ACTION_COLORS } from "@/lib/actionColors";
import { tournaments as tournamentsApi, coachDashboard, metrics, ReplayData, ReplayStep, TournamentDecision, CoachAnnotation, CoachOverrideLabel, type CoachReplayHand } from "@/lib/api";


function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function anonymizeDesc(desc: string, aliases: Record<string, string>): string {
  let result = desc;
  for (const [name, alias] of Object.entries(aliases)) {
    if (name !== alias) result = result.replace(new RegExp(escapeRegex(name), "g"), alias);
  }
  return result;
}

// ── Replayer ──────────────────────────────────────────────────────────────────

// Module-scoped cache de replays (sobrevive re-renders). Chave: `t|h|student?`.
// TTL 5 min — alinhado com backend cache. Permite prefetch da próxima mão em
// background pra navegação fluida durante review de torneio.
type ReplayCacheEntry = { ts: number; data: ReplayData };
const REPLAY_CACHE = new Map<string, ReplayCacheEntry>();
const REPLAY_CACHE_TTL = 5 * 60 * 1000;
const REPLAY_CACHE_MAX = 64;

function replayCacheKey(t: string, h: string, student: number | null): string {
  return `${t}|${h}|${student ?? ""}`;
}

function replayCacheGet(key: string): ReplayData | null {
  const e = REPLAY_CACHE.get(key);
  if (!e) return null;
  if (Date.now() - e.ts > REPLAY_CACHE_TTL) {
    REPLAY_CACHE.delete(key);
    return null;
  }
  return e.data;
}

function replayCacheSet(key: string, data: ReplayData) {
  if (REPLAY_CACHE.size >= REPLAY_CACHE_MAX) {
    // Evict mais antigo
    let oldestKey: string | null = null;
    let oldestTs = Infinity;
    REPLAY_CACHE.forEach((v, k) => { if (v.ts < oldestTs) { oldestTs = v.ts; oldestKey = k; } });
    if (oldestKey) REPLAY_CACHE.delete(oldestKey);
  }
  REPLAY_CACHE.set(key, { ts: Date.now(), data });
}

const Replayer = () => {
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t } = useTranslation("replayer");
  const tableOrientation = useTableOrientation();
  const landscapeMobile = useIsLandscapeMobile();
  // Celular (qualquer orientação, <1024) usa SEMPRE o modo landscape fullscreen da mesa;
  // em pé mostramos um prompt pedindo pra girar (a mesa é mais agradável deitada).
  const mobileReplayer = landscapeMobile || tableOrientation === "portrait";
  const tournamentId = params.get("t") ?? "";
  const handId       = params.get("h") ?? "";
  const studentId    = params.get("student") ? Number(params.get("student")) : null;
  // Modo coach (toggle on/off no próprio Replayer, persistido): filtra a navegação só pras mãos
  // que valem revisão (pula fold pré-flop correto) e mostra o comentário do coach por mão. Pode
  // vir ligado pela URL (?coach=1, usado pelo botão "Revisar com o coach" do torneio).
  const coachParam   = params.get("coach") === "1" || params.get("walk") === "1";
  // Filtro herdado da LISTA de mãos (&f=error/attention/...): a navegação percorre SÓ as mãos
  // que passam nele — avançar pula as demais (ex.: filtrou "erros" → vai direto pro próximo erro).
  // A regra de classificação é a MESMA da lista (lib/handFilter), nunca reimplementada aqui.
  const resultFilter = parseResultFilter(params.get("f"));
  const [coachMode, setCoachMode] = useState<boolean>(
    () => coachParam || localStorage.getItem("replayer_coach") === "true");
  const [walkMap, setWalkMap] = useState<Record<string, CoachReplayHand>>({});
  // Playlist do coach NA ORDEM (walkMap é Record, não guarda ordem). Fonte da navegação em
  // modo coach; o efeito de interseção abaixo a combina com o &f= da URL.
  const [coachIds, setCoachIds] = useState<string[]>([]);
  const toggleCoach = () => setCoachMode((v) => {
    const nv = !v;
    localStorage.setItem("replayer_coach", String(nv));
    return nv;
  });

  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [stepIdx, setStepIdx]       = useState(0);
  const [playing, setPlaying]       = useState(false);
  const [speed, setSpeed]           = useState(1);
  const [handList, setHandList]     = useState<string[]>([]);
  const [betUnit, setBetUnit]       = useState<"chips" | "bb">("bb");
  const [showAnalysis, setShowAnalysis] = useState(false);   // mobile: bottom-sheet do card de análise
  const [showHud, setShowHud]       = useState<boolean>(
    () => localStorage.getItem('replayer_show_hud') !== 'false'   // HUD HM-style: ligado por padrão
  );
  // Tooltip completo do HUD (hover) por jogador — todas as stats rotuladas. Termos de
  // poker (VPIP/PFR/3-bet/c-bet/AF/WTSD) não se traduzem; só os conectivos são i18n.
  const hudTips = useMemo<Record<string, string>>(() => {
    const profs = replayData?.opponent_profiles ?? {};
    const reveals = replayData?.villain_reveals ?? {};
    const pp = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);
    // "Mostrou: Qc6c (#123456) · AhKd (#654321)" — mão revelada no SUMMARY é FATO, não read
    // inferido, por isso entra sem gate de amostra. O backend já exclui a mão atual (spoiler).
    const shownLine = (name: string) => {
      const rv = reveals[name];
      if (!rv?.length) return "";
      const itens = rv.map((r) => `${r.cards.join("")} (#${r.hand})`).join(" · ");
      return `\n${t("hudShowed")}: ${itens}`;
    };
    const out: Record<string, string> = {};
    for (const [name, p] of Object.entries(profs)) {
      const s = p.stats ?? {};
      const af = s.af == null ? "–" : (typeof s.af === "number" ? s.af.toFixed(1) : String(s.af));
      const low = p.confidence === "insufficient" || p.archetype === "unknown";
      const arch = low ? t("card.villainSampleLow") : t(`card.archetype.${p.archetype}`, p.archetype);
      // significado do arquétipo (o que é + como explorar) — pra quem não sabe o que é "Nit"/"LAG" etc.
      const hint = low ? "" : t(`card.archetypeHint.${p.archetype}`, { defaultValue: "" });
      out[name] =
        `${name} · ${arch} · ${p.hands} ${t("hudHands")}\n` +
        (hint ? `${hint}\n` : "") +
        `VPIP ${pp(s.vpip_pct)}   PFR ${pp(s.pfr_pct)}   3-bet ${pp(s.threebet_pct)}\n` +
        `c-bet ${pp(s.cbet_pct)}   fold→c-bet ${pp(s.foldcbet_pct)}\n` +
        `AF ${af}   WTSD ${pp(s.wtsd_pct)}` +
        shownLine(name);
    }
    return out;
  }, [replayData?.opponent_profiles, replayData?.villain_reveals, t]);
  const [decisions, setDecisions]   = useState<TournamentDecision[]>([]);
  const [showRange, setShowRange]           = useState(false);
  const [annotating, setAnnotating]         = useState(false);
  const [annComment, setAnnComment]         = useState("");
  const [annMode, setAnnMode]               = useState<"complement" | "replace">("complement");
  const [annAction, setAnnAction]           = useState("");
  const [annOverride, setAnnOverride]       = useState<CoachOverrideLabel>(null);
  const [gtoRequestStatus, setGtoRequestStatus] = useState<"idle" | "requesting" | "queued" | "solver_queued" | "done" | "error" | "quota_exceeded">("idle");
  // Track which hand_id we already auto-requested so we don't spam on step navigation
  const gtoAutoRequestedRef = useRef<string | null>(null);

  // Modo foco / tela cheia (#replayer) — coach revisa o torneio sem o chrome do app.
  // Mantém mesa, controles e o painel de decisão; some o HudHeader (nav/upload/etc).
  const rootRef = useRef<HTMLDivElement>(null);
  const [focusMode, setFocusMode] = useState(false);
  const enterFocus = () => {
    setFocusMode(true);
    rootRef.current?.requestFullscreen?.().catch(() => {}); // degrada p/ modo foco CSS se negado
  };
  const exitFocus = () => {
    setFocusMode(false);
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  };
  // Sai do modo foco quando o usuário deixa o fullscreen nativo (ex.: tecla ESC).
  useEffect(() => {
    const onFsChange = () => { if (!document.fullscreenElement) setFocusMode(false); };
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  // Celular: entra em tela cheia + trava em landscape NO TOQUE (a Fullscreen API exige gesto do
  // usuário; não dá auto). Android Chrome esconde a barra do navegador e auto-rotaciona. iOS Safari
  // (iPhone) NÃO suporta requestFullscreen — a Apple não deixa ocultar a barra via JS; lá degrada
  // pro prompt manual de girar (o h-dvh já usa o espaço que sobra).
  const canFullscreen = typeof document !== "undefined" && !!document.documentElement.requestFullscreen;
  // iOS Safari não suporta Fullscreen API, mas em modo standalone (PWA "Adicionar à Tela de Início")
  // a barra some. Detecta se já está instalado p/ não mostrar o hint à toa.
  const isStandalone = typeof window !== "undefined" &&
    (window.matchMedia?.("(display-mode: standalone)").matches === true ||
     (window.navigator as unknown as { standalone?: boolean }).standalone === true);
  const goImmersive = async () => {
    try {
      await document.documentElement.requestFullscreen?.();
      await (screen.orientation as unknown as { lock?: (o: string) => Promise<void> })?.lock?.("landscape");
    } catch { /* negado/sem suporte → segue no prompt manual */ }
  };

  // Floating Range panel drag state
  const [rangePos, setRangePos]         = useState({ x: 24, y: 96 });
  const isDraggingRange                 = useRef(false);
  const rangeDragStart                  = useRef({ mouseX: 0, mouseY: 0, panelX: 0, panelY: 0 });

  useEffect(() => {
    if (!tournamentId || !handId) return;
    setError("");
    setStepIdx(0);
    setPlaying(false);
    setGtoRequestStatus("idle");

    // Cache hit local: zero latência percebida
    const cacheKey = replayCacheKey(tournamentId, handId, studentId);
    const cached = replayCacheGet(cacheKey);
    if (cached) {
      setReplayData(cached);
      setLoading(false);
      // Ainda precisa do tournament data se nao tem (primeiro load)
      if (handList.length === 0) {
        const tournamentFn = studentId
          ? coachDashboard.studentTournament(studentId, tournamentId)
              .then((r) => ({ decisions: r.decisions }))
              .catch(() => null)
          : tournamentsApi.get(tournamentId).catch(() => null);
        tournamentFn.then((tournamentData) => {
          if (tournamentData) {
            // filterHandIds respeita o &f= da URL (all → todas, em ordem cronológica)
            const ids = filterHandIds(tournamentData.decisions, resultFilter);
            if (!coachMode) setHandList(ids);   // no modo coach a playlist filtrada manda na navegação
            setDecisions(tournamentData.decisions);
          }
        });
      }
      return;
    }

    setLoading(true);
    const replayFn = studentId
      ? coachDashboard.studentReplay(studentId, tournamentId, handId)
      : tournamentsApi.replay(tournamentId, handId);

    const tournamentFn = studentId
      ? coachDashboard.studentTournament(studentId, tournamentId)
          .then((r) => ({ decisions: r.decisions }))
          .catch(() => null)
      : tournamentsApi.get(tournamentId).catch(() => null);

    Promise.all([replayFn, tournamentFn])
      .then(([replay, tournamentData]) => {
        setReplayData(replay);
        replayCacheSet(cacheKey, replay);
        if (tournamentData) {
          const ids = filterHandIds(tournamentData.decisions, resultFilter);
          if (!coachMode) setHandList(ids);   // no modo coach a playlist filtrada manda na navegação
          setDecisions(tournamentData.decisions);
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar replay"))
      .finally(() => setLoading(false));
  }, [tournamentId, handId, studentId, coachMode]);

  // Modo coach LIGADO: carrega a playlist da sessão (mãos que valem revisão, em ordem). Keyed no
  // torneio (não na mão) → estável ao avançar. Se a mão atual ficou de fora da playlist (ex.:
  // entrou por um fold pré-flop), salta pra primeira mão que vale.
  useEffect(() => {
    if (!coachMode || !tournamentId) return;
    let alive = true;
    metrics.coachReplay(tournamentId).then((d) => {
      if (!alive || !d?.hands?.length) return;
      const ids = d.hands.map((h) => h.hand_id);
      setCoachIds(ids);
      const m: Record<string, CoachReplayHand> = {};
      d.hands.forEach((h) => { m[h.hand_id] = h; });
      setWalkMap(m);
      if (handId && !m[handId]) {
        navigate(`/replayer?t=${tournamentId}&h=${ids[0]}${studentId ? `&student=${studentId}` : ""}&coach=1`,
          { replace: true });
      }
    }).catch(() => {});
    return () => { alive = false; };
  }, [coachMode, tournamentId]);

  // A navegação em modo coach: a playlist dá a ORDEM, mas o &f= da URL segue valendo — a
  // INTERSEÇÃO dos dois. Antes a playlist substituía o filtro calada: usuário filtrava "só os
  // erros" na lista, abria com coach=1, e o avançar pousava em mão Aceitável que a lista não
  // mostra (mão 259090517149, reportado em 14/08) — com a barra ainda rotulada "só os erros"
  // (o "3/84" do primeiro print era o TAMANHO DA PLAYLIST, não a contagem de erros).
  // Fallback para a playlist inteira se a interseção esvaziar — navegação nunca morre.
  useEffect(() => {
    if (!coachMode || !coachIds.length) return;
    if (resultFilter === "all" || !decisions.length) { setHandList(coachIds); return; }
    const passa = new Set(filterHandIds(decisions, resultFilter));
    const ids = coachIds.filter((h) => passa.has(h));
    setHandList(ids.length ? ids : coachIds);
  }, [coachMode, coachIds, decisions, resultFilter]);

  // Modo coach DESLIGADO: restaura a lista completa do torneio (todas as mãos) a partir das decisões.
  useEffect(() => {
    if (coachMode) return;
    setWalkMap({});
    setCoachIds([]);
    if (decisions.length) setHandList(filterHandIds(decisions, resultFilter));
  }, [coachMode, decisions, resultFilter]);

  // Prefetch em background: prioriza ADIANTE (o usuário avança) — as próximas PREFETCH_AHEAD mãos +
  // a anterior. Conforme avança, o useEffect re-dispara (handId muda) e a janela desliza, mantendo
  // sempre N mãos à frente no cache → sem "carregando" ao avançar. Cada uma só se não estiver cacheada.
  useEffect(() => {
    if (!tournamentId || handList.length === 0) return;
    const idx = handList.indexOf(handId);
    if (idx < 0) return;
    const PREFETCH_AHEAD = 3;
    const toPrefetch: string[] = [];
    for (let k = 1; k <= PREFETCH_AHEAD; k++) {
      if (idx + k < handList.length) toPrefetch.push(handList[idx + k]);
    }
    if (idx - 1 >= 0) toPrefetch.push(handList[idx - 1]);
    toPrefetch.forEach((h) => {
      const k = replayCacheKey(tournamentId, h, studentId);
      if (replayCacheGet(k)) return;
      const fn = studentId
        ? coachDashboard.studentReplay(studentId, tournamentId, h)
        : tournamentsApi.replay(tournamentId, h);
      fn.then((replay) => replayCacheSet(k, replay)).catch(() => {});
    });
  }, [tournamentId, handId, studentId, handList]);

  const steps = replayData?.timeline ?? [];
  const step  = steps[stepIdx] as ReplayStep | undefined;

  // Hand navigation — handList já vem filtrado (&f=), então avançar pula o que não passa.
  const handIdx  = handList.indexOf(handId);
  let prevHand = handIdx > 0 ? handList[handIdx - 1] : null;
  let nextHand = handIdx >= 0 && handIdx < handList.length - 1 ? handList[handIdx + 1] : null;
  // Mão atual FORA do filtro (ex.: URL montada à mão): sem isso o prev/next morria (idx -1).
  // Navega pela vizinhança CRONOLÓGICA — a mão filtrada mais próxima antes/depois desta.
  if (handIdx < 0 && handList.length && decisions.length) {
    const seenAll = new Set<string>();
    const allIds: string[] = [];
    decisions.forEach((d) => {
      if (d.hand_id && !seenAll.has(d.hand_id)) { seenAll.add(d.hand_id); allIds.push(d.hand_id); }
    });
    const pos = allIds.indexOf(handId);
    if (pos >= 0) {
      const inFilter = new Set(handList);
      for (let i = pos - 1; i >= 0; i--) if (inFilter.has(allIds[i])) { prevHand = allIds[i]; break; }
      for (let i = pos + 1; i < allIds.length; i++) if (inFilter.has(allIds[i])) { nextHand = allIds[i]; break; }
    }
  }
  // URL de outra mão do MESMO contexto (preserva coach-student e o modo walkthrough).
  const handHref = (h: string) =>
    `/replayer?t=${tournamentId}&h=${h}${studentId ? `&student=${studentId}` : ""}${coachMode ? "&coach=1" : ""}`
    + (resultFilter !== "all" ? `&f=${resultFilter}` : "");
  const walkCurrent = coachMode ? walkMap[handId] : undefined;

  // "Voltar" = LISTA DE MÃOS do torneio (/tournaments/:id), não a mão anterior do histórico do browser
  // (navegar entre mãos não deveria empilhar; o voltar leva de volta ao torneio). Coach (student) ou
  // sem torneio → fallback no voltar do browser.
  const goBack = () => {
    if (tournamentId && !studentId) navigate(`/tournaments/${tournamentId}`);
    else navigate(-1);
  };

  // Alias map: todos os jogadores com nomes reais
  const playerAliases = useMemo<Record<string, string>>(() => {
    if (!replayData?.seats) return {};
    const aliases: Record<string, string> = {};
    Object.values(replayData.seats).forEach(({ player }) => {
      aliases[player] = player;
    });
    return aliases;
  }, [replayData]);

  // Cartas reveladas na mesa: mid-hand all-in shows + showdown
  // seat_str → cards (array vazio = muck, sem cartas exibidas)
  const revealedCards = useMemo<Record<string, string[]>>(() => {
    if (!step) return {};
    const rc: Record<string, string[]> = { ...(step.revealed_cards ?? {}) };
    if (step.type === "showdown" && step.summary?.seats) {
      for (const sd of step.summary.seats) {
        const seatKey = Object.keys(step.seats ?? {}).find(
          (k) => (step.seats as Record<string, { player: string }>)[k]?.player === sd.player
        );
        if (!seatKey) continue;
        if (sd.hand_desc === "mucked") {
          rc[seatKey] = [];         // muck: assento existe mas sem cartas
        } else if (sd.cards?.length >= 2) {
          rc[seatKey] = sd.cards;   // mostrou cartas
        }
      }
    }
    return rc;
  }, [step]);

  // Auto-play
  useEffect(() => {
    if (!playing || !step) return;
    const t = setTimeout(() => {
      setStepIdx((i) => {
        if (i < steps.length - 1) return i + 1;
        setPlaying(false);
        return i;
      });
    }, 1600 / speed);
    return () => clearTimeout(t);
  }, [playing, stepIdx, speed, steps.length, step]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.code === "ArrowRight") setStepIdx((i) => Math.min(steps.length - 1, i + 1));
      if (e.code === "ArrowLeft")  setStepIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [steps.length]);

  // Draggable Range panel
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDraggingRange.current) return;
      setRangePos({
        x: rangeDragStart.current.panelX + (e.clientX - rangeDragStart.current.mouseX),
        y: rangeDragStart.current.panelY + (e.clientY - rangeDragStart.current.mouseY),
      });
    };
    const onUp = () => { isDraggingRange.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const handleRangeDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    isDraggingRange.current = true;
    rangeDragStart.current = { mouseX: e.clientX, mouseY: e.clientY, panelX: rangePos.x, panelY: rangePos.y };
  };

  // Reset annotation form when step changes
  useEffect(() => { setAnnotating(false); }, [stepIdx]);

  // Coach annotation for current step — must be before early returns (Rules of Hooks)
  const coachAnnotation = useMemo(() => {
    const annotations = replayData?.coach_annotations;
    // Anotações disponíveis em QUALQUER spot do hero — não só nos erros. O coach
    // pode comentar uma jogada correta/marginal também (reforço, contexto, leak fino).
    if (!annotations) return null;
    return Object.values(annotations).find(
      (a) => a.street === step?.street && a.action_taken === step?.action
    ) ?? null;
  }, [replayData?.coach_annotations, step?.street, step?.action]);

  // decision_id for annotation save/delete (coaches only) — todo spot do hero, não só erro
  const currentDecisionId = useMemo(() => {
    if (!studentId || !step?.is_hero) return null;
    if (coachAnnotation) return coachAnnotation.decision_id;
    return decisions.find(
      (d) => d.hand_id === handId && d.street === step.street && d.action_taken === step.action
    )?.id ?? null;
  }, [studentId, step?.is_hero, step?.street, step?.action, coachAnnotation, decisions, handId]);

  const saveAnn = useMutation({
    mutationFn: () => coachDashboard.upsertAnnotation(studentId!, {
      decision_id: currentDecisionId!,
      comment: annComment,
      mode: annMode,
      coach_action: annAction || undefined,
      coach_override_label: annOverride,
    }),
    onSuccess: (saved: CoachAnnotation) => {
      // A resposta da API NÃO traz street/action_taken (são da tabela decisions, não da
      // anotação); o match do card é por (street, action). Sem isso, a anotação recém-salva
      // "sumia" até o refresh (que re-busca com esses campos). Injeta os do step atual.
      const enriched = { ...saved, street: step?.street, action_taken: step?.action };
      setReplayData((prev) => prev ? {
        ...prev,
        coach_annotations: { ...prev.coach_annotations, [String(saved.decision_id)]: enriched },
      } : prev);
      setAnnotating(false);
    },
  });

  const deleteAnn = useMutation({
    mutationFn: () => coachDashboard.deleteAnnotation(studentId!, currentDecisionId!),
    onSuccess: () => {
      setReplayData((prev) => {
        if (!prev || !currentDecisionId) return prev;
        const anns = { ...prev.coach_annotations };
        delete anns[String(currentDecisionId)];
        return { ...prev, coach_annotations: anns };
      });
      setAnnotating(false);
    },
  });

  const openAnnotationForm = () => {
    setAnnComment(coachAnnotation?.comment ?? "");
    setAnnMode(coachAnnotation?.mode ?? "complement");
    setAnnAction(coachAnnotation?.coach_action ?? "");
    setAnnOverride(coachAnnotation?.coach_override_label ?? null);
    setAnnotating(true);
  };

  const handleRequestGto = async () => {
    if (!tournamentId || !handId) {
      console.warn("[GTO] handId ou tournamentId vazio", { tournamentId, handId });
      return;
    }
    console.log("[GTO] solicitando análise", { tournamentId, handId });
    setGtoRequestStatus("requesting");
    try {
      const res = await tournamentsApi.requestGtoAnalysis(tournamentId, handId);
      console.log("[GTO] resposta:", res);
      if (res.status === "done") {
        const replayFn = studentId
          ? coachDashboard.studentReplay(studentId, tournamentId, handId)
          : tournamentsApi.replay(tournamentId, handId);
        const fresh = await replayFn;
        setReplayData(fresh);
        setGtoRequestStatus("done");
      } else {
        setGtoRequestStatus("queued");
      }
    } catch (err) {
      console.error("[GTO] erro na solicitação:", err);
      // #26 — cota de solves estourada (402) → upsell, não erro genérico
      if (err instanceof Error && err.message === "solve_quota_exceeded") {
        setGtoRequestStatus("quota_exceeded");
      } else {
        setGtoRequestStatus("error");
      }
    }
  };

  // Polling: enquanto status é "queued", verifica a cada 4s
  // Quando "done" ou "solver_queued", recarrega o replay
  useEffect(() => {
    if (gtoRequestStatus !== "queued") return;
    if (!tournamentId || !handId) return;

    const poll = setInterval(async () => {
      try {
        const s = await tournamentsApi.getGtoRequestStatus(handId);
        if (s.status === "done" || s.status === "solver_queued") {
          clearInterval(poll);
          const replayFn = studentId
            ? coachDashboard.studentReplay(studentId, tournamentId, handId)
            : tournamentsApi.replay(tournamentId, handId);
          const fresh = await replayFn;
          setReplayData(fresh);
          setGtoRequestStatus(s.status === "solver_queued" ? "solver_queued" : "done");
        } else if (s.status === "error") {
          clearInterval(poll);
          setGtoRequestStatus("error");
        }
      } catch {
        // ignora erros transitórios de rede
      }
    }, 4000);

    return () => clearInterval(poll);
  }, [gtoRequestStatus, tournamentId, handId, studentId]);

  // Auto-request GTO when navigating to a postflop hero step without GTO data
  useEffect(() => {
    if (!replayData || !handId) return;
    const steps = replayData.timeline ?? [];
    // Só auto-solva spots SOLVÁVEIS sem nó ainda ('pending'). Multiway, deep>60bb,
    // hero IP enfrentando aposta e sem-vilão são heurísticos por design (o solver é
    // heads-up) — nunca terão cobertura, então não dispara requisição inútil.
    const hasPostflopHeroNoGto = steps.some(s => {
      const cov = (s as { gto_coverage?: string }).gto_coverage;
      return s.is_hero && s.type === "action" && s.street !== "preflop" && !s.gto_label &&
        s.action !== "shows" && s.action !== "mucks" &&
        (cov === "pending" || cov === undefined);
    });
    if (!hasPostflopHeroNoGto) return;
    if (gtoAutoRequestedRef.current === handId) return;
    if (gtoRequestStatus !== "idle") return;
    gtoAutoRequestedRef.current = handId;
    handleRequestGto();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replayData, handId]);

  // ── No params: show placeholder ──────────────────────────────────────────────
  if (!tournamentId || !handId) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("description")}>
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
          <p className="text-sm">{t("noParams")}</p>
          <button onClick={goBack} className="inline-flex items-center gap-2 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> {t("back")}
          </button>
        </div>
      </HudLayout>
    );
  }

  if (loading) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title={t("loading")} description="">
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">{t("loadingHand")}</span>
        </div>
      </HudLayout>
    );
  }

  if (error) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title={t("error")} description="">
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={goBack} className="inline-flex items-center gap-2 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> {t("back")}
          </button>
        </div>
      </HudLayout>
    );
  }

  if (!replayData || !step) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title="—" description="">
        <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">{t("noData")}</div>
      </HudLayout>
    );
  }

  const isError   = step.is_error ?? false;
  // 'shows'/'mucks'/'posts' NÃO são decisões — nunca recebem veredito (mesmo guard do card em :186).
  // Sem isto o show do showdown (ação já realizada) ganhava badge "Correto" via VerdictPill.
  const _nonDecisionAction = ["shows", "show", "mucks", "muck", "posts", "post"]
    .includes((step.action ?? "").toLowerCase());
  const isCorrect = step.is_hero && !isError && step.type === "action" && !_nonDecisionAction;

  // ── Celular DEITADO: mesa FULLSCREEN edge-to-edge + controles/logo/pill flutuando ──
  if (mobileReplayer) {
    // Celular em PÉ: a mesa só roda em landscape → pede pra girar o aparelho.
    if (tableOrientation === "portrait") {
      return (
        <div className="h-dvh flex flex-col items-center justify-center gap-5 bg-background hud-scanline px-10 text-center"
          style={{ background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)" }}>
          <RotateCw className="size-14 text-primary" />
          <p className="font-mono text-[13px] uppercase tracking-widest text-muted-foreground leading-relaxed">{t("rotatePrompt")}</p>
          {canFullscreen && (
            <button onClick={goImmersive}
              className="flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 font-mono text-[12px] font-bold uppercase tracking-widest text-primary-foreground shadow-lg transition-transform active:scale-95">
              <Maximize2 className="size-4" /> {t("fullscreenRotate")}
            </button>
          )}
          {/* iPhone: sem Fullscreen API → dica de instalar como PWA p/ tela cheia (sem barra). */}
          {!canFullscreen && !isStandalone && (
            <p className="max-w-[280px] rounded-xl bg-primary/10 px-4 py-2.5 font-mono text-[10px] leading-relaxed text-primary/90 ring-1 ring-primary/20">
              {t("iosInstallHint")}
            </p>
          )}
          <button onClick={goBack}
            className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70 transition-colors hover:text-primary">{t("back")}</button>
        </div>
      );
    }
    return (
      <div ref={rootRef} className="h-dvh relative overflow-hidden hud-scanline"
        style={{ background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)" }}>
        {/* Mesa (dimensões boas, height-bound, sem cortar pods) com fundo TRANSPARENTE: o
            gradiente acima é único na tela → sem caixa/borda dando impressão de sobreposição. */}
        <div className="absolute inset-0 flex items-center justify-center p-0.5">
          <div className="h-full w-auto max-w-full mx-auto" style={{ aspectRatio: "1160 / 710" }}>
            <PokerTableV3
              step={step} hero={replayData.hero} heroCards={replayData.hero_cards}
              bb={replayData.bb} betUnit={betUnit} playerAliases={playerAliases}
              revealedCards={revealedCards} profiles={replayData.opponent_profiles}
              showHud={showHud} hudTips={hudTips} orientation="landscape" fill
            />
          </div>
        </div>

        {/* Voltar — topo-esquerda */}
        <button onClick={goBack}
          className="absolute top-[calc(0.5rem+env(safe-area-inset-top))] left-[calc(0.5rem+env(safe-area-inset-left))] z-30 inline-flex items-center gap-1.5 rounded-full bg-background/70 backdrop-blur px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground ring-1 ring-border transition-colors hover:text-primary">
          <ArrowLeft className="size-3.5" /> {t("back")}
        </button>

        {/* Logo GrindLab + contador de mão — topo-direita */}
        <div className="absolute top-[calc(0.5rem+env(safe-area-inset-top))] right-[calc(0.5rem+env(safe-area-inset-right))] z-30 flex items-center gap-2.5 rounded-full bg-background/70 backdrop-blur px-3 py-1.5 ring-1 ring-border">
          {handList.length > 1 && handIdx >= 0 && (
            <span className="font-mono text-[10px] text-muted-foreground tabular-nums">{handIdx + 1}/{handList.length}</span>
          )}
          <img src={logoHorizontal} alt="GrindLab" className="h-5 w-auto" />
        </div>

        {/* Verdict pill / Análise — canto inferior-direito */}
        <div className="absolute bottom-[calc(0.5rem+env(safe-area-inset-bottom))] right-[calc(0.5rem+env(safe-area-inset-right))] z-30">
          <VerdictPill
            level={step.multiway_advice ? null : clampVerdict(verdictLevel(step.error_label) ?? (step.is_hero && step.type === "action" ? ((isError ? "error" : isCorrect ? "correct" : null) as VerdictLevel | null) : null), step.gto_action, step.action, step.gto_label,
                    step.preflop_gto?.hand_freq?.fold)}
            evLossBb={step.ev_loss_bb}
            onClick={() => setShowAnalysis(true)}
          />
        </div>

        {/* Controles — extrema inferior-esquerda */}
        <div className="absolute bottom-[calc(0.5rem+env(safe-area-inset-bottom))] left-[calc(0.5rem+env(safe-area-inset-left))] z-30 flex items-center gap-1 rounded-full bg-background/80 backdrop-blur px-2 py-1 ring-1 ring-border shadow-lg">
          <button onClick={() => { if (stepIdx > 0) setStepIdx(0); else if (prevHand) navigate(handHref(prevHand), { replace: true }); }}
            disabled={stepIdx === 0 && !prevHand}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><Rewind className="size-4" /></button>
          <button onClick={() => setStepIdx((i) => Math.max(0, i - 1))} disabled={stepIdx === 0}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><ChevronLeft className="size-5" /></button>
          <button onClick={() => setPlaying((p) => !p)}
            className="inline-flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary-glow">
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />}</button>
          <button onClick={() => setStepIdx((i) => Math.min(steps.length - 1, i + 1))} disabled={stepIdx === steps.length - 1}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><ChevronRight className="size-5" /></button>
          <button onClick={() => { if (stepIdx < steps.length - 1) setStepIdx(steps.length - 1); else if (nextHand) navigate(handHref(nextHand), { replace: true }); }}
            disabled={stepIdx === steps.length - 1 && !nextHand}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><FastForward className="size-4" /></button>
          <span className="px-1.5 font-mono text-[10px] text-muted-foreground tabular-nums">{stepIdx + 1}/{steps.length}</span>
        </div>

        {/* Sheet de análise (on-demand, tap na pill) */}
        {showAnalysis && (
          <div className="fixed inset-0 z-50 flex flex-col justify-end">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowAnalysis(false)} />
            <div className="relative max-h-[90vh] overflow-y-auto rounded-t-2xl bg-background p-3 pb-[calc(1.5rem+env(safe-area-inset-bottom))] shadow-2xl ring-1 ring-border">
              <button onClick={() => setShowAnalysis(false)} aria-label={t("close")}
                className="absolute right-3 top-3 z-10 rounded-full bg-background/80 backdrop-blur p-1.5 text-muted-foreground ring-1 ring-border transition-colors hover:bg-secondary hover:text-foreground"><X className="size-4" /></button>
              <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" onClick={() => setShowAnalysis(false)} />
              <SidePanels
                step={step} isError={isError} isCorrect={isCorrect}
                coachAnnotation={coachAnnotation} studentId={studentId}
                currentDecisionId={currentDecisionId} annotating={annotating}
                annComment={annComment} annMode={annMode} annAction={annAction}
                annOverride={annOverride} saveAnn={saveAnn} deleteAnn={deleteAnn}
                replayData={replayData} playerAliases={playerAliases}
                setAnnotating={setAnnotating} setAnnComment={setAnnComment}
                setAnnMode={setAnnMode} setAnnAction={setAnnAction}
                setAnnOverride={setAnnOverride} openAnnotationForm={openAnnotationForm}
                t={t}
                gtoRequestStatus={gtoRequestStatus} onRequestGto={handleRequestGto}
                tournamentId={tournamentId} handId={handId}
                compact
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="h-dvh flex flex-col overflow-hidden bg-background hud-scanline">
      {!focusMode && <HudHeader />}

      {/* ── Outer wrapper: top-bar + [table | side-panel] + controls ── */}
      <div className={cn(
        "flex-1 min-h-0 flex flex-col px-3 md:px-5 pt-2 pb-20 md:pb-2 mx-auto w-full",
        focusMode ? "max-w-none" : "max-w-[1600px]",
      )}>

        {/* Top bar */}
        <div className="shrink-0 grid grid-cols-3 items-center mb-2">
          <div className="flex items-center gap-3 min-w-0">
            {/* Logo GrindLab — presença de marca no modo foco (HudHeader fica oculto) */}
            {focusMode && (
              <img src={logoHorizontal} alt="GrindLab" className="h-7 w-auto shrink-0" />
            )}
            <button
              onClick={goBack}
              className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
            >
              <ArrowLeft className="size-3.5" /> {t("back")}
            </button>
          </div>

          {handList.length > 1 && handIdx >= 0 ? (
            <div className="flex items-center justify-center gap-2.5">
              <div className="flex items-baseline gap-1 font-mono tabular-nums">
                <span className="text-[9px] uppercase tracking-widest text-muted-foreground">{t("navigation.handLabel")}</span>
                <span className="text-sm font-bold text-foreground">{handIdx + 1}</span>
                <span className="text-[11px] text-muted-foreground">/{handList.length}</span>
              </div>
              <div className="hidden sm:block h-1 w-28 overflow-hidden rounded-full bg-border">
                <div
                  className="h-full rounded-full bg-primary/70 transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(4, ((handIdx + 1) / handList.length) * 100)}%` }}
                />
              </div>
            </div>
          ) : <div />}

          <div className="flex items-center justify-end gap-2">
            {replayData?.is_pko && (
              <span
                className="inline-flex items-center rounded-md bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1 ring-amber-500/30 text-amber-300"
                title={t("pkoTooltip")}
              >
                PKO
              </span>
            )}
            {/* Compartilhar (29/08): a mao vira link publico com a pergunta do dono. */}
            {!studentId && tournamentId && handId && (
              <CompartilharMao tournamentId={tournamentId} handId={handId} stepIdx={stepIdx} />
            )}
            {/* Modo coach: pula os folds pré-flop óbvios e comenta cada mão que vale revisão. */}
            {!studentId && (
              <button
                onClick={toggleCoach}
                aria-pressed={coachMode}
                title={t(coachMode ? "coachModo.desligar" : "coachModo.ligar")}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  coachMode ? "bg-primary/15 text-primary ring-1 ring-primary/30"
                            : "text-muted-foreground hover:bg-secondary hover:text-foreground")}
              >
                <GraduationCap className="size-3.5" />
                <span className="hidden sm:inline">Coach</span>
              </button>
            )}
            <button
              onClick={focusMode ? exitFocus : enterFocus}
              aria-label={focusMode ? t("focus.exit") : t("focus.enter")}
              title={focusMode ? t("focus.exit") : t("focus.enter")}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {focusMode ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
              <span className="hidden sm:inline">{focusMode ? t("focus.exit") : t("focus.enter")}</span>
            </button>
          </div>
        </div>

        {/* ── Modo coach: comentário do coach pra mão atual (só nas mãos que valem revisão) ── */}
        {coachMode && walkCurrent && (
          <div className="shrink-0 mb-2 flex items-center gap-3 rounded-xl border border-primary/25 bg-primary/[0.06] px-4 py-2.5">
            <GraduationCap className="size-5 shrink-0 text-primary" aria-hidden />
            <p className="min-w-0 flex-1 truncate text-sm text-foreground">
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-primary">Coach</span>
              <span className="mx-2 text-muted-foreground">·</span>
              {walkCurrent.narration}
            </p>
            <span className={cn(
              "shrink-0 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1",
              walkCurrent.verdict === "error" ? "bg-red-500/10 text-red-400 ring-red-500/25"
              : walkCurrent.verdict === "acceptable" ? "bg-sky-500/10 text-sky-400 ring-sky-500/25"
              : "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20")}>
              {t(`veredito.${walkCurrent.verdict}`)}
              {walkCurrent.ev_loss_bb > 0 && ` · -${walkCurrent.ev_loss_bb}bb`}
            </span>
          </div>
        )}

        {/* ── Filtro herdado da lista: deixa EXPLÍCITO que a navegação pula mãos ──
            Sem isto o usuário avança e "some" mão do meio sem entender por quê. */}
        {resultFilter !== "all" && (
          <div className="shrink-0 mb-2 flex items-center gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-4 py-2">
            <Filter className="size-4 shrink-0 text-amber-400" aria-hidden />
            <p className="min-w-0 flex-1 text-sm text-foreground">
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-amber-400">
                {t("filterNav.label")}
              </span>
              <span className="mx-2 text-muted-foreground">·</span>
              {t(`filterNav.${resultFilter}`)}
              {handList.length > 0 && (
                <span className="ml-2 font-mono text-[11px] tabular-nums text-muted-foreground">
                  {handIdx >= 0 ? `${handIdx + 1}/${handList.length}` : `${handList.length}`}
                </span>
              )}
            </p>
            <button
              onClick={() => navigate(
                `/replayer?t=${tournamentId}&h=${handId}`
                + (studentId ? `&student=${studentId}` : "")
                + (coachMode ? "&coach=1" : ""))}
              className="shrink-0 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground ring-1 ring-border transition-colors hover:text-foreground hover:ring-amber-500/40"
            >
              {t("filterNav.showAll")}
            </button>
          </div>
        )}

        {/* ── Main row: table (flex-1) + side panel (w-72, desktop only) ── */}
        {/* Mobile: 3 faixas em h-dvh sem scroll (mesa flex-1); desktop: row de altura fixa */}
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-3">

          {/* Table column */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col gap-2">
            {/* Mesa — height-bound: cabe SEMPRE na faixa flex-1 (acima dos controles), nunca
                rola pra baixo do menu. Aspect fixo 16/10: só landscape chega aqui — portrait
                já retornou no ramo mobileReplayer, então o ternário por orientação era morto. */}
            <div className="relative flex-1 min-h-0 overflow-hidden flex items-center justify-center">
              <div
                className="h-full w-auto max-w-full max-h-full mx-auto"
                style={{ aspectRatio: "16 / 10" }}
              >
                <PokerTableV3
                  step={step}
                  hero={replayData.hero}
                  heroCards={replayData.hero_cards}
                  bb={replayData.bb}
                  betUnit={betUnit}
                  playerAliases={playerAliases}
                  revealedCards={revealedCards}
                  profiles={replayData.opponent_profiles}
                  showHud={showHud}
                  hudTips={hudTips}
                  orientation={tableOrientation}
                  transparentBg
                />
              </div>

              {/* Desktop: pill de veredito flutuando sobre a mesa (canto inferior-direito)
                  que abre o modal de análise sob demanda. Some quando não há veredito. */}
              <div className="hidden lg:block absolute bottom-3 right-3 z-30">
                <VerdictPill
                  desktop
                  level={step.multiway_advice ? null : clampVerdict(
                    verdictLevel(step.error_label)
                    ?? (step.is_hero && step.type === "action"
                          ? (isError ? "error" : isCorrect ? "correct" : null) as VerdictLevel | null
                          : null),
                    step.gto_action, step.action, step.gto_label,
                    step.preflop_gto?.hand_freq?.fold)
                  }
                  evLossBb={step.ev_loss_bb}
                  onClick={() => setShowAnalysis(true)}
                />
              </div>
            </div>

            {/* Mobile: barra de veredito (3 níveis, fonte única VERDICT_META) que abre o sheet de análise */}
            <VerdictPill
              level={step.multiway_advice ? null : clampVerdict(
                verdictLevel(step.error_label)
                ?? (step.is_hero && step.type === "action"
                      ? (isError ? "error" : isCorrect ? "correct" : null) as VerdictLevel | null
                      : null),
                step.gto_action, step.action, step.gto_label,
                    step.preflop_gto?.hand_freq?.fold)
              }
              evLossBb={step.ev_loss_bb}
              onClick={() => setShowAnalysis(true)}
            />

            {/* Controls */}
            <div className="shrink-0 border border-border rounded-xl bg-hud-surface p-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    if (stepIdx > 0) setStepIdx(0);
                    else if (prevHand) navigate(handHref(prevHand));
                  }}
                  disabled={stepIdx === 0 && !prevHand}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={stepIdx === 0 && prevHand ? t("navigation.prevHand") : "Reiniciar"}
                ><Rewind className="size-4" /></button>
                <button onClick={() => setStepIdx((i) => Math.max(0, i - 1))} disabled={stepIdx === 0}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Anterior"><ChevronLeft className="size-5" /></button>
                <button onClick={() => setPlaying((p) => !p)}
                  className="inline-flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={playing ? t("controls.pause") : t("controls.play")}>
                  {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
                </button>
                <button onClick={() => setStepIdx((i) => Math.min(steps.length - 1, i + 1))} disabled={stepIdx === steps.length - 1}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={t("proximo")}><ChevronRight className="size-5" /></button>
                <button
                  onClick={() => {
                    if (stepIdx < steps.length - 1) setStepIdx(steps.length - 1);
                    else if (nextHand) navigate(handHref(nextHand));
                  }}
                  disabled={stepIdx === steps.length - 1 && !nextHand}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={stepIdx === steps.length - 1 && nextHand ? t("navigation.nextHand") : "Final"}
                ><FastForward className="size-4" /></button>
              </div>

              <div className="flex flex-1 items-center gap-3">
                <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                  {stepIdx + 1}/{steps.length}
                </span>
                <div className="flex-1 flex gap-0.5">
                  {steps.map((s, i) => (
                    <button key={i} onClick={() => setStepIdx(i)}
                      className={cn(
                        "h-1.5 flex-1 rounded-sm transition-colors focus-visible:outline-none",
                        i <= stepIdx
                          ? (s.is_error ? "bg-destructive" : "bg-primary")
                          : "bg-border"
                      )}
                      aria-label={`Passo ${i + 1}`}
                    />
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowRange(s => !s)}
                  disabled={step.street !== 'preflop'}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider ring-1 transition-colors focus-visible:outline-none',
                    showRange && step.street === 'preflop'
                      ? 'bg-primary/15 text-primary ring-primary/30'
                      : step.street !== 'preflop'
                      ? 'cursor-not-allowed text-muted-foreground/30 ring-border/30'
                      : 'text-muted-foreground ring-border hover:text-foreground',
                  )}
                >
                  <LayoutGrid className="size-3" /> Range
                </button>
                <div className="flex items-center gap-1">
                  {[0.5, 1, 2].map((s) => (
                    <button key={s} onClick={() => setSpeed(s)}
                      className={cn(
                        "rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                        speed === s ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:text-foreground"
                      )}>{s}x</button>
                  ))}
                </div>
                <div className="flex items-center rounded-sm ring-1 ring-border overflow-hidden">
                  {(["chips", "bb"] as const).map((u) => (
                    <button key={u} onClick={() => setBetUnit(u)}
                      className={cn(
                        "px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                        betUnit === u ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                      )}>{u}</button>
                  ))}
                </div>
                {/* HUD HM-style: liga/desliga os boxes de stats dos vilões na mesa.
                    Só aparece quando há perfis (torneio com nomes reais rastreados). */}
                {replayData.opponent_profiles && Object.keys(replayData.opponent_profiles).length > 0 && (
                  <button
                    onClick={() => setShowHud(v => { const n = !v; localStorage.setItem('replayer_show_hud', String(n)); return n; })}
                    title={t("hudToggleTip")}
                    className={cn(
                      "flex items-center gap-1 rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors ring-1 focus-visible:outline-none",
                      showHud ? "bg-primary/15 text-primary ring-primary/30" : "text-muted-foreground ring-border hover:text-foreground"
                    )}>
                    <Users className="size-3" /> HUD
                  </button>
                )}
              </div>
            </div>

            {/* Mobile: card de análise como bottom-sheet sobreposto (página não rola) */}
            {showAnalysis && (
              <div className="lg:hidden fixed inset-0 z-50 flex flex-col justify-end">
                <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowAnalysis(false)} />
                <div className="relative max-h-[82vh] overflow-y-auto rounded-t-2xl bg-background p-3 pb-6 shadow-2xl ring-1 ring-border">
                  <button
                    onClick={() => setShowAnalysis(false)}
                    aria-label={t("close")}
                    className="absolute right-3 top-3 z-10 rounded-full bg-background/80 backdrop-blur p-1.5 text-muted-foreground ring-1 ring-border transition-colors hover:bg-secondary hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                  <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" onClick={() => setShowAnalysis(false)} />
                  <SidePanels
                    step={step} isError={isError} isCorrect={isCorrect}
                    coachAnnotation={coachAnnotation} studentId={studentId}
                    currentDecisionId={currentDecisionId} annotating={annotating}
                    annComment={annComment} annMode={annMode} annAction={annAction}
                    annOverride={annOverride} saveAnn={saveAnn} deleteAnn={deleteAnn}
                    replayData={replayData} playerAliases={playerAliases}
                    setAnnotating={setAnnotating} setAnnComment={setAnnComment}
                    setAnnMode={setAnnMode} setAnnAction={setAnnAction}
                    setAnnOverride={setAnnOverride} openAnnotationForm={openAnnotationForm}
                    t={t}
                    gtoRequestStatus={gtoRequestStatus} onRequestGto={handleRequestGto}
                    tournamentId={tournamentId} handId={handId}
                    compact
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Desktop: análise sob demanda como modal centrado (mesa fica full-width).
            Só desktop (lg) — no mobile o bottom-sheet acima cuida do showAnalysis. */}
        {showAnalysis && (
          <div className="hidden lg:flex fixed inset-0 z-50 items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowAnalysis(false)} />
            <div className="relative max-w-[420px] w-full max-h-[85vh] overflow-y-auto rounded-2xl bg-background ring-1 ring-border shadow-2xl p-4">
              <button
                onClick={() => setShowAnalysis(false)}
                aria-label={t("close")}
                className="absolute right-3 top-3 z-10 rounded-full bg-background/80 backdrop-blur p-1.5 text-muted-foreground ring-1 ring-border transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="size-4" />
              </button>
              <SidePanels
                step={step} isError={isError} isCorrect={isCorrect}
                coachAnnotation={coachAnnotation} studentId={studentId}
                currentDecisionId={currentDecisionId} annotating={annotating}
                annComment={annComment} annMode={annMode} annAction={annAction}
                annOverride={annOverride} saveAnn={saveAnn} deleteAnn={deleteAnn}
                replayData={replayData} playerAliases={playerAliases}
                setAnnotating={setAnnotating} setAnnComment={setAnnComment}
                setAnnMode={setAnnMode} setAnnAction={setAnnAction}
                setAnnOverride={setAnnOverride} openAnnotationForm={openAnnotationForm}
                t={t}
                gtoRequestStatus={gtoRequestStatus} onRequestGto={handleRequestGto}
                tournamentId={tournamentId} handId={handId}
              />
            </div>
          </div>
        )}

      </div>

      {/* ── Range panel — floating (desktop) / bottom sheet (mobile) ── */}
      {showRange && step.street === 'preflop' && (
        <>
          <div
            className="hidden lg:block fixed z-50 w-[360px] rounded-xl shadow-2xl ring-1 ring-primary/25"
            style={{ left: rangePos.x, top: rangePos.y }}
          >
            <RangePanel key={stepIdx} step={step} hero={replayData.hero} heroCards={replayData.hero_cards} onClose={() => setShowRange(false)} onHeaderMouseDown={handleRangeDragStart} />
          </div>
          <div className="lg:hidden fixed inset-0 z-50 flex flex-col justify-end">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowRange(false)} />
            <div className="relative max-h-[72vh] overflow-y-auto rounded-t-2xl">
              <RangePanel key={`mobile-${stepIdx}`} step={step} hero={replayData.hero} heroCards={replayData.hero_cards} onClose={() => setShowRange(false)} />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Replayer;
