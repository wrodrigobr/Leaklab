import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  BarChart3, Upload, Brain, TrendingUp, ChevronRight,
  Check, Zap, Shield, BookOpen, Target, Activity,
} from "lucide-react";
import { LEVEL_ICONS } from "@/components/hud/LevelIcons";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import heroEn from "@/assets/brand/grindlab_og_en.png";
import heroEs from "@/assets/brand/grindlab_og_es.png";
import heroPt from "@/assets/brand/grindlab_og_ptbr.png";

// Hero da landing por idioma do usuário (i18n). Base da locale: pt-BR→pt, etc.
const HERO_BY_LANG: Record<string, string> = { en: heroEn, es: heroEs, pt: heroPt };
function heroForLang(lang?: string): string {
  return HERO_BY_LANG[(lang || "en").split("-")[0].toLowerCase()] ?? heroEn;
}

const LEVELS = ["Iniciante", "Estudante", "Grinder", "Regular", "Sólido", "Expert", "Elite"] as const;

// ── Subcomponents ─────────────────────────────────────────────────────────────

function Navbar() {
  const { t } = useTranslation("landing");
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md">
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
  const { t, i18n } = useTranslation("landing");
  const heroBanner = heroForLang(i18n.language);
  return (
    <section className="relative flex min-h-dvh flex-col items-center justify-center px-6 pt-20 pb-16 text-center overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      <div className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 size-[500px] rounded-full bg-primary/8 blur-3xl" />

      <div className="relative space-y-6 max-w-3xl">
        <img
          src={heroBanner}
          alt="GrindLab"
          className="mx-auto w-full max-w-2xl rounded-2xl border border-border/40 shadow-elevated"
        />
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground leading-tight">
          {t("hero.title1")}<br />
          <span className="text-primary">{t("hero.title2")}</span>
        </h1>

        <p className="text-base text-muted-foreground max-w-xl mx-auto leading-relaxed">
          {t("hero.subtitle")}
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            to="/login"
            className="flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors shadow-glow"
          >
            {t("hero.ctaStart")} <Zap className="size-4" />
          </Link>
          <a
            href="#planos"
            className="flex items-center gap-2 rounded-md border border-border px-5 py-2.5 font-mono text-sm text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
          >
            {t("hero.ctaPlans")} <ChevronRight className="size-4" />
          </a>
        </div>

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
          {t("hero.levels")}
        </p>
      </div>
    </section>
  );
}

function StatsSection() {
  const { t } = useTranslation("landing");
  const stats = [
    { value: "100+", label: t("stats.leakSpots") },
    { value: "7",    label: t("stats.levels") },
    { value: "100%", label: t("stats.realData") },
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
  const { t } = useTranslation("landing");
  const steps = [
    { step: "01", icon: Upload,     title: t("howItWorks.step1Title"), desc: t("howItWorks.step1Desc") },
    { step: "02", icon: Brain,      title: t("howItWorks.step2Title"), desc: t("howItWorks.step2Desc") },
    { step: "03", icon: TrendingUp, title: t("howItWorks.step3Title"), desc: t("howItWorks.step3Desc") },
  ];
  return (
    <section className="py-24 px-6">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("howItWorks.eyebrow")}</p>
          <h2 className="text-2xl font-bold text-foreground">{t("howItWorks.heading")}</h2>
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
            </div>
          ))}
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
    { icon: Shield,    title: t("features.f4Title"), desc: t("features.f4Desc") },
    { icon: Brain,     title: t("features.f5Title"), desc: t("features.f5Desc") },
    { icon: BarChart3, title: t("features.f6Title"), desc: t("features.f6Desc") },
  ];
  return (
    <section className="py-24 px-6 bg-hud-surface/30">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-14">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-primary mb-2">{t("features.eyebrow")}</p>
          <h2 className="text-2xl font-bold text-foreground">{t("features.heading")}</h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f) => (
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
        <p className="text-center font-mono text-[10px] text-muted-foreground mt-8">
          {t("plans.manualActivation")}
        </p>
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
      <StatsSection />
      <HowItWorksSection />
      <FeaturesSection />
      <PricingSection />
      <CtaSection />
      <Footer />
    </div>
  );
}
