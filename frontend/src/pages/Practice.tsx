import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, History as HistoryIcon, Loader2, SlidersHorizontal, X } from "lucide-react";
import { metrics, practice, type EvLeak, type PracticeGrade, type PracticeTable } from "@/lib/api";
import { MesaDePratica } from "@/components/practice/MesaDePratica";
import { PainelDePratica } from "@/components/practice/PainelDePratica";
import { RelatorioDePratica } from "@/components/practice/RelatorioDePratica";
import {
  acaoDaTecla, acumula, CONFIG_PADRAO, configNaTela, devePausar, MAX_MESAS, mudaOSorteio,
  gradeDaTela, ALTURA_MINIMA_DO_CARD, POSICOES_DISPONIVEIS,
  nivelDoGrade, proximoFoco, STATS_ZERO, tetoDeMesas, type ConfigPratica, type Pausa,
  type StatsPratica, type Unidade,
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

/** Quanto o veredito fica na tela antes do spot novo entrar NAQUELA mesa.
 *
 *  Dois segundos foi o que o dono pediu, e o numero e visivel de proposito: e o unico lugar que
 *  decide o ritmo do treino, e ele vai querer mexer depois de rodar uma sessao. Com "pausar
 *  depois de" ligado, este prazo nao corre -- quem solta e o jogador. */
const MS_DO_VEREDITO = 2000;

export default function Practice() {
  const { t } = useTranslation("practice");
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  // ── a configuração vem da URL, com o padrão da casa no lugar do que faltar ────────────────
  const daUrl = useMemo<ConfigPratica>(() => {
    const n = Number(params.get("mesas"));
    const stacks = (params.get("stacks") || "").split(",").map(Number).filter((x) => x > 0);
    const spot = params.get("spot") || "";
    // A posição só entra pelo ROTULO, e um rotulo desconhecido e descartado em vez de virar
    // filtro que nunca casa: `?posicoes=BUTTON` pediria um spot que o servidor nunca devolve, e a
    // tela ficaria pedindo mesas para sempre sem dizer por que.
    const pos = (params.get("posicoes") || "").split(",")
      .map((x) => x.trim().toUpperCase())
      .filter((x) => (POSICOES_DISPONIVEIS as readonly string[]).includes(x));
    const pausa = params.get("pausa") || "";
    const un = params.get("un") || "";
    return {
      mesas: n >= 1 && n <= MAX_MESAS ? n : CONFIG_PADRAO.mesas,
      stacks: stacks.length ? stacks.sort((a, b) => a - b) : CONFIG_PADRAO.stacks,
      // a ORDEM DE AÇÃO, e não a ordem em que ele digitou: duas listas com as mesmas posições em
      // ordens diferentes fariam `mudaOSorteio` dizer que mudou algo
      posicoes: pos.length
        ? POSICOES_DISPONIVEIS.filter((x) => pos.includes(x))
        : CONFIG_PADRAO.posicoes,
      cenario: ["mixed", "rfi", "vs_rfi", "vs_3bet"].includes(spot) ? spot : CONFIG_PADRAO.cenario,
      pausa: (["nunca", "erro", "acao"].includes(pausa) ? pausa : CONFIG_PADRAO.pausa) as Pausa,
      // O padrao vem de `CONFIG_PADRAO`, e nao de um literal aqui: com "bb" escrito nesta
      // linha havia DUAS fontes para a mesma decisao, e a daqui ganhava sempre -- mudar o
      // padrao na lib nao mudava nada, e o guarda passava verde com o padrao invertido. Foi o
      // controle da quebra que pegou (regra 5).
      unidade: (["bb", "fichas"].includes(un) ? un : CONFIG_PADRAO.unidade) as Unidade,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()]);

  /** o que está VALENDO nas mesas abertas (só muda quando uma rodada nova nasce) */
  const [config, setConfig] = useState<ConfigPratica>(daUrl);
  /** o que o jogador escolheu e ainda não entrou */
  const [pendente, setPendente] = useState<ConfigPratica | null>(null);
  const [relatorio, setRelatorio] = useState(false);

  /**
   * A largura da JANELA, observada.
   *
   * Nenhum teste de user-agent: o que decide quantas mesas cabem e o espaco, e o espaco muda com
   * o celular girando e com a janela do desktop pela metade. `resize` cobre os dois; detectar
   * aparelho erraria nos dois, e erraria calado.
   */
  const [janela, setJanela] = useState(() => ({
    w: typeof window === "undefined" ? 1440 : window.innerWidth,
    h: typeof window === "undefined" ? 900 : window.innerHeight,
  }));
  useEffect(() => {
    const aoRedimensionar = () => setJanela({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", aoRedimensionar);
    // orientationchange porque em alguns navegadores de celular o `resize` chega antes de a
    // largura nova valer, e a leitura sai com o valor velho
    window.addEventListener("orientationchange", aoRedimensionar);
    return () => {
      window.removeEventListener("resize", aoRedimensionar);
      window.removeEventListener("orientationchange", aoRedimensionar);
    };
  }, []);
  // A ALTURA entra na conta: o dono reduziu a altura da janela com quatro mesas e elas viraram
  // fitas. Medido com o medidor de colisao: card de 300px de altura passa com zero
  // sobreposicoes, 250px da 648 e 200px da 4.824. Se nao cabem quatro, o Pratica abre duas.
  const teto = tetoDeMesas(janela.w, janela.h);
  const [painel, setPainel] = useState(() => {
    // No celular o painel comeca FECHADO, e a preferencia guardada nao vale ali: aberto, a gaveta
    // cobre a mesa inteira, e o jogador cairia no treino sem ver o que esta treinando. No desktop
    // ele e uma coluna ao lado, e a preferencia manda.
    if (typeof window !== "undefined" && tetoDeMesas(window.innerWidth, window.innerHeight) < MAX_MESAS) return false;
    return localStorage.getItem("pratica_painel") !== "false";
  });

  const [mesas, setMesas] = useState<PracticeTable[]>([]);
  /**
   * A GRADE desta tela, recalculada a cada render.
   *
   * O teto de mesas era consultado num lugar so: na hora de BUSCAR. Quem desenhava usava classes
   * fixas, e por isso reduzir a janela com quatro mesas abertas encolhia as quatro em vez de
   * fechar duas. Agora quem desenha pergunta a mesma funcao, e o que nao cabe nao aparece.
   */
  const gradeNaTela = gradeDaTela(mesas.length, janela.w, janela.h);
  const visiveis = mesas.slice(0, gradeNaTela.mesas);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  /**
   * O filtro rendeu MENOS mesas do que o pedido.
   *
   * Isto e informacao, e nao acidente: medido em 17/09, tres combinacoes de posicao e tipo de spot
   * tem um spot so e nao mais -- `rfi` com BB (o BB nunca abre primeiro), `vs_rfi` com UTG
   * (ninguem age antes do UTG) e `vs_3bet` com BB. Sem esta linha, escolher uma delas mostraria
   * UMA mesa no lugar de quatro e o jogador leria isso como travamento. O servidor sempre devolve
   * `pedidas` e `servidas`; quem nao usava era a tela.
   */
  const [estreito, setEstreito] = useState<{ pedidas: number; servidas: number } | null>(null);
  const [foco, setFoco] = useState(0);
  const [respostas, setRespostas] = useState<
    Record<number, { acao: string; grade: PracticeGrade | null; avaliando: boolean }>
  >({});
  const [stats, setStats] = useState<StatsPratica>(STATS_ZERO);
  /** Quais mesas estão SEGURADAS pelo "pausar depois de". Por mesa, e não global: com as mesas
   *  girando independentes, um único sinalizador faria uma pausa na mesa 3 travar as outras. */
  const [esperando, setEsperando] = useState<Record<number, boolean>>({});
  const [detalhe, setDetalhe] = useState<number | null>(null);
  const [inicio] = useState(() => Date.now());

  /** os spots já servidos nesta sessão, para o servidor evitá-los enquanto houver pool */
  const vistos = useRef<string[]>([]);
  /** A configuração que vale AGORA, para quem roda dentro de `setTimeout` ler o valor atual em
   *  vez do que a closure capturou. Sem isto, mudar o filtro no painel só valeria dois spots
   *  depois, e de um jeito que ninguém liga à causa. */
  const cfg = useRef<ConfigPratica>(daUrl);
  /** Um temporizador por mesa: eles vivem em paralelo, e um `clearTimeout` de um não pode
   *  alcançar o de outra mesa. */
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  /** a lista de leaks dele, para marcar quando um spot sorteado calha de ser um */
  const [leaks, setLeaks] = useState<EvLeak[]>([]);

  // `cfg` acompanha o estado: um `useEffect` sem condição, porque ele é só espelho.
  useEffect(() => { cfg.current = config; }, [config]);

  // Sair da tela com temporizadores armados dispararia `setState` em componente desmontado, e
  // pior, uma busca de spot para uma sessão que já acabou.
  useEffect(() => () => {
    Object.values(timers.current).forEach(clearTimeout);
    timers.current = {};
  }, []);

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
      // O teto da TELA entra aqui, no unico ponto em que as mesas sao pedidas: qualquer caminho
      // (a URL com `?mesas=4`, o painel, o botao aplicar) passa por este lugar. A leitura e
      // direta da janela, e nao do estado, porque isto tambem roda dentro de temporizadores --
      // e o estado que a closure capturou pode ser de antes de o celular girar.
      const naTela = configNaTela(
        c,
        typeof window === "undefined" ? 1440 : window.innerWidth,
        typeof window === "undefined" ? 900 : window.innerHeight,
      );
      const r = await practice.tables(naTela.mesas, {
        cenario: c.cenario, stacks: c.stacks, posicoes: c.posicoes,
        evitar: vistos.current.slice(-400),
      });
      const vindas = r.tables ?? [];
      // Sem mesa nenhuma não há tela: melhor dizer que o filtro não tem spot do que piscar vazio.
      if (!vindas.length) { setErro(true); setMesas([]); return; }
      setEstreito(r.servidas < r.pedidas ? { pedidas: r.pedidas, servidas: r.servidas } : null);
      vistos.current = [...vistos.current, ...vindas.map((m) => m.id)];
      setMesas(vindas);
      setRespostas({});
      setFoco(0);
      setEsperando({});
      setConfig(c);
      setPendente(null);
    } catch {
      setErro(true);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => { void novaRodada(daUrl); /* primeira rodada */ }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * A janela mudou de tamanho e o numero de mesas que CABE mudou com ela: nasce uma rodada nova.
   *
   * O aparo do desenho (`visiveis`) ja protege a legibilidade na hora, e este efeito e o que
   * acerta o estado atras dele -- sem ele, quem reduz a janela fica com duas mesas desenhadas e
   * quatro vivas (as duas escondidas ainda puxariam spot), e quem volta a maximizar nao recupera
   * as quatro, porque o estado tem duas.
   *
   * O atraso existe porque arrastar a borda da janela dispara `resize` dezenas de vezes: sem ele
   * o Pratica pediria uma rodada por quadro. E a comparacao e com o que esta ABERTO, para o efeito
   * nao se armar sozinho -- o que ele muda e justamente o que ele compara.
   */
  useEffect(() => {
    if (!mesas.length) return;
    const cabe = configNaTela(config, janela.w, janela.h).mesas;
    if (cabe === mesas.length) return;
    const t = setTimeout(() => { void novaRodada(config); }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [janela.w, janela.h, mesas.length, config]);

  /** O foco nunca pode ficar numa mesa que a tela deixou de mostrar. */
  useEffect(() => {
    if (foco >= gradeNaTela.mesas) setFoco(0);
  }, [foco, gradeNaTela.mesas]);

  // ── responder uma mesa ────────────────────────────────────────────────────────────────────
  const responder = useCallback(async (i: number, acao: string) => {
    const mesa = mesas[i];
    if (!mesa || respostas[i]) return;
    // Grava a escolha ANTES da resposta do servidor: sem isso, dois cliques rápidos na mesma
    // mesa mandariam duas correções, e a segunda contaria no placar de novo.
    // `avaliando` e o que separa "a resposta nao voltou ainda" de "a resposta voltou vazia". Sem
    // essa distincao a mesa julgava com `grade` nulo e acusava "errada" no intervalo, que foi o
    // flash que o dono viu.
    setRespostas((r) => ({ ...r, [i]: { acao, grade: null, avaliando: true } }));
    let grade: PracticeGrade | null = null;
    try {
      grade = await practice.grade(mesa.spot, acao, mesa.xp_value);
    } catch {
      grade = null;
    }
    setRespostas((r) => ({ ...r, [i]: { acao, grade, avaliando: false } }));
    setStats((s) => acumula(s, grade, acao));

    const nivel = nivelDoGrade(grade, acao);
    setFoco((f) => {
      const respondidas = new Set([...Object.keys(respostas).map(Number), i]);
      // `grade.mesas`, e nao `mesas.length`: numa janela baixa o Pratica desenha menos mesas
      // do que abriu, e o foco nao pode cair numa que a tela nao mostra.
      const prox = proximoFoco(f, gradeNaTela.mesas, respondidas);
      return prox >= 0 ? prox : f;
    });

    // O veredito fica, e DEPOIS a mesa recebe um spot novo -- so ela. Esperar as quatro
    // responderem para girar a rodada inteira (o desenho anterior) fazia o jogador parar na
    // mesa mais lenta, que e o oposto do que quatro mesas existem para resolver.
    //
    // Com a pausa ligada no nivel dela, o prazo nao corre: quem solta e o jogador, e e o
    // `continuar` que dispara a troca do que estiver esperando.
    if (devePausar(cfg.current.pausa, nivel)) {
      setEsperando((e) => ({ ...e, [i]: true }));
      return;
    }
    agendarTroca(i);
  }, [mesas, respostas]);   // eslint-disable-line react-hooks/exhaustive-deps

  /** Marca a mesa para trocar depois do tempo de leitura do veredito. */
  const agendarTroca = useCallback((i: number) => {
    const antigo = timers.current[i];
    if (antigo) clearTimeout(antigo);
    timers.current[i] = setTimeout(() => {
      delete timers.current[i];
      void trocarSpot(i);
    }, MS_DO_VEREDITO);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Um spot novo NAQUELA mesa, com a configuração que vale AGORA.
   *
   *  `cfg.current` e não a variável de estado: este código roda dentro de um `setTimeout`, e a
   *  closure capturaria a configuração de dois segundos atrás -- o jogador mudaria o filtro no
   *  painel e a mesa seguinte ainda viria do filtro velho. */
  const trocarSpot = useCallback(async (i: number) => {
    const c = cfg.current;
    try {
      const r = await practice.tables(1, {
        cenario: c.cenario, stacks: c.stacks, evitar: vistos.current.slice(-400),
      });
      const nova = r.tables?.[0];
      if (!nova) return;                 // sem spot no filtro: a mesa fica com o veredito à vista
      vistos.current = [...vistos.current, nova.id];
      setMesas((ms) => ms.map((m, k) => (k === i ? nova : m)));
      setRespostas((rs) => {
        const { [i]: _fora, ...resto } = rs;
        return resto;
      });
      setEsperando((e) => {
        const { [i]: _f, ...resto } = e;
        return resto;
      });
    } catch {
      /* mantém a mesa como está: melhor o veredito parado do que a mesa vazia */
    }
  }, []);

  /** Solta as mesas que a pausa segurou: cada uma recebe spot novo, sem esperar as outras. */
  const soltarEsperando = useCallback(() => {
    const paradas = Object.keys(esperando).map(Number);
    setEsperando({});
    paradas.forEach((i) => agendarTroca(i));
  }, [esperando, agendarTroca]);

  // ── teclado ───────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const alvo = e.target as HTMLElement | null;
      if (alvo && /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName)) return;

      if (e.key === "Tab") {
        const prox = proximoFoco(foco, gradeNaTela.mesas, new Set(Object.keys(respostas).map(Number)));
        if (prox >= 0) { e.preventDefault(); setFoco(prox); }
        return;
      }
      // Enter solta a rodada que o "pausar depois de" segurou
      // Enter solta o que a pausa segurou (todas as mesas paradas, de uma vez)
      if (e.key === "Enter" && Object.keys(esperando).length) {
        e.preventDefault();
        soltarEsperando();
        return;
      }

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
      // pausa e unidade valem JA; o pendente, se houver, herda as duas
      setPendente(pendente ? { ...pendente, pausa: c.pausa, unidade: c.unidade } : null);
    } else {
      setPendente(c);
    }
    const p = new URLSearchParams();
    p.set("mesas", String(c.mesas));
    p.set("stacks", c.stacks.join(","));
    p.set("spot", c.cenario);
    p.set("pausa", c.pausa);
    p.set("un", c.unidade);
    setParams(p, { replace: true });
  };

  /** Troca TODAS as mesas agora, com a configuração pendente.
   *
   *  Descartar as mesas abertas é o comportamento certo AQUI, e não contradiz o cuidado de
   *  `mudaOSorteio`: lá o risco é a configuração descartar por conta própria o que o jogador
   *  está jogando; aqui ele pediu a troca, clicando. E o que ele já respondeu continua no
   *  placar -- o descarte é dos spots ainda não respondidos.
   *
   *  Os temporizadores pendentes precisam morrer junto: um `trocarSpot` agendado para a mesa 2
   *  chegaria depois da rodada nova e substituiria uma mesa recém-sorteada. */
  const aplicarAgora = useCallback(() => {
    Object.values(timers.current).forEach(clearTimeout);
    timers.current = {};
    void novaRodada(pendente ?? config);
  }, [pendente, config, novaRodada]);

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
      {/* ── A barra ──────────────────────────────────────────────────────────────────────────
          No celular ela estava ILEGIVEL: "voltar ao treino", "maos praticadas" e "encerrar e ver
          boletim" somados passam de 390px, e os tres textos se sobrepunham (o dono fotografou).
          Agora o texto de cada botao aparece a partir de `sm`, e no celular ficam os icones -- o
          proprio rotulo vai no `title`/`aria-label`, que e o que um icone sozinho precisa. */}
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-hud-surface px-2 py-2 sm:gap-4 sm:px-3">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <button onClick={() => navigate("/training")} title={t("voltar")} aria-label={t("voltar")}
                  className="inline-flex shrink-0 items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary">
            <ArrowLeft className="size-3.5" />
            <span className="hidden sm:inline">{t("voltar")}</span>
          </button>
          {/* a configuracao: no celular o painel e uma gaveta, e este e o unico acesso a ela */}
          <button onClick={() => alternarPainel(!painel)} data-testid="pratica-abrir-painel-mobile"
                  title={t("painel.abrir")} aria-label={t("painel.abrir")}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary lg:hidden">
            <SlidersHorizontal className="size-3" />
          </button>
          <span className="truncate font-mono text-[10.5px] tracking-widest text-muted-foreground">
            {t("sessao", { maos: stats.maos, min: minutos })}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
        {/* O relatorio abre SOBRE a tela do treino, e nao em outra rota: o jogador consulta e
            volta para as mesas que ainda estao abertas. Trocar de rota perderia a sessao. */}
        <button onClick={() => setRelatorio(true)} data-testid="pratica-abrir-relatorio"
                title={t("relatorio.titulo")} aria-label={t("relatorio.titulo")}
                className="inline-flex items-center gap-1.5 rounded border border-border px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary">
          <HistoryIcon className="size-3" />
          <span className="hidden sm:inline">{t("relatorio.titulo")}</span>
        </button>
        <button onClick={() => navigate("/training")}
                data-testid="pratica-encerrar"
                title={t("encerrar")} aria-label={t("encerrar")}
                className="shrink-0 rounded border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground sm:px-2.5">
          <X className="size-3 sm:hidden" />
          <span className="hidden sm:inline">{t("encerrar")}</span>
        </button>
        </div>
      </div>

      <div className="relative flex min-h-0 flex-1">
        <RelatorioDePratica aberto={relatorio} onFechar={() => setRelatorio(false)} />
        <PainelDePratica aberto={painel} config={config} pendente={pendente} stats={stats}
                         tetoDeMesas={teto}
                         onConfig={aoConfigurar} onAlternar={alternarPainel}
                         onAplicar={aplicarAgora} />

        {/* As mesas cabem na tela, SEM barra de rolagem (requisito do dono, 16/09): esta faixa
            e `overflow-hidden` e a grade abaixo e limitada por ALTURA. Um `overflow-y-auto` aqui
            deixaria a 3a e a 4a mesa abaixo da dobra em notebook, e o jogador rolaria a tela no
            meio de uma rodada de quatro mesas -- perdendo justamente o que o modo existe para
            treinar. Mesma doutrina da mesa do replayer, que e height-bound pelo mesmo motivo. */}
        <div className={cn("min-w-0 flex-1 p-3", gradeNaTela.rola ? "overflow-y-auto" : "overflow-hidden")}>
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
            // As colunas, as linhas e o PISO de altura de cada celula saem de `gradeDaTela`,
            // e nao de classes fixas. Era o contrario: `grid-rows-2` cravado dividia a altura em
            // duas e cada mesa encolhia sem piso -- numa janela baixa com quatro mesas abertas,
            // cada uma virava um borrao de 86px, que foi a captura do dono em 17/09.
            //
            // Com o piso, se a celula nao alcanca o minimo a faixa ROLA em vez de achatar; antes
            // de chegar la a grade ja tirou mesa e tirou coluna.
            <>
            {estreito && (
              <p data-testid="pratica-filtro-estreito"
                 className="mb-2 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 font-mono text-[10px] leading-relaxed text-amber-200/90">
                {t("filtroEstreito", { servidas: estreito.servidas, pedidas: estreito.pedidas })}
              </p>
            )}
            <div className={cn("grid min-h-0 gap-3",
                               gradeNaTela.rola ? "h-auto" : "h-full",
                               gradeNaTela.mesas === 1 && "mx-auto max-w-[980px]")}
                 data-testid="pratica-grade"
                 style={{
                   gridTemplateColumns: `repeat(${gradeNaTela.colunas}, minmax(0, 1fr))`,
                   gridTemplateRows: `repeat(${gradeNaTela.linhas}, minmax(${ALTURA_MINIMA_DO_CARD}px, 1fr))`,
                 }}>
              {visiveis.map((m, i) => (
                <MesaDePratica
                  key={m.id}
                  mesa={m}
                  foco={i === foco}
                  respondida={!!respostas[i]}
                  grade={respostas[i]?.grade ?? null}
                  avaliando={!!respostas[i]?.avaliando}
                  acaoEscolhida={respostas[i]?.acao ?? null}
                  leakDoJogador={leakDoSpot(m)}
                  compacta={visiveis.length >= 3}
                  unidade={config.unidade}
                  onAgir={(a) => void responder(i, a)}
                  onFocar={() => setFoco(i)}
                  onDetalhe={() => setDetalhe(i)}
                />
              ))}
            </div>
            </>
          )}

          {/* o "pausar depois de" segurou: o jogador solta quando quiser */}
          {!!Object.keys(esperando).length && (
            <div className="sticky bottom-0 mt-3 flex items-center justify-center">
              <button type="button" onClick={soltarEsperando}
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
