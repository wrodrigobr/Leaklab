import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, X } from "lucide-react";
import { metrics, practice, type EvLeak, type PracticeGrade, type PracticeTable } from "@/lib/api";
import { MesaDePratica } from "@/components/practice/MesaDePratica";
import { PainelDePratica } from "@/components/practice/PainelDePratica";
import {
  acaoDaTecla, acumula, CONFIG_PADRAO, devePausar, MAX_MESAS, mudaOSorteio, nivelDoGrade,
  proximoFoco, STATS_ZERO, type ConfigPratica, type Pausa, type StatsPratica,
} from "@/lib/pratica";
import { chaveDoLeak } from "@/lib/playlistDoLeak";
import { cn } from "@/lib/utils";

/**
 * Modo Prática: de 1 a 4 mesas preflop ao mesmo tempo.
 *
 * ── O que esta página decide, e o que ela não decide ──────────────────────────────────────────
 *
 * Ela orquestra: busca a rodada, guarda a resposta de cada mesa, move o foco, acumula o placar.
 * As REGRAS moram em `lib/pratica` (que tecla vira que ação naquele spot, quando a configuração
 * entra, o que conta como acerto, quando pausar), porque uma página com quatro mesas, rede em
 * toda rodada e teclado global não se monta em teste.
 *
 * ── O treino inteiro na URL ───────────────────────────────────────────────────────────────────
 *
 * Como no GTO Wizard, a configuração vive nos parâmetros: `?mesas=4&stacks=10,14&spot=vs_rfi`.
 * O efeito que interessa é o nosso: o coach monta o treino que o aluno precisa e manda o link.
 */

export default function Practice() {
  const { t } = useTranslation("practice");
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  // ── a configuração vem da URL, com o padrão da casa no lugar do que faltar ────────────────
  const daUrl = useMemo<ConfigPratica>(() => {
    const n = Number(params.get("mesas"));
    const stacks = (params.get("stacks") || "").split(",").map(Number).filter((x) => x > 0);
    const spot = params.get("spot") || "";
    const pausa = params.get("pausa") || "";
    return {
      mesas: n >= 1 && n <= MAX_MESAS ? n : CONFIG_PADRAO.mesas,
      stacks: stacks.length ? stacks.sort((a, b) => a - b) : CONFIG_PADRAO.stacks,
      cenario: ["mixed", "rfi", "vs_rfi", "vs_3bet"].includes(spot) ? spot : CONFIG_PADRAO.cenario,
      pausa: (["nunca", "erro", "acao"].includes(pausa) ? pausa : CONFIG_PADRAO.pausa) as Pausa,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()]);

  /** o que está VALENDO nas mesas abertas (só muda quando uma rodada nova nasce) */
  const [config, setConfig] = useState<ConfigPratica>(daUrl);
  /** o que o jogador escolheu e ainda não entrou */
  const [pendente, setPendente] = useState<ConfigPratica | null>(null);
  const [painel, setPainel] = useState(
    () => localStorage.getItem("pratica_painel") !== "false");

  const [mesas, setMesas] = useState<PracticeTable[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [foco, setFoco] = useState(0);
  const [respostas, setRespostas] = useState<Record<number, { acao: string; grade: PracticeGrade | null }>>({});
  const [stats, setStats] = useState<StatsPratica>(STATS_ZERO);
  const [esperando, setEsperando] = useState(false);
  const [detalhe, setDetalhe] = useState<number | null>(null);
  const [inicio] = useState(() => Date.now());

  /** os spots já servidos nesta sessão, para o servidor evitá-los enquanto houver pool */
  const vistos = useRef<string[]>([]);
  /** a lista de leaks dele, para marcar quando um spot sorteado calha de ser um */
  const [leaks, setLeaks] = useState<EvLeak[]>([]);

  useEffect(() => {
    let vivo = true;
    metrics.evSummary(0)
      .then((d) => { if (vivo) setLeaks(d.top_leaks ?? []); })
      .catch(() => { /* sem a lista, o treino roda igual: a marca é um extra */ });
    return () => { vivo = false; };
  }, []);

  // ── a rodada ──────────────────────────────────────────────────────────────────────────────
  const novaRodada = useCallback(async (c: ConfigPratica) => {
    setCarregando(true);
    setErro(false);
    try {
      const r = await practice.tables(c.mesas, {
        cenario: c.cenario, stacks: c.stacks, evitar: vistos.current.slice(-400),
      });
      const vindas = r.tables ?? [];
      // Sem mesa nenhuma não há tela: melhor dizer que o filtro não tem spot do que piscar vazio.
      if (!vindas.length) { setErro(true); setMesas([]); return; }
      vistos.current = [...vistos.current, ...vindas.map((m) => m.id)];
      setMesas(vindas);
      setRespostas({});
      setFoco(0);
      setEsperando(false);
      setConfig(c);
      setPendente(null);
    } catch {
      setErro(true);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => { void novaRodada(daUrl); /* primeira rodada */ }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  // ── responder uma mesa ────────────────────────────────────────────────────────────────────
  const responder = useCallback(async (i: number, acao: string) => {
    const mesa = mesas[i];
    if (!mesa || respostas[i]) return;
    // Grava a escolha ANTES da resposta do servidor: sem isso, dois cliques rápidos na mesma
    // mesa mandariam duas correções, e a segunda contaria no placar de novo.
    setRespostas((r) => ({ ...r, [i]: { acao, grade: null } }));
    let grade: PracticeGrade | null = null;
    try {
      grade = await practice.grade(mesa.spot, acao, mesa.xp_value);
    } catch {
      grade = null;
    }
    setRespostas((r) => ({ ...r, [i]: { acao, grade } }));
    setStats((s) => acumula(s, grade, acao));
    if (devePausar(config.pausa, nivelDoGrade(grade, acao))) setEsperando(true);
    setFoco((f) => {
      const respondidas = new Set([...Object.keys(respostas).map(Number), i]);
      const prox = proximoFoco(f, mesas.length, respondidas);
      return prox >= 0 ? prox : f;
    });
  }, [mesas, respostas, config.pausa]);

  const todasRespondidas = mesas.length > 0 && Object.keys(respostas).length >= mesas.length;

  // Fim de rodada: segue sozinho, a menos que o "pausar depois de" tenha segurado.
  useEffect(() => {
    if (!todasRespondidas || esperando || carregando) return;
    const id = setTimeout(() => { void novaRodada(pendente ?? config); }, 900);
    return () => clearTimeout(id);
  }, [todasRespondidas, esperando, carregando, pendente, config, novaRodada]);

  // ── teclado ───────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const alvo = e.target as HTMLElement | null;
      if (alvo && /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName)) return;

      if (e.key === "Tab") {
        const prox = proximoFoco(foco, mesas.length, new Set(Object.keys(respostas).map(Number)));
        if (prox >= 0) { e.preventDefault(); setFoco(prox); }
        return;
      }
      // Enter solta a rodada que o "pausar depois de" segurou
      if (e.key === "Enter" && esperando) { e.preventDefault(); setEsperando(false); return; }

      const mesa = mesas[foco];
      if (!mesa || respostas[foco]) return;
      const acao = acaoDaTecla(e.key, mesa.options);
      if (acao) { e.preventDefault(); void responder(foco, acao); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [foco, mesas, respostas, esperando, responder]);

  // ── a configuração ────────────────────────────────────────────────────────────────────────
  const aoConfigurar = (c: ConfigPratica) => {
    // A pausa aplica na HORA (só decide quando a tela espera); o resto muda o sorteio e espera.
    if (!mudaOSorteio(config, c)) {
      setConfig(c);
      setPendente(pendente ? { ...pendente, pausa: c.pausa } : null);
    } else {
      setPendente(c);
    }
    const p = new URLSearchParams();
    p.set("mesas", String(c.mesas));
    p.set("stacks", c.stacks.join(","));
    p.set("spot", c.cenario);
    p.set("pausa", c.pausa);
    setParams(p, { replace: true });
  };

  const alternarPainel = (v: boolean) => {
    setPainel(v);
    localStorage.setItem("pratica_painel", String(v));
  };

  /** Este spot é um leak medido DELE? Devolve a posição na lista, ou null. */
  const leakDoSpot = (m: PracticeTable): number | null => {
    if (!leaks.length) return null;
    const chave = `preflop:${m.spot.scenario}`;
    const i = leaks.findIndex((l) => chaveDoLeak(l).startsWith(chave));
    return i >= 0 ? i + 1 : null;
  };

  const minutos = Math.floor((Date.now() - inicio) / 60000);
  const emDetalhe = detalhe != null ? respostas[detalhe] : null;

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background hud-scanline">
      {/* barra */}
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border bg-hud-surface px-3 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <button onClick={() => navigate("/training")}
                  className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary">
            <ArrowLeft className="size-3.5" /> {t("voltar")}
          </button>
          <span className="truncate font-mono text-[10.5px] tracking-widest text-muted-foreground">
            {t("sessao", { maos: stats.maos, min: minutos })}
          </span>
        </div>
        <button onClick={() => navigate("/training")}
                data-testid="pratica-encerrar"
                className="shrink-0 rounded border border-border px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground">
          {t("encerrar")}
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
        <PainelDePratica aberto={painel} config={config} pendente={pendente} stats={stats}
                         onConfig={aoConfigurar} onAlternar={alternarPainel} />

        <div className="min-w-0 flex-1 overflow-y-auto scrollbar-hud p-3">
          {carregando && !mesas.length ? (
            <div className="flex h-full items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> <span className="font-mono text-xs">{t("carregando")}</span>
            </div>
          ) : erro ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <p className="font-mono text-sm text-foreground">{t("semSpot.titulo")}</p>
              <p className="max-w-[46ch] text-xs text-muted-foreground">{t("semSpot.desc")}</p>
            </div>
          ) : (
            <div className={cn("grid gap-3",
              mesas.length === 1 ? "mx-auto max-w-[900px] grid-cols-1"
                : mesas.length === 2 ? "grid-cols-1 xl:grid-cols-2"
                : "grid-cols-1 lg:grid-cols-2")}>
              {mesas.map((m, i) => (
                <MesaDePratica
                  key={m.id}
                  mesa={m}
                  foco={i === foco}
                  respondida={!!respostas[i]}
                  grade={respostas[i]?.grade ?? null}
                  acaoEscolhida={respostas[i]?.acao ?? null}
                  leakDoJogador={leakDoSpot(m)}
                  compacta={mesas.length >= 3}
                  onAgir={(a) => void responder(i, a)}
                  onFocar={() => setFoco(i)}
                  onDetalhe={() => setDetalhe(i)}
                />
              ))}
            </div>
          )}

          {/* o "pausar depois de" segurou: o jogador solta quando quiser */}
          {esperando && todasRespondidas && (
            <div className="sticky bottom-0 mt-3 flex items-center justify-center">
              <button type="button" onClick={() => setEsperando(false)}
                      data-testid="pratica-continuar"
                      className="rounded-full bg-primary px-5 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground shadow-lg">
                {t("continuar")}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* o detalhe, sob demanda: a linha do veredito basta na maioria das rodadas */}
      {emDetalhe && detalhe != null && mesas[detalhe] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
             onClick={() => setDetalhe(null)}>
          <div className="relative w-full max-w-[440px] rounded-xl bg-background p-4 ring-1 ring-border"
               onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setDetalhe(null)} aria-label={t("fechar")}
                    className="absolute right-3 top-3 text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
            <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
              {mesas[detalhe].context}
            </p>
            <p className="mt-1 font-mono text-lg font-bold">{mesas[detalhe].hand}</p>
            <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {emDetalhe.grade?.explanation || t("semExplicacao")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
