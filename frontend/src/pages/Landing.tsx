import { Link } from "react-router-dom";
import {
  BarChart3, Upload, Brain, TrendingUp, ChevronRight,
  Check, Zap, Shield, BookOpen, Target, Activity,
} from "lucide-react";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";

// ── Helpers ───────────────────────────────────────────────────────────────────

const PLAN_FREE = {
  name: "Free",
  price: "R$ 0",
  period: "/mês",
  highlight: false,
  features: [
    "3 torneios por mês",
    "10 análises IA por mês",
    "Análise de decisões e leaks",
    "Sistema de nível (7 níveis)",
    "Plano de estudos básico",
  ],
  cta: "Começar grátis",
  href: "/login",
};

const PLAN_PRO = {
  name: "Pro",
  price: "R$ 15",
  period: "/mês",
  highlight: true,
  features: [
    "30 torneios por mês",
    "50 análises IA por mês",
    "Plano de estudos personalizado",
    "Histórico completo + evolução",
    "Acesso ao marketplace de coaches",
    "Suporte prioritário",
  ],
  cta: "Assinar Pro",
  href: "mailto:rodrigo.phpro@gmail.com?subject=Assinar%20LeakLabs%20Pro",
};

const HOW_IT_WORKS = [
  {
    step: "01",
    icon: Upload,
    title: "Importe seu histórico",
    desc: "Faça upload do arquivo .txt de qualquer torneio (PokerStars ou GGPoker). Suporte a múltiplos arquivos de uma vez.",
  },
  {
    step: "02",
    icon: Brain,
    title: "LeakLabs prioriza seus erros",
    desc: "Cada decisão é avaliada por equity, posição e contexto MTT/SNG. O motor de detecção cruza frequência com impacto — e te mostra exatamente o que está custando fichas.",
  },
  {
    step: "03",
    icon: TrendingUp,
    title: "Evolua com foco no que importa",
    desc: "Plano de estudos construído sobre os seus próprios padrões de erro — não conteúdo genérico. Acompanhe a evolução pelos 7 níveis do sistema.",
  },
];

const FEATURES = [
  { icon: Target,   title: "Seus dados, não teoria genérica",   desc: "O diagnóstico é construído sobre os seus próprios torneios. Cada leak identificado existe no seu histórico real." },
  { icon: Activity, title: "Prioridade por impacto financeiro",  desc: "Leaks são ranqueados por frequência × gravidade. Você foca no que realmente está custando fichas, não no que é mais fácil de estudar." },
  { icon: BookOpen, title: "Plano de estudos por spot",          desc: "Cards de estudo gerados por spot de erro específico — com diagnóstico, exercício e recursos — não conteúdo genérico." },
  { icon: Shield,   title: "Contexto MTT nativo",               desc: "M-ratio, pressão ICM, estágio do torneio, posição — o motor avalia cada decisão com o contexto certo, não equity isolada." },
  { icon: Brain,    title: "Replayer com análise de decisão",    desc: "Revisão mão a mão com explicação detalhada de cada ação crítica — entenda o que errou e por quê." },
  { icon: BarChart3,title: "Progressão mensurável",              desc: "7 níveis de evolução com métricas claras. Você sabe exatamente onde está e o que falta para avançar." },
];

const LEVELS = ["Iniciante", "Estudante", "Grinder", "Regular", "Sólido", "Expert", "Elite"] as const;

// ── Subcomponents ─────────────────────────────────────────────────────────────

function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-glow">
            <BarChart3 className="size-4" />
          </span>
          <span className="font-semibold text-foreground tracking-tight">
            LeakLabs<span className="text-primary italic font-light">.ai</span>
          </span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            to="/login"
            className="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors uppercase tracking-widest-2"
          >
            Entrar
          </Link>
          <Link
            to="/login"
            className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Começar grátis <ChevronRight className="size-3" />
          </Link>
        </nav>
      </div>
    </header>
  );
}

function HeroSection() {
  return (
    <section className="relative flex min-h-dvh flex-col items-center justify-center px-6 pt-20 pb-16 text-center overflow-hidden">
      {/* Grid de fundo */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      {/* Glow central */}
      <div className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 size-[500px] rounded-full bg-primary/8 blur-3xl" />

      <div className="relative space-y-6 max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-3 py-1">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" />
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
            Powered by Claude AI
          </span>
        </div>

        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground leading-tight">
          Pare de vazar fichas<br />
          <span className="text-primary">nos mesmos spots.</span>
        </h1>

        <p className="text-base text-muted-foreground max-w-xl mx-auto leading-relaxed">
          O LeakLabs analisa cada decisão do seu histórico de torneios, identifica os padrões de erro mais caros e entrega um plano de estudo baseado nos <em>seus</em> dados reais — não em teoria genérica que todo mundo já conhece.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            to="/login"
            className="flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors shadow-glow"
          >
            Começar grátis <Zap className="size-4" />
          </Link>
          <a
            href="#planos"
            className="flex items-center gap-2 rounded-md border border-border px-5 py-2.5 font-mono text-sm text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
          >
            Ver planos <ChevronRight className="size-4" />
          </a>
        </div>

        {/* Níveis mini-preview */}
        <div className="flex items-center justify-center gap-2 pt-4">
          {LEVELS.map((lvl) => {
            const Icon = LEVEL_ICONS[lvl];
            return (
              <div key={lvl} title={lvl} className="flex flex-col items-center gap-1 opacity-60 hover:opacity-100 transition-opacity">
                {Icon && <Icon size={16} className="text-primary" />}
                <span className="font-mono text-[8px] text-muted-foreground hidden sm:block">{lvl}</span>
              </div>
            );
          })}
        </div>
        <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
          7 níveis de evolução — de Iniciante a Elite
        </p>
      </div>
    </section>
  );
}

function StatsSection() {
  const stats = [
    { value: "100+",  label: "Spots de leak mapeados" },
    { value: "7",     label: "Níveis de progressão" },
    { value: "100%",  label: "Baseado nos seus dados reais" },
  ];
  return (
    <section className="border-y border-border bg-hud-surface/50 py-10">
      <div className="mx-auto max-w-4xl px-6">
        <div className="grid grid-cols-3 gap-6 text-center">
          {stats.map((s) => (
            <div key={s.label}>
              <p className="text-3xl font-bold text-primary">{s.value}</p>
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HowItWorksSection() {
  return (
    <section className="py-24 px-6">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">Como funciona</p>
          <h2 className="text-2xl font-bold text-foreground">Do arquivo HH ao diagnóstico preciso</h2>
        </div>
        <div className="grid sm:grid-cols-3 gap-8">
          {HOW_IT_WORKS.map((item) => (
            <div key={item.step} className="relative rounded-xl border border-border bg-hud-surface p-6 space-y-4">
              <span className="font-mono text-4xl font-bold text-primary/15 absolute top-4 right-5 select-none">
                {item.step}
              </span>
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <item.icon className="size-5" />
              </div>
              <h3 className="font-semibold text-foreground">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FeaturesSection() {
  return (
    <section className="py-24 px-6 bg-hud-surface/30">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">Funcionalidades</p>
          <h2 className="text-2xl font-bold text-foreground">Por que o LeakLabs é diferente</h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-hud-surface p-5 space-y-3 hover:border-primary/40 transition-colors">
              <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="size-4.5" />
              </div>
              <h3 className="font-medium text-foreground text-sm">{f.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PricingSection() {
  return (
    <section id="planos" className="py-24 px-6">
      <div className="mx-auto max-w-3xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">Planos</p>
          <h2 className="text-2xl font-bold text-foreground">Simples e transparente</h2>
          <p className="text-sm text-muted-foreground mt-2">Comece grátis. Faça upgrade quando precisar de mais.</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-6">
          {[PLAN_FREE, PLAN_PRO].map((plan) => (
            <div
              key={plan.name}
              className={`rounded-xl border p-6 space-y-6 ${
                plan.highlight
                  ? "border-primary/60 bg-primary/5 shadow-glow"
                  : "border-border bg-hud-surface"
              }`}
            >
              {plan.highlight && (
                <div className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2.5 py-0.5">
                  <Zap className="size-3 text-primary" />
                  <span className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">Recomendado</span>
                </div>
              )}
              <div>
                <p className="font-mono text-xs uppercase tracking-widest-2 text-muted-foreground">{plan.name}</p>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className="text-3xl font-bold text-foreground">{plan.price}</span>
                  <span className="font-mono text-xs text-muted-foreground">{plan.period}</span>
                </div>
              </div>
              <ul className="space-y-2.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <Check className="size-4 text-primary shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>
              <a
                href={plan.href}
                className={`flex items-center justify-center gap-1.5 w-full rounded-md py-2.5 font-mono text-xs font-bold uppercase tracking-widest-2 transition-colors ${
                  plan.highlight
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "border border-border text-muted-foreground hover:text-foreground hover:border-primary/50"
                }`}
              >
                {plan.cta} <ChevronRight className="size-3.5" />
              </a>
            </div>
          ))}
        </div>
        <p className="text-center font-mono text-[10px] text-muted-foreground mt-6">
          Plano Pro em v1 ativado manualmente via e-mail em até 24h.
        </p>
      </div>
    </section>
  );
}

function CtaSection() {
  return (
    <section className="py-24 px-6 border-t border-border">
      <div className="mx-auto max-w-xl text-center space-y-6">
        <h2 className="text-2xl font-bold text-foreground">
          Seus leaks já existem. Você só não sabe quais são.
        </h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Importe seu primeiro torneio agora — em minutos você vai saber exatamente onde está perdendo fichas.
        </p>
        <Link
          to="/login"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors shadow-glow"
        >
          Criar conta grátis <Zap className="size-4" />
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border bg-hud-surface/30 py-8 px-6">
      <div className="mx-auto max-w-6xl flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <BarChart3 className="size-3.5" />
          </span>
          <span className="font-semibold text-sm text-foreground">
            LeakLabs<span className="text-primary italic font-light">.ai</span>
          </span>
        </div>
        <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
          © 2026 LeakLabs · Tactical Tournament Intelligence
        </p>
        <Link
          to="/login"
          className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors uppercase tracking-widest-2"
        >
          Entrar →
        </Link>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Landing() {
  return (
    <div className="min-h-dvh bg-background hud-scanline text-foreground">
      <Navbar />
      <HeroSection />
      <StatsSection />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <CtaSection />
      <Footer />
    </div>
  );
}
