import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Upload, Brain, TrendingUp, ChevronRight,
  Check, Zap, BookOpen, Target, Activity, HelpCircle,
} from "lucide-react";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";
import { SiteLogo } from "@/components/hud/SiteLogo";
import { HandExportGuide } from "@/components/hud/HandExportGuide";
import { SampleDecisionCard } from "@/components/hud/SampleDecisionCard";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";

const LEVELS = ["Iniciante", "Estudante", "Grinder", "Regular", "Sólido", "Expert", "Elite"] as const;

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
            className="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors uppercase tracking-widest-2"
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

function HeroSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="relative flex min-h-dvh flex-col items-center justify-center px-6 pt-24 pb-16 text-center overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      <div className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 size-[520px] rounded-full bg-primary/8 blur-3xl" />

      <div className="relative mx-auto max-w-3xl space-y-6">
        <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
          {t("hero.eyebrow")}
        </p>
        <h1 className="font-heading text-4xl sm:text-6xl font-bold tracking-tight text-foreground leading-[1.05]">
          {t("hero.title1")}<br />
          <span className="text-primary">{t("hero.title2")}</span>
        </h1>
        <p className="text-base sm:text-lg text-muted-foreground max-w-xl mx-auto leading-relaxed">
          {t("hero.subtitle")}
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
          <Link
            to="/login"
            className="flex items-center gap-2 rounded-md bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors shadow-glow"
          >
            {t("hero.ctaStart")} <Zap className="size-4" />
          </Link>
          <a
            href="#exemplo"
            className="flex items-center gap-2 rounded-md border border-border px-6 py-3 font-mono text-sm text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
          >
            {t("hero.ctaSample")} <ChevronRight className="size-4" />
          </a>
        </div>
      </div>
    </section>
  );
}

function SupportedNetworksSection() {
  const { t } = useTranslation("landing");
  const { t: to } = useTranslation("onboarding");
  const [showGuide, setShowGuide] = useState(false);
  const NETWORKS = [
    { site: "pokerstars", name: "PokerStars" },
    { site: "ggpoker",    name: "GGPoker" },
    { site: "acr",        name: "ACR (WPN)" },
    { site: "coinpoker",  name: "CoinPoker", isNew: true },
  ];
  return (
    <section className="border-y border-border/50 bg-hud-surface/30 py-12 px-6">
      <div className="mx-auto max-w-4xl text-center">
        <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("networks.eyebrow")}</p>
        <h2 className="font-heading text-xl font-bold text-foreground">{t("networks.heading")}</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground leading-relaxed">{t("networks.subtitle")}</p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
          {NETWORKS.map((n) => (
            <div key={n.site}
              className={`inline-flex items-center gap-2.5 rounded-full border px-4 py-2 ${
                (n as { isNew?: boolean }).isNew ? "border-primary/40 bg-primary/[0.06]" : "border-border bg-hud-surface"}`}>
              <SiteLogo site={n.site} size={24} />
              <span className="font-mono text-sm font-bold text-foreground">{n.name}</span>
              {(n as { isNew?: boolean }).isNew && (
                <span className="rounded-full bg-primary px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-primary-foreground">
                  {t("networks.new")}
                </span>
              )}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setShowGuide(true)}
          className="mt-6 inline-flex items-center gap-1.5 text-xs font-medium text-primary transition-colors hover:text-primary-glow underline-offset-4 hover:underline"
        >
          <HelpCircle className="size-3.5" aria-hidden />
          {to("exportGuide.trigger")}
        </button>
      </div>
      <HandExportGuide open={showGuide} onClose={() => setShowGuide(false)} />
    </section>
  );
}

function HowItWorksSection() {
  const { t } = useTranslation("landing");
  const steps = [
    { step: "01", icon: Upload,     title: t("howItWorks.step1Title"), desc: t("howItWorks.step1Desc"), levels: false },
    { step: "02", icon: Brain,      title: t("howItWorks.step2Title"), desc: t("howItWorks.step2Desc"), levels: false },
    { step: "03", icon: TrendingUp, title: t("howItWorks.step3Title"), desc: t("howItWorks.step3Desc"), levels: true },
  ];
  return (
    <section id="como-funciona" className="py-24 px-6 scroll-mt-16">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("howItWorks.eyebrow")}</p>
          <h2 className="font-heading text-2xl font-bold text-foreground">{t("howItWorks.heading")}</h2>
        </div>
        <div className="grid sm:grid-cols-3 gap-8">
          {steps.map((item) => (
            <div key={item.step} className="relative rounded-xl border border-border bg-hud-surface p-6 space-y-4">
              <span className="font-mono text-4xl font-bold text-primary/15 absolute top-4 right-5 select-none">
                {item.step}
              </span>
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <item.icon className="size-5" />
              </div>
              <h3 className="font-semibold text-foreground">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              {item.levels && (
                <div className="pt-1">
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
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function LandingDemoSection() {
  const { t } = useTranslation("landing");
  const bullets = [t("demo.b1"), t("demo.b2"), t("demo.b3")];
  return (
    <section id="exemplo" className="py-24 px-6 scroll-mt-16" aria-labelledby="landing-demo-heading">
      <div className="mx-auto grid max-w-5xl items-center gap-10 lg:grid-cols-2">
        <div className="order-2 lg:order-1">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("demo.eyebrow")}</p>
          <h2 id="landing-demo-heading" className="font-heading text-2xl font-bold text-foreground">{t("demo.heading")}</h2>
          <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{t("demo.subtitle")}</p>
          <ul className="mt-6 space-y-3">
            {bullets.map((b) => (
              <li key={b} className="flex gap-3 text-sm text-foreground/90">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span className="leading-snug">{b}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="relative order-1 lg:order-2">
          <span className="absolute -top-2 right-3 z-10 bg-background px-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("demo.seal")}
          </span>
          <SampleDecisionCard />
        </div>
      </div>
    </section>
  );
}

function FeaturesSection() {
  const { t } = useTranslation("landing");
  const features = [
    { icon: Target,    title: t("features.f1Title"), desc: t("features.f1Desc") },
    { icon: Activity,  title: t("features.f2Title"), desc: t("features.f2Desc") },
    { icon: BookOpen,  title: t("features.f3Title"), desc: t("features.f3Desc") },
  ];
  return (
    <section className="py-24 px-6 bg-hud-surface/30">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("features.eyebrow")}</p>
          <h2 className="font-heading text-2xl font-bold text-foreground">{t("features.heading")}</h2>
        </div>
        <div className="grid gap-5 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-hud-surface p-6 space-y-3 hover:border-primary/40 transition-colors">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="size-5" />
              </div>
              <h3 className="font-medium text-foreground">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PricingSection() {
  const { t } = useTranslation("landing");
  const plans = [
    {
      id: "free",
      name: "Freemium",
      price: "R$ 0",
      period: t("plans.period"),
      highlight: false,
      badge: null as string | null,
      features: [t("plans.freeF1"), t("plans.freeF2"), t("plans.freeF3"), t("plans.freeF4")],
      cta: t("plans.ctaFree"),
      href: "/login",
    },
    {
      id: "pro",
      name: "Pro",
      price: "R$ 99",
      period: t("plans.period"),
      highlight: true,
      badge: t("plans.grinder") as string | null,
      features: [t("plans.proF1"), t("plans.proF2"), t("plans.proF7"), t("plans.proF3"), t("plans.proF4"), t("plans.proF5"), t("plans.proF6")],
      cta: t("plans.ctaSubscribe", { name: "Pro" }),
      href: "mailto:rodrigo.phpro@gmail.com?subject=Assinar%20GrindLab%20Pro",
    },
  ];
  return (
    <section id="planos" className="py-24 px-6">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("plans.eyebrow")}</p>
          <h2 className="text-2xl font-bold text-foreground">{t("plans.heading")}</h2>
          <p className="text-sm text-muted-foreground mt-2">{t("plans.details")}</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-5 max-w-3xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`relative rounded-xl border p-6 space-y-5 flex flex-col ${
                plan.highlight
                  ? "border-primary/60 bg-primary/5 shadow-glow"
                  : "border-border bg-hud-surface"
              }`}
            >
              {plan.badge && (
                <div className={`absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 rounded-full px-3 py-0.5 ${
                  plan.highlight ? "bg-primary text-primary-foreground" : "bg-hud-surface border border-border text-muted-foreground"
                }`}>
                  {plan.highlight && <Zap className="size-3" />}
                  <span className="font-mono text-[10px] uppercase tracking-widest-2">{plan.badge}</span>
                </div>
              )}
              <div>
                <p className="font-mono text-xs uppercase tracking-widest-2 text-muted-foreground">{plan.name}</p>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className="text-3xl font-bold text-foreground">{plan.price}</span>
                  <span className="font-mono text-xs text-muted-foreground">{plan.period}</span>
                </div>
              </div>
              <ul className="space-y-2.5 flex-1">
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
      </div>
    </section>
  );
}

function CtaSection() {
  const { t } = useTranslation("landing");
  return (
    <section className="py-24 px-6 border-t border-border">
      <div className="mx-auto max-w-xl text-center space-y-6">
        <h2 className="text-2xl font-bold text-foreground">
          {t("cta.heading")}
        </h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {t("cta.desc")}
        </p>
        <Link
          to="/login"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors shadow-glow"
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
    <footer className="border-t border-border bg-hud-surface/30 py-8 px-6">
      <div className="mx-auto max-w-6xl flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center">
          <img src={logoHorizontal} alt="GrindLab Poker" className="h-7 w-auto" />
        </div>
        <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
          {t("footer.copyright")}
        </p>
        <Link
          to="/login"
          className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors uppercase tracking-widest-2"
        >
          {t("footer.login")}
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
      <SupportedNetworksSection />
      <HowItWorksSection />
      <LandingDemoSection />
      <FeaturesSection />
      <PricingSection />
      <CtaSection />
      <Footer />
    </div>
  );
}
