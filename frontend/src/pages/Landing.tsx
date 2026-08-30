import { useEffect, useState } from "react";
import { subscription } from "@/lib/api";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Vitrine, type BlocoVitrine } from "@/components/landing/Vitrine";
import {
  Upload, Brain, TrendingUp, ChevronRight,
  Check, Zap, BookOpen, Target, Activity, HelpCircle,
  ClipboardCheck, Sigma, RotateCcw, Sparkles, ChevronDown,
} from "lucide-react";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";
import { SiteLogo } from "@/components/hud/SiteLogo";
import { HandExportGuide } from "@/components/hud/HandExportGuide";
import { SampleDecisionCard } from "@/components/hud/SampleDecisionCard";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

/**
 * LANDING DESLOGADA — remodelada 2026-08-03 sobre uma referência de layout do usuário.
 *
 * ── O problema que a remodelagem resolve ──────────────────────────────────────────────────────
 *
 * Da faixa de redes até os planos, a página tinha UM ritmo repetido três vezes: `HowItWorks`,
 * `Diferencial` e `Features` eram a mesma coisa — grade de 3 cards, cada um com ícone num quadrado
 * de 40px, título e parágrafo, mesmo `py-24`, mesmo cabeçalho centralizado, duas delas com o mesmo
 * fundo. Quem rolava via o mesmo bloco três vezes e parava de ler.
 *
 * Agora cada seção tem uma DENSIDADE própria: grade de fio de cabelo (processo) → lista numerada
 * com filetes (argumento, ritmo de leitura) → cards leves com cantos táticos (varredura).
 *
 * ── O que da referência NÃO foi copiado, e por quê ────────────────────────────────────────────
 *
 * A referência trazia afirmações que este produto não sustenta, e copiá-las seria repetir uma
 * cicatriz que já está registrada aqui: esta mesma landing já exibiu um selo **AES-256 sem uma
 * linha de cifragem por trás**.
 *
 *   • "1.4M mãos analisadas" / "42 padrões de leak"  → número que não temos como provar;
 *   • "4 sites: PokerStars, GG, 888, Party"          → 888 e Party estão DESLIGADOS (foco PS/GG,
 *                                                      mais ACR e CoinPoker);
 *   • "criptografia AES-256"                         → a cicatriz acima;
 *   • "~3 min do upload ao diagnóstico"              → não medido;
 *   • R$ 79 / R$ 199 e um terceiro plano             → os planos reais são Free e Pro R$ 99;
 *   • marca LeakLabs.ai e links para `/dashboard`    → é GrindLab, e as rotas são `/login` e `/demo`.
 *
 * O que ficou é o LAYOUT e a linguagem visual (fio de cabelo, mono em caixa alta, ponto de status,
 * cantos táticos, caixa de CTA com brilho), com o conteúdo verdadeiro que já existia.
 *
 * Zero chave de i18n nova: a remodelagem é visual e reusa toda a copy que já estava nas 3 locales.
 */

const LEVELS = ["Iniciante", "Estudante", "Grinder", "Regular", "Sólido", "Expert", "Elite"] as const;

/**
 * As redes que a landing MOSTRA. Exportada porque a frase abaixo da faixa também as lista, em
 * prosa e em três idiomas — duas fontes para o mesmo fato.
 *
 * Elas já divergiram: os chips mostravam CoinPoker e a frase dizia "PokerStars, GGPoker e ACR
 * (WPN)". Quem lia a frase concluía que a rede não era suportada. `landingNetworks.test.ts` exige
 * que a copy cubra esta lista nas três locales, então acrescentar rede aqui e esquecer o texto
 * passa a quebrar o teste em vez de virar informação errada na página.
 */
/** `name` é o que a faixa desenha; `token` é o que a copy PRECISA mencionar (sem a pontuação,
 *  que muda de idioma para idioma). */
export const LANDING_NETWORKS = [
  { site: "pokerstars", name: "PokerStars", token: "PokerStars" },
  { site: "ggpoker",    name: "GGPoker",    token: "GGPoker" },
  { site: "acr",        name: "ACR (WPN)",  token: "ACR" },
  { site: "coinpoker",  name: "CoinPoker",  token: "CoinPoker", isNew: true },
] as const;

// ── Subcomponents ─────────────────────────────────────────────────────────────

function Navbar() {
  const { t } = useTranslation("landing");
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="flex items-center">
          <img src={logoHorizontal} alt="GrindLab" className="h-12 w-auto" />
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            to="/login"
            className="inline-flex items-center py-2 font-mono text-xs text-prose-fg hover:text-foreground transition-colors uppercase tracking-widest-2"
          >
            {t("nav.login")}
          </Link>
          <Link
            to="/login"
            className="hidden sm:flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            {t("nav.startFree")} <ChevronRight className="size-3" />
          </Link>
        </nav>
      </div>
    </header>
  );
}

/**
 * Hero em DUAS COLUNAS: a promessa à esquerda, a análise real à direita.
 *
 * O anterior era `min-h-dvh` com um bloco de 349px centralizado: numa janela de 1280x720 sobravam
 * 371px vazios (52% da primeira tela) e o texto ocupava 45% da largura. Pior que o vazio: a
 * primeira evidência do produto ficava a **2,3 telas** de distância, então a página pedia
 * confiança antes de mostrar qualquer coisa.
 *
 * O card à direita é o mesmo Decision Card do produto, com dados de uma mão REAL. A referência
 * punha ali um mock com números inventados; o nosso é mais forte justamente por não ser mock.
 */
function HeroSection() {
  const { t } = useTranslation("landing");
  const bullets = [t("demo.b1"), t("demo.b2"), t("demo.b3")];
  return (
    <section className="relative overflow-hidden border-b border-border px-6 pt-28 pb-16">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(60% 80% at 50% -10%, hsl(var(--primary) / 0.14), transparent 70%)" }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div className="space-y-6 text-center lg:text-left">
          {/* Pílula + linha de status com ponto pulsando: as duas assinaturas do HUD. A pílula diz
              o que move o produto, a linha diz que ele está VIVO — antes de qualquer promessa. */}
          <div className="flex flex-col items-center gap-3 lg:items-start">
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
              <Sparkles className="size-3" aria-hidden />
              {t("hero.badge")}
            </span>
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
              <span className="size-1.5 shrink-0 rounded-full bg-primary animate-pulse" aria-hidden />
              {t("hero.eyebrow")}
            </div>
          </div>

          {/* leading TAMBÉM nas variantes: text-5xl/6xl trazem line-height 1 embutido e, por
              virem na camada do breakpoint, ganhavam do leading base — medido vivo: 60/60. */}
          <h1 className="font-heading text-4xl font-bold leading-[1.06] tracking-tight text-foreground sm:text-5xl sm:leading-[1.06] md:text-6xl md:leading-[1.06]">
            {t("hero.title1")}<br />
            <span className="text-primary">{t("hero.title2")}</span>
          </h1>
          <p className="mx-auto max-w-xl text-base leading-relaxed text-prose-fg lg:mx-0">
            {t("hero.subtitle")}
          </p>

          <ul className="mx-auto max-w-md space-y-2 lg:mx-0">
            {bullets.map((b) => (
              <li key={b} className="flex gap-2.5 text-sm text-foreground/90">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span className="leading-snug text-left">{b}</span>
              </li>
            ))}
          </ul>

          <div className="flex flex-col items-center gap-3 pt-1 sm:flex-row lg:justify-start">
            <Link
              to="/login"
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-6 py-3.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground shadow-glow transition-colors hover:bg-primary/90 sm:w-auto"
            >
              {t("hero.ctaStart")} <Zap className="size-4" />
            </Link>
            {/* Leva ao produto POVOADO, não a um exemplo de uma mão. É a coisa mais forte que
                temos para mostrar a quem ainda não tem dado nenhum. */}
            <Link
              to="/demo"
              className="flex w-full items-center justify-center gap-2 rounded-md border border-border bg-hud-surface px-6 py-3.5 font-mono text-sm text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground sm:w-auto"
            >
              {t("hero.ctaDemo")} <ChevronRight className="size-4" />
            </Link>
          </div>

          {/* Responde as três objeções antes de elas nascerem. A terceira é vantagem direta sobre
              concorrente que só roda em desktop. */}
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground/70">
            {t("hero.risco")}
          </p>
        </div>

        <SampleDecisionCard />
      </div>
    </section>
  );
}

/**
 * A faixa logo abaixo do hero, em FIO DE CABELO (`gap-px` sobre `bg-border`).
 *
 * A referência usava esta batida visual para uma tira de estatísticas ("1.4M mãos", "42 padrões").
 * Aqui ela carrega as REDES SUPORTADAS, que é o fato equivalente que sabemos ser verdade — e que
 * responde a primeira pergunta de quem chega: "dá pra importar de onde eu jogo?".
 */
function SupportedNetworksSection() {
  const { t } = useTranslation("landing");
  const { t: to } = useTranslation("onboarding");
  const [showGuide, setShowGuide] = useState(false);
  return (
    <section className="border-b border-border bg-hud-surface/30">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          {/* h3, não h2: é rótulo de faixa, não título de seção — como h2 de 18px ele quebrava
              a escala (as seções reais são 30px, o fechamento 36px). Avaliação de 06/08, item 3. */}
          <h3 className="font-heading text-lg font-bold text-foreground">{t("networks.heading")}</h3>
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("networks.eyebrow")}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-4">
          {LANDING_NETWORKS.map((n) => {
            const novo = (n as { isNew?: boolean }).isNew;
            return (
              <div key={n.site} className="flex items-center gap-3 bg-background px-5 py-4">
                <SiteLogo site={n.site} size={26} />
                <span className="flex-1 truncate font-mono text-sm font-bold text-foreground">{n.name}</span>
                {novo && (
                  <span className="rounded-sm bg-primary/15 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest-2 text-primary">
                    {t("networks.new")}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-5 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm leading-relaxed text-prose-fg">{t("networks.subtitle")}</p>
          <button
            type="button"
            onClick={() => setShowGuide(true)}
            className="inline-flex shrink-0 items-center gap-1.5 py-1.5 text-xs font-medium text-primary underline-offset-4 transition-colors hover:text-primary-glow hover:underline"
          >
            <HelpCircle className="size-3.5" aria-hidden />
            {to("exportGuide.trigger")}
          </button>
        </div>
      </div>
      <HandExportGuide open={showGuide} onClose={() => setShowGuide(false)} />
    </section>
  );
}

/** PROCESSO — grade de fio de cabelo. Densa e larga: lê-se de relance, que é o que um "como
 *  funciona" precisa. É o primeiro dos três ritmos. */
function HowItWorksSection() {
  const { t } = useTranslation("landing");
  const steps = [
    { step: "01", icon: Upload,     title: t("howItWorks.step1Title"), desc: t("howItWorks.step1Desc"), levels: false },
    { step: "02", icon: Brain,      title: t("howItWorks.step2Title"), desc: t("howItWorks.step2Desc"), levels: false },
    { step: "03", icon: TrendingUp, title: t("howItWorks.step3Title"), desc: t("howItWorks.step3Desc"), levels: true },
  ];
  return (
    <section id="como-funciona" className="scroll-mt-16 px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            {t("howItWorks.heading")}
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("howItWorks.eyebrow")}
          </span>
        </div>

        <ol className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-border bg-border shadow-elevated sm:grid-cols-3">
          {steps.map((item) => (
            <li key={item.step} className="bg-hud-surface p-6 transition-colors hover:bg-hud-surface-elevated">
              <div className="mb-4 flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold tracking-widest-2 text-primary">{item.step}</span>
                <item.icon className="size-4 text-primary/60" aria-hidden />
              </div>
              <h3 className="text-sm font-semibold text-foreground">{item.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-prose-fg">{item.desc}</p>
              {item.levels && (
                <div className="mt-4 border-t border-border/60 pt-3">
                  <div className="flex items-center justify-between gap-1">
                    {LEVELS.map((lvl) => {
                      const Icon = LEVEL_ICONS[lvl];
                      return (
                        <div key={lvl} title={lvl} className="opacity-70">
                          {Icon && <Icon size={15} className="text-primary" />}
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-2 font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
                    {t("howItWorks.levels")}
                  </p>
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/**
 * O DIFERENCIAL. Vem logo depois do exemplo e antes das features, que é onde a pergunta nasce:
 * o visitante acabou de ver uma análise real e pensa "e por que você, se eu já uso um trainer?".
 * Enterrar isto depois das features genéricas seria responder tarde.
 *
 * As três afirmações foram conferidas no código antes de irem para a tela, e não é zelo abstrato:
 * esta mesma landing exibia um selo "AES-256" sem uma linha de cifragem por trás.
 *   • "mede no seu jogo"         → `_category_error_counts` compara as mãos importadas contra o
 *                                  histórico anterior ao baseline (repositories.py);
 *   • "só afirma quando resiste" → `validate_leak` (Wilson + Newcombe + shrinkage, validation.py);
 *   • "reabre sozinho"           → `should_reopen` move o baseline e dispara o sino.
 * Se alguma delas sair do produto, esta seção sai da landing junto.
 *
 * SEGUNDO RITMO: lista numerada com filetes, em duas colunas, com o título fixo à esquerda. É a
 * seção que carrega o argumento mais forte, então ela pede ritmo de LEITURA — não de varredura.
 * Era a terceira grade de 3 cards seguida, e o leitor já tinha desistido antes de chegar aqui.
 */
function DiferencialSection() {
  const { t } = useTranslation("landing");
  const cards = [
    { icon: Activity,  title: t("prova.c1Title"), desc: t("prova.c1Desc") },
    { icon: Sigma,     title: t("prova.c2Title"), desc: t("prova.c2Desc") },
    { icon: RotateCcw, title: t("prova.c3Title"), desc: t("prova.c3Desc") },
  ];
  return (
    <section
      className="border-y border-border bg-hud-surface/40 px-6 py-20"
      aria-labelledby="landing-prova-heading"
    >
      <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[minmax(0,21rem)_1fr] lg:gap-16">
        <div className="space-y-3 lg:sticky lg:top-24 lg:self-start">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
            {t("prova.eyebrow")}
          </p>
          <h2 id="landing-prova-heading" className="font-heading text-2xl font-bold leading-snug text-foreground md:text-3xl">
            {t("prova.heading")}
          </h2>
          <p className="text-sm leading-relaxed text-prose-fg">{t("prova.sub")}</p>
        </div>

        <div>
          <ol className="border-t border-border/70">
            {cards.map((c, i) => (
              <li key={c.title} className="grid grid-cols-[auto_1fr] gap-x-4 border-b border-border/70 py-6">
                <span className="font-mono text-xs font-bold tracking-widest-2 text-primary/60 pt-0.5">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3 className="flex items-center gap-2 font-semibold text-foreground">
                    <c.icon className="size-4 shrink-0 text-primary" aria-hidden />
                    {c.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-prose-fg">{c.desc}</p>
                </div>
              </li>
            ))}
          </ol>

          {/* O fecho é o que separa isto de marketing: diz de onde o número sai. */}
          <p className="mt-6 flex items-start gap-2 text-sm leading-relaxed text-prose-fg">
            <ClipboardCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span>{t("prova.nota")}</span>
          </p>
        </div>
      </div>
    </section>
  );
}

/** TERCEIRO RITMO: cards leves com cantos táticos e elevação no hover. Mais arejado que a grade
 *  de fio de cabelo e mais rápido que a lista — é varredura, que é o papel de uma seção de
 *  funcionalidades. */
function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    { icon: Target,   title: t("features.f1Title"), desc: t("features.f1Desc") },
    { icon: Activity, title: t("features.f2Title"), desc: t("features.f2Desc") },
    { icon: BookOpen, title: t("features.f3Title"), desc: t("features.f3Desc") },
  ];
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            {t("features.heading")}
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("features.eyebrow")}
          </span>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((f) => (
            <article
              key={f.title}
              className="tactical-corners rounded-lg border border-border bg-hud-surface p-6 transition-transform hover:-translate-y-1"
            >
              <f.icon className="size-5 text-primary" aria-hidden />
              <h3 className="mt-5 text-base font-medium text-foreground">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-prose-fg">{f.desc}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function VitrineSection() {
  const { t } = useTranslation("landing");
  // ── Três blocos, e o quarto está de fora por um motivo (28/08) ───────────────────────────
  //
  // Eram quatro, e três apontavam para `/landing/*.webp` com a pasta `public/landing/` inexistente:
  // o componente caía no `onError` e renderizava "captura pendente" com o caminho do arquivo. Isso
  // foi para o ar -- o `main-*.js` publicado continha a frase.
  //
  // O bloco 1 não é captura: renderiza o `RangeGrid` de verdade, com dado da carta. Os blocos 2 e
  // 3 agora têm captura real, gerada por `scripts/landing_shots.mjs` a partir de um banco de
  // captura anonimizado (43 screen names de gente real trocados por "Jogador N").
  //
  // A EVOLUÇÃO só entrou depois: o banco de captura sintético tem um torneio só e
  // `/player/career` responde `insufficient_data`. Semear torneios para desenhar uma curva de
  // melhora seria fabricar, numa imagem de marketing, exatamente o número que o produto se
  // recusa a inventar na tela. Ela foi capturada da conta REAL do dono, com 40 torneios, e por
  // isso o recorte começa abaixo da barra de navegação: o handle dele não vai para uma imagem
  // pública. Ver o cabeçalho de `scripts/landing_shots.mjs`.
  //
  // `landingCapturasExistem.test.ts` quebra a build se um `print:` voltar sem o arquivo.
  const blocos: BlocoVitrine[] = [
    { rotulo: t("vitrine.b1.rotulo"), titulo: t("vitrine.b1.titulo"), texto: t("vitrine.b1.texto"),
      bullets: [t("vitrine.b1.b1a"), t("vitrine.b1.b1b")] },
    { rotulo: t("vitrine.b2.rotulo"), titulo: t("vitrine.b2.titulo"), texto: t("vitrine.b2.texto"),
      bullets: [t("vitrine.b2.b2a"), t("vitrine.b2.b2b")], print: "/landing/veredito.webp" },
    { rotulo: t("vitrine.b3.rotulo"), titulo: t("vitrine.b3.titulo"), texto: t("vitrine.b3.texto"),
      bullets: [t("vitrine.b3.b3a"), t("vitrine.b3.b3b")], print: "/landing/treino.webp" },
    { rotulo: t("vitrine.b4.rotulo"), titulo: t("vitrine.b4.titulo"), texto: t("vitrine.b4.texto"),
      bullets: [t("vitrine.b4.b4a"), t("vitrine.b4.b4b")], print: "/landing/evolucao.webp" },
  ];

  return <Vitrine eyebrow={t("vitrine.eyebrow")} heading={t("vitrine.heading")} blocos={blocos} />;
}

/**
 * O vídeo de usabilidade. `null` enquanto ele não existe, e aí a seção inteira não renderiza.
 *
 * A versão anterior renderizava uma moldura tracejada dizendo "vídeo de usabilidade em gravação",
 * e o comentário que a justificava dizia: "vazio silencioso parece proposital". O raciocínio
 * valia para uma preview de desenvolvimento; numa landing pública ele soma com as três "captura
 * pendente" logo acima, e o visitante lê quatro admissões de obra inacabada em sequência.
 *
 * Para ligar: aponte a constante para o arquivo. Só isso.
 */
const VIDEO_DE_USABILIDADE: string | null = null;

function VideoSection() {
  const { t } = useTranslation("landing");
  if (!VIDEO_DE_USABILIDADE) return null;
  return (
    <section className="border-t border-border px-6 py-20">
      <div className="mx-auto max-w-4xl text-center">
        <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
          {t("vitrine.video.heading")}
        </h2>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-prose-fg">{t("vitrine.video.sub")}</p>
        <video
          src={VIDEO_DE_USABILIDADE}
          controls
          preload="metadata"
          className="mt-8 aspect-video w-full rounded-xl border border-border bg-hud-surface"
        />
      </div>
    </section>
  );
}

/** Centavos -> "R$ 39,90". Mesma função do CheckoutModal, de propósito duplicada aqui e não
 *  extraída: são dois bundles (a landing é pública e não carrega o modal). O guarda
 *  `precoNaoEhCravado.test.ts` é quem impede as duas de divergirem, porque impede QUALQUER
 *  literal de moeda nestas telas. */
function brlLanding(centavos: number | undefined | null): string {
  if (centavos == null) return "";
  return (centavos / 100).toLocaleString("pt-BR", {
    style: "currency", currency: "BRL", minimumFractionDigits: 2,
  });
}

function PricingSection() {
  const { t } = useTranslation("landing");
  // ── O preço vem da API (28/08) ────────────────────────────────────────────────────────────
  //
  // Estava `price: "R$ 99"` cravado aqui, ao lado de `PLAN_AMOUNTS` no backend, das traduções do
  // checkout e do preço real no Stripe: CINCO fontes para o mesmo fato. No dia em que o dono
  // baixou o Pro para R$39,90, mudar só uma delas faria o site anunciar um valor e o cartão ser
  // debitado de outro.
  //
  // `/subscription/plans` é público (sem login), então a landing lê da mesma fonte que o
  // checkout. Enquanto não chega, o card mostra o plano SEM preço -- número provisório numa
  // página de vendas é pior que número ausente.
  const [precos, setPrecos] = useState<{ mensal?: number; anual?: number; economia?: number;
                                        meses?: number } | null>(null);
  useEffect(() => {
    let vivo = true;
    subscription.plans()
      .then((r) => {
        if (!vivo) return;
        const pro = (r.plans || []).find((p) => p.id === "pro");
        const a = pro?.billing?.annual;
        setPrecos({
          mensal:   pro?.billing?.monthly?.price,
          anual:    a?.price,
          economia: a ? a.full_price - a.price : undefined,
          meses:    a?.months_free,
        });
      })
      .catch(() => { /* sem preço, e não um preço errado */ });
    return () => { vivo = false; };
  }, []);
  const plans = [
    {
      id: "free",
      name: "Free",
      price: t("plans.gratis"),
      period: t("plans.period"),
      highlight: false,
      badge: null as string | null,
      features: [t("plans.freeF1"), t("plans.freeF2"), t("plans.freeF3"), t("plans.freeF4"), t("plans.freeF5")],
      cta: t("plans.ctaFree"),
      href: "/login",
    },
    {
      id: "pro",
      name: "Pro",
      price: brlLanding(precos?.mensal),
      period: t("plans.period"),
      highlight: true,
      badge: t("plans.grinder") as string | null,
      // proF5 (marketplace) fora por decisao do dono em 30/08: some da vitrine ate o
      // marketplace ter trilha propria de valor.
      features: [t("plans.proF1"), t("plans.proF2"), t("plans.proF7"), t("plans.proF8"), t("plans.proF3"), t("plans.proF4"), t("plans.proF6")],
      cta: t("plans.ctaSubscribe", { name: "Pro" }),
      // Era um `mailto:` para o e-mail pessoal do dono — sobra de quando a assinatura ainda não
      // existia. Desde 2026-06-17 o Stripe está no ar, e o botão mandava o interessado escrever
      // um e-mail em vez de assinar: o pior lugar possível para perder alguém que já decidiu
      // pagar. De quebra, publicava um endereço pessoal na landing.
      //
      // `?next=` porque `/subscription` exige login: sem ele o visitante cai no login e a
      // intenção de assinar se perde no caminho.
      href: "/login?next=%2Fsubscription",
    },
  ];
  return (
    <section id="planos" className="border-y border-border bg-hud-surface/40 px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <div>
            <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
              {t("plans.heading")}
            </h2>
            <p className="mt-2 text-sm text-prose-fg">{t("plans.details")}</p>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("plans.eyebrow")}
          </span>
        </div>

        <div className="mx-auto grid max-w-3xl gap-6 sm:grid-cols-2">
          {plans.map((plan) => (
            <article
              key={plan.id}
              className={`flex flex-col rounded-xl border bg-background p-6 ${
                plan.highlight ? "border-primary/50 shadow-glow" : "border-border"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
                  {plan.name}
                </span>
                {plan.badge && (
                  <span className="inline-flex items-center gap-1 rounded-sm bg-primary/15 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest-2 text-primary">
                    {plan.highlight && <Zap className="size-2.5" aria-hidden />}
                    {plan.badge}
                  </span>
                )}
              </div>
              <div className="mt-5 flex items-baseline gap-1.5">
                <span className="text-3xl font-semibold text-foreground">{plan.price}</span>
                <span className="font-mono text-xs text-muted-foreground">{plan.period}</span>
              </div>
              <ul className="mt-6 flex-1 space-y-2.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-prose-fg">
                    <Check className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
                    {f}
                  </li>
                ))}
              </ul>
              {/* `Link`, e não `<a href>`: os dois planos apontam para dentro do app desde que o
                  `mailto:` saiu daqui. Com âncora, assinar recarregava a página inteira — e o
                  destino escapava da varredura de links internos (`routeLinks.test.ts`). */}
              <Link
                to={plan.href}
                className={`mt-7 inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors ${
                  plan.highlight
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "border border-border text-foreground hover:border-primary/40 hover:text-primary"
                }`}
              >
                {plan.cta} <ChevronRight className="size-3" />
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/**
 * FAQ — as objeções logo ANTES do pedido, que é onde elas nascem: o visitante acabou de ver o
 * preço e a próxima coisa que ele faz é procurar o motivo para não começar.
 *
 * `<details>`/`<summary>` nativos de propósito: abre e fecha sem JavaScript, é navegável por
 * teclado e lido por leitor de tela sem nenhum `aria-*` escrito à mão. Um acordeão em estado de
 * React aqui seria mais código para entregar menos.
 *
 * **Toda resposta foi conferida no código antes de virar texto**, e não é zelo abstrato: esta
 * landing já exibiu um selo "AES-256" sem uma linha de cifragem por trás. O que sustenta cada uma:
 *   • redes    → `LANDING_NETWORKS` e o parser (PS/GG/ACR/CoinPoker); o resumo do torneio é o que
 *                habilita colocação, prêmio, ROI e detecção de mesa final;
 *   • solver   → o gabarito sai de solve próprio, e o produto o aplica às mãos do jogador;
 *   • "não é chute" → `validate_leak` (intervalo de confiança) e `should_reopen`, os mesmos que
 *                sustentam a seção do diferencial;
 *   • plano Free → os limites são os de `plans.freeF1..F4`, na mesma página;
 *   • cash game  → o motor é de torneio (`mtt_context.py`: ICM, M-ratio, estágio, bolha), então a
 *                resposta diz o que ele É, sem prometer cash para depois.
 *
 * A pergunta sobre DADOS ficou de fora de propósito. A única resposta completa teria de falar do
 * acervo compartilhado do modo grind, e o aviso sobre isso foi removido do produto por decisão do
 * usuário — reintroduzi-lo aqui seria contrariar essa decisão pela porta dos fundos.
 */
/** Quantos pares q/a a seção desenha. Exportado porque falta de chave NÃO quebra o i18next: ele
 *  imprime a chave crua ("faq.q7") na tela. `landingFaq.test.ts` cobra as 3 locales contra este
 *  número, então o modo de falha vira teste vermelho em vez de texto quebrado na página. */
export const FAQ_COUNT = 6;

function FaqSection() {
  const { t } = useTranslation("landing");
  const perguntas = Array.from({ length: FAQ_COUNT }, (_, k) => k + 1).map((i) => ({
    q: t(`faq.q${i}`),
    a: t(`faq.a${i}`),
  }));
  return (
    <section id="faq" className="px-6 py-20">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            {t("faq.heading")}
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("faq.eyebrow")}
          </span>
        </div>

        <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-hud-surface">
          {perguntas.map((f) => (
            <details key={f.q} className="group px-5 py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium text-foreground transition-colors hover:text-primary">
                {f.q}
                <ChevronDown
                  className="size-4 shrink-0 text-primary transition-transform group-open:rotate-180"
                  aria-hidden
                />
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-prose-fg">{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

/** CTA final em caixa com brilho radial — a batida de fecho da referência. Sozinha no fim da
 *  página, ela recupera a atenção de quem rolou até aqui sem clicar. */
function CtaSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="mx-auto max-w-6xl px-6 py-20">
      <div className="relative overflow-hidden rounded-xl border border-primary/30 bg-primary/5 p-8 text-center md:p-12">
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(60% 100% at 50% 0%, hsl(var(--primary) / 0.16), transparent 70%)" }}
          aria-hidden
        />
        <h2 className="relative font-heading text-2xl font-bold tracking-tight text-foreground md:text-4xl">
          {t("cta.heading")}
        </h2>
        <p className="relative mx-auto mt-4 max-w-xl text-sm leading-relaxed text-prose-fg">
          {t("cta.desc")}
        </p>
        <Link
          to="/login"
          className="relative mt-8 inline-flex items-center gap-2 rounded-md bg-primary px-7 py-3.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground shadow-glow transition-colors hover:bg-primary/90"
        >
          {t("cta.btn")} <Zap className="size-4" />
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  const { t } = useTranslation("landing");
  return (
    <footer className="border-t border-border bg-hud-surface/30">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row">
        <img src={logoHorizontal} alt="GrindLab Poker" className="h-7 w-auto" />
        <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {t("footer.copyright")}
        </p>
        <div className="flex items-center gap-4">
          {/* py-2: alvo de toque ≥24px (WCAG 2.2) — os links tinham 15px de altura no vivo. */}
          <Link
            to="/privacidade"
            className="inline-flex items-center py-2 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("footer.privacy")}
          </Link>
          <Link
            to="/termos"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("footer.termos")}
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center py-2 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("footer.login")}
          </Link>
        </div>
      </div>
    </footer>
  );
}

export default function Landing() {
  return (
    <div id="top" className="min-h-dvh bg-background hud-scanline text-foreground">
      <Navbar />
      <main>
        <HeroSection />
        <SupportedNetworksSection />
        <HowItWorksSection />
        <DiferencialSection />
        <FeaturesSection />
      <VideoSection />
      <VitrineSection />
        <PricingSection />
        <FaqSection />
        <CtaSection />
      </main>
      <Footer />
    </div>
  );
}
