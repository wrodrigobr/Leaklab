import { useTranslation } from "react-i18next";
import { RotateCw, SlidersHorizontal, X } from "lucide-react";
import {
  MAX_MESAS, NIVEIS, SIMBOLO_DO_NIVEL, STACKS_DISPONIVEIS, type ConfigPratica, type Nivel,
  type Pausa, type StatsPratica, type Unidade,
} from "@/lib/pratica";
import { cn } from "@/lib/utils";

/**
 * O painel lateral: configura o treino SEM sair dele, e mostra o placar da sessão.
 *
 * ── A decisão que ele carrega ─────────────────────────────────────────────────────────────────
 *
 * Mexer em mesas, stack ou tipo de spot muda o SORTEIO, então entra na próxima rodada e o painel
 * diz isso onde a mudança acontece. No GTO Wizard trocar o número de mesas reinicia a sessão e
 * descarta o que o jogador já respondeu; aqui as mesas em jogo terminam com as regras com que
 * começaram. A régua de quem espera e quem aplica na hora é `mudaOSorteio`, em `lib/pratica`.
 *
 * ── Por que lateral, e recolhível ─────────────────────────────────────────────────────────────
 *
 * Mesmo motivo do painel do leak no replayer: com quatro mesas a largura é o recurso escasso.
 * Recolhido, sobra a aba de 36px e a grade recupera o espaço.
 */

/** A cor do símbolo na legenda, alinhada com a da barra. */
const TEXTO_DA_ESCALA: Record<Nivel, string> = {
  correta:    "text-emerald-400",
  imprecisao: "text-amber-400",
  errada:     "text-red-400",
  grave:      "text-red-600",
};

const COR_DA_BARRA: Record<Nivel, string> = {
  correta:    "bg-emerald-500",
  imprecisao: "bg-amber-500",
  errada:     "bg-red-500",
  grave:      "bg-red-900",
};

export function PainelDePratica({
  aberto, config, pendente, stats, tetoDeMesas, onConfig, onAlternar, onAplicar,
}: {
  aberto: boolean;
  /** Quantas mesas a TELA aguenta. No celular e 1, e o seletor trava acima disso: "Nao permitir
   *  aumentar o numero de mesas em telas pequenas" (o dono, 17/09). */
  tetoDeMesas: number;
  /** o que está VALENDO nas mesas abertas */
  config: ConfigPratica;
  /** o que o jogador escolheu e entra na próxima rodada; `null` = nada pendente */
  pendente: ConfigPratica | null;
  stats: StatsPratica;
  onConfig: (c: ConfigPratica) => void;
  onAlternar: (v: boolean) => void;
  /** troca TODAS as mesas agora, com a configuração pendente */
  onAplicar: () => void;
}) {
  const { t } = useTranslation("practice");
  // O painel edita o PENDENTE quando há um, senão o que está valendo: sem isso, dois cliques
  // seguidos no painel fariam o segundo esquecer o primeiro.
  const atual = pendente ?? config;
  const muda = (p: Partial<ConfigPratica>) => onConfig({ ...atual, ...p });

  if (!aberto) {
    return (
      // Fechado, a abinha vertical existe SO no desktop: no celular ela comeria largura da mesa,
      // e o acesso de la e o botao na barra do topo.
      <aside data-testid="pratica-painel-fechado"
             className="hidden lg:flex w-9 shrink-0 flex-col items-center gap-2 border-r border-border bg-hud-surface/40 py-3">
        <button type="button" onClick={() => onAlternar(true)}
                data-testid="pratica-painel-abrir"
                aria-label={t("painel.abrir")} title={t("painel.abrir")}
                className="text-primary transition-colors hover:text-primary-glow">
          <SlidersHorizontal className="size-4" aria-hidden />
        </button>
        <span className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground"
              style={{ writingMode: "vertical-rl" }}>
          {t("painel.aba")}
        </span>
      </aside>
    );
  }

  return (
    /* ── Aberto: GAVETA no celular, coluna no desktop ──────────────────────────────────────
       Ele era `hidden lg:flex`, ou seja no celular o painel simplesmente NAO EXISTIA -- e sem
       ele nao havia como trocar stack, cenario nem unidade no telefone. O dono: "garantir que o
       menu de configuracao apareca, hoje isto nao esta acontecendo".

       No celular a gaveta se sobrepoe as mesas (`absolute`) em vez de dividir a largura com
       elas: uma coluna de 180px num card de 390 nao deixa mesa nenhuma legivel. */
    <aside data-testid="pratica-painel"
           className="absolute inset-y-0 left-0 z-30 flex w-[min(84vw,272px)] shrink-0 flex-col
                      overflow-y-auto scrollbar-hud border-r border-border bg-hud-surface
                      lg:static lg:z-auto lg:w-[clamp(180px,14vw,224px)] lg:bg-hud-surface/60">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="font-mono text-[9.5px] uppercase tracking-widest-2 text-primary">
          {t("painel.titulo")}
        </span>
        <button type="button" onClick={() => onAlternar(false)} aria-label={t("painel.fechar")}
                className="text-muted-foreground transition-colors hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>

      {/* mesas */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.mesas")}</Rotulo>
        <div className="flex gap-1">
          {Array.from({ length: MAX_MESAS }, (_, i) => i + 1).map((n) => {
            const cabe = n <= tetoDeMesas;
            return (
              <Seg key={n} on={atual.mesas === n && cabe} onClick={() => cabe && muda({ mesas: n })}
                   desabilitado={!cabe} titulo={cabe ? undefined : t("painel.soUmaMesa")}
                   testid={`pratica-mesas-${n}`}>{n}</Seg>
            );
          })}
        </div>
        {tetoDeMesas < MAX_MESAS && (
          // A frase explica o que o botao cinza nao explica. Sem ela, o jogador acha que o
          // seletor esta quebrado -- e no celular ele nao tem como descobrir o motivo.
          <p data-testid="pratica-so-uma-mesa"
             className="mt-1.5 font-mono text-[9px] leading-relaxed text-muted-foreground/80">
            {t("painel.soUmaMesa")}
          </p>
        )}
        {pendente && (
          <div data-testid="pratica-pendente" className="mt-2">
            {/* ── O botao APLICAR (pedido do dono, 16/09) ────────────────────────────────────
                "quando troco alguma configuracao, aparece esta msg...mas demora muito pra trocar
                a configuracao....acho que poderiamos ter um botao aplicar".

                A demora tem causa: com as mesas girando INDEPENDENTES, a configuracao nova so
                entra quando CADA mesa termina a mao dela -- e com quatro mesas isso leva varias
                rodadas. O aviso dizia a verdade e ainda assim frustrava, porque quem mexe no
                painel quer ver o efeito.

                Agora sao duas saidas, e o jogador escolhe: clicar e trocar tudo agora, ou nao
                clicar e deixar entrar sozinho. O aviso continua embaixo explicando a segunda. */}
            <button type="button" onClick={onAplicar}
                    data-testid="pratica-aplicar"
                    className="flex w-full items-center justify-center gap-1.5 rounded bg-primary px-2 py-1.5
                               font-mono text-[10px] font-bold uppercase tracking-widest-2 text-background
                               transition-colors hover:bg-primary-glow">
              <RotateCw className="size-3" aria-hidden />
              {t("painel.aplicarAgora")}
            </button>
            <span className="mt-1 block font-mono text-[9px] leading-relaxed text-primary/70">
              {t("painel.aplicaDepois")}
            </span>
          </div>
        )}
      </div>

      {/* stack efetivo */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.stack")}</Rotulo>
        <div className="flex flex-wrap gap-1">
          {STACKS_DISPONIVEIS.map((s) => {
            const on = atual.stacks.includes(s);
            return (
              <button key={s} type="button" data-testid={`pratica-stack-${s}`}
                      onClick={() => muda({
                        // Nunca deixa a lista vazia: sem stack nenhum o sorteio não tem de onde
                        // tirar mesa, e a tela ficaria pedindo mesas que nunca chegam.
                        stacks: on
                          ? (atual.stacks.length > 1 ? atual.stacks.filter((x) => x !== s) : atual.stacks)
                          : [...atual.stacks, s].sort((a, b) => a - b),
                      })}
                      className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors",
                        on ? "border-primary/45 bg-primary/10 text-primary"
                           : "border-border text-muted-foreground hover:text-foreground")}>
                {s}
              </button>
            );
          })}
        </div>
      </div>

      {/* tipo de spot */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.spot")}</Rotulo>
        <div className="flex flex-col gap-1">
          {(["mixed", "rfi", "vs_rfi", "vs_3bet"] as const).map((c) => (
            <Seg key={c} on={atual.cenario === c} onClick={() => muda({ cenario: c })}
                 testid={`pratica-cenario-${c}`} esquerda>{t(`cenario.${c}`)}</Seg>
          ))}
        </div>
      </div>

      {/* unidade da mesa — aplica na HORA: só muda como o número é escrito */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.unidade")}</Rotulo>
        <div className="flex gap-1">
          {(["bb", "fichas"] as Unidade[]).map((u) => (
            <Seg key={u} on={atual.unidade === u} onClick={() => muda({ unidade: u })}
                 testid={`pratica-unidade-${u}`}>{t(`unidade.${u}`)}</Seg>
          ))}
        </div>
      </div>

      {/* pausar depois de — aplica na HORA, porque só decide quando a tela espera */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.pausa")}</Rotulo>
        <div className="flex gap-1">
          {(["nunca", "erro", "acao"] as Pausa[]).map((p) => (
            <Seg key={p} on={atual.pausa === p} onClick={() => muda({ pausa: p })}
                 testid={`pratica-pausa-${p}`}>{t(`pausa.${p}`)}</Seg>
          ))}
        </div>
      </div>

      {/* placar da sessão */}
      <div className="mt-auto border-t border-border px-3 py-2.5">
        <Rotulo>{t("painel.sessao")}</Rotulo>
        <div className="mb-2 flex gap-3">
          <div className="flex-1">
            <span className="block font-mono text-[17px] font-bold leading-none text-primary tabular-nums">
              {stats.maos ? Math.round((stats.acertos / stats.maos) * 100) : 0}%
            </span>
            <span className="font-mono text-[8.5px] uppercase tracking-widest-2 text-muted-foreground">
              {t("painel.acerto")}
            </span>
          </div>
          <div className="flex-1">
            <span className="block font-mono text-[17px] font-bold leading-none text-red-400 tabular-nums">
              {stats.bbPerdidos ? `−${stats.bbPerdidos.toFixed(1)}` : "0"}
            </span>
            <span className="font-mono text-[8.5px] uppercase tracking-widest-2 text-muted-foreground">
              {t("painel.bbPerdidos")}
            </span>
          </div>
        </div>
        <div className="grid gap-1">
          {NIVEIS.map((n) => {
            const q = stats.porNivel[n];
            const pct = stats.maos ? (q / stats.maos) * 100 : 0;
            return (
              <div key={n} data-testid={`pratica-nivel-${n}`}
                   className="grid grid-cols-[16px_18px_1fr_auto] items-center gap-1.5 font-mono text-[9.5px] text-muted-foreground">
                {/* a MESMA escala do card do centro, de `SIMBOLO_DO_NIVEL`: duas escalas seriam
                    duas linguagens para a mesma coisa na mesma tela */}
                <span className={cn("text-[10px] leading-none", TEXTO_DA_ESCALA[n])}>
                  {SIMBOLO_DO_NIVEL[n]}
                </span>
                <b className="font-bold text-foreground tabular-nums">{q}</b>
                <i className="block h-1 rounded-sm bg-border">
                  <span className={cn("block h-full rounded-sm", COR_DA_BARRA[n])}
                        style={{ width: `${pct}%` }} />
                </i>
                <span>{t(`nivel.${n}`)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1.5 block font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground/70">
      {children}
    </span>
  );
}

function Seg({ on, onClick, children, testid, esquerda = false, desabilitado = false, titulo }: {
  on: boolean; onClick: () => void; children: React.ReactNode;
  testid?: string; esquerda?: boolean;
  /** A opção existe mas não cabe nesta tela: fica visível e inerte, com o motivo no `title`.
   *  Some-la seria pior -- o jogador no desktop conhece as quatro, e no celular ver a opção
   *  apagada com a frase ao lado explica; ver o seletor encurtar não explica nada. */
  desabilitado?: boolean;
  titulo?: string;
}) {
  return (
    <button type="button" onClick={onClick} data-testid={testid} aria-pressed={on}
            disabled={desabilitado} title={titulo}
            className={cn("flex-1 rounded border py-1 font-mono text-[10.5px] transition-colors",
              esquerda ? "px-2 text-left" : "text-center",
              desabilitado
                ? "cursor-not-allowed border-border/40 text-muted-foreground/35"
                : on ? "border-primary bg-primary font-bold text-background"
                     : "border-border text-muted-foreground hover:text-foreground")}>
      {children}
    </button>
  );
}
