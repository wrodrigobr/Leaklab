import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Upload, Rocket, ChevronLeft, ChevronRight, X, HelpCircle, Eye, FileUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { auth as authApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { HandExportGuide } from "@/components/hud/HandExportGuide";

// 3 passos orientados à AÇÃO (antes eram 4 slides passivos). O último termina em CTA, não em texto.
const STEPS = ["welcome", "upload", "ready"] as const;
type Step = typeof STEPS[number];

const ICONS: Record<Step, React.ReactNode> = {
  welcome: <Sparkles className="size-10 text-primary" />,
  upload:  <Upload   className="size-10 text-primary" />,
  ready:   <Rocket   className="size-10 text-primary" />,
};

interface Props {
  onClose: () => void;
}

export function OnboardingModal({ onClose }: Props) {
  const { t } = useTranslation("onboarding");
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const current = STEPS[step];
  const isLast  = step === STEPS.length - 1;
  const isFirst = step === 0;

  // completeOnboarding roda em QUALQUER saída (X, Esc, os 2 CTAs) → não reabre no próximo login.
  const complete = async (dest?: "import" | "sample") => {
    if (saving) return;
    setSaving(true);
    try {
      await authApi.completeOnboarding();
      await refreshUser();
    } catch {
      // proceed regardless — onboarding state will sync on next login
    } finally {
      setSaving(false);
    }
    onClose();
    if (dest === "import") navigate("/dashboard");
    else if (dest === "sample") navigate("/dashboard?onboarding=sample");
  };

  // a11y: Esc fecha (= pular) + foco inicial no painel. O modal atual não tinha nenhum dos dois.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") complete(); };
    document.addEventListener("keydown", onKey);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
    <HandExportGuide open={showGuide} onClose={() => setShowGuide(false)} />
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl border border-border bg-hud-surface shadow-elevated flex flex-col focus:outline-none"
      >

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("step", { current: step + 1, total: STEPS.length })}
          </span>
          <button
            onClick={() => complete()}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label={t("skip")}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Step dots */}
        <div className="flex items-center justify-center gap-2 pt-5 px-6">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === step
                  ? "w-6 bg-primary"
                  : i < step
                  ? "w-3 bg-primary/40"
                  : "w-3 bg-border"
              }`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="flex flex-col items-center text-center px-8 py-8 gap-4 flex-1">
          <div className="rounded-2xl bg-primary/10 p-4">
            {ICONS[current]}
          </div>

          <h2 className="text-xl font-bold text-foreground">
            {t(`steps.${current}.title`)}
          </h2>

          <p className="text-sm text-muted-foreground leading-relaxed">
            {t(`steps.${current}.desc`)}
          </p>

          {current === "upload" && (
            <>
              <p className="text-xs text-muted-foreground/70 bg-muted/40 rounded-lg px-4 py-2.5 leading-relaxed">
                {t("steps.upload.hint")}
              </p>
              <button
                type="button"
                onClick={() => setShowGuide(true)}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-primary transition-colors hover:text-primary-glow underline-offset-4 hover:underline"
              >
                <HelpCircle className="size-3.5" aria-hidden />
                {t("exportGuide.trigger")}
              </button>
            </>
          )}
        </div>

        {/* Footer — último passo termina em AÇÃO (2 CTAs), não num "finish" genérico. */}
        {isLast ? (
          <div className="flex flex-col gap-2 px-6 pb-6">
            <button
              onClick={() => complete("import")}
              disabled={saving}
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow disabled:opacity-50"
            >
              <FileUp className="size-4" />
              {t("finishImport")}
            </button>
            <button
              onClick={() => complete("sample")}
              disabled={saving}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-border px-5 text-sm text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
            >
              <Eye className="size-4" />
              {t("finishSample")}
            </button>
            <button
              onClick={() => setStep((s) => s - 1)}
              className="mt-1 inline-flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronLeft className="size-3.5" />
              {t("back")}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3 px-6 pb-6">
            {!isFirst ? (
              <button
                onClick={() => setStep((s) => s - 1)}
                className="inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <ChevronLeft className="size-4" />
                {t("back")}
              </button>
            ) : (
              <button
                onClick={() => complete()}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("skip")}
              </button>
            )}
            <button
              onClick={() => setStep((s) => s + 1)}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow"
            >
              {t("next")}
              <ChevronRight className="size-4" />
            </button>
          </div>
        )}
      </div>
    </div>
    </>
  );
}
