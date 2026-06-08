import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { loadStripe, type Stripe, type StripeElements } from "@stripe/stripe-js";
import { X, Loader2, CreditCard, CheckCircle2, AlertCircle, Zap } from "lucide-react";
import { subscription } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const STRIPE_KEY = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string;

const PLAN_INFO = {
  pro: {
    label: "Pro",
    price: "R$ 99/mês",
    colorClass: "text-primary border-primary/30 bg-primary/5",
    features: [
      "Torneios ilimitados",
      "Análises GrindLab ilimitadas",
      "AI Coach Chat (conversa contextual)",
      "Plano de estudos personalizado",
      "Acesso ao marketplace de coaches",
    ],
  },
} as const;

interface Props {
  plan: "pro";
  onClose: () => void;
  onSuccess?: (newPlan: string) => void;
}

export function CheckoutModal({ plan, onClose, onSuccess }: Props) {
  const { refreshUser } = useAuth();
  const info = PLAN_INFO[plan];

  const [clientSecret,   setClientSecret]   = useState<string | null>(null);
  const [subscriptionId, setSubscriptionId] = useState<string | null>(null);
  const [stripeInstance, setStripeInstance] = useState<Stripe | null>(null);
  const [formMounted,    setFormMounted]     = useState(false);
  const [submitting,     setSubmitting]      = useState(false);
  const [error,          setError]           = useState<string | null>(null);
  const [success,        setSuccess]         = useState(false);

  const elementsRef = useRef<StripeElements | null>(null);

  // Phase 1: load Stripe.js + create subscription intent in parallel
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [intentResult, stripe] = await Promise.all([
          subscription.checkout(plan),
          loadStripe(STRIPE_KEY),
        ]);
        if (!active) return;
        if (!stripe) throw new Error("Falha ao carregar SDK de pagamento.");
        setStripeInstance(stripe);
        setClientSecret(intentResult.client_secret);
        setSubscriptionId(intentResult.subscription_id);
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Erro ao iniciar pagamento.");
      }
    })();
    return () => { active = false; };
  }, [plan]);

  // Phase 2: mount PaymentElement once stripe + clientSecret are ready
  useEffect(() => {
    if (!stripeInstance || !clientSecret) return;
    let active = true;

    elementsRef.current = stripeInstance.elements({
      clientSecret,
      locale: "pt-BR",
      appearance: {
        theme: "night",
        variables: {
          colorPrimary:         "#22c55e",
          colorBackground:      "#0f172a",
          colorText:            "#e2e8f0",
          colorTextSecondary:   "#94a3b8",
          colorDanger:          "#ef4444",
          borderRadius:         "6px",
          fontFamily:           "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSizeBase:         "14px",
          spacingUnit:          "4px",
        },
      },
    });

    const paymentEl = elementsRef.current.create("payment");
    paymentEl.on("ready", () => { if (active) setFormMounted(true); });
    paymentEl.mount("#stripe-payment-element");

    return () => {
      active = false;
      try { paymentEl.unmount(); } catch { /* ignore */ }
      elementsRef.current = null;
    };
  }, [stripeInstance, clientSecret]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripeInstance || !elementsRef.current || !subscriptionId) return;
    setSubmitting(true);
    setError(null);
    try {
      const { error: stripeError, paymentIntent } = await stripeInstance.confirmPayment({
        elements: elementsRef.current,
        redirect: "if_required",
        confirmParams: { return_url: `${window.location.origin}/dashboard` },
      });
      if (stripeError) {
        throw new Error(stripeError.message || "Pagamento recusado.");
      }
      if (paymentIntent?.status === "succeeded") {
        await subscription.activate(plan, paymentIntent.id, subscriptionId);
        setSuccess(true);
        await refreshUser();
        setTimeout(() => { onSuccess?.(plan); onClose(); }, 2500);
      } else {
        throw new Error(`Status inesperado: ${paymentIntent?.status ?? "unknown"}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao processar pagamento.");
    } finally {
      setSubmitting(false);
    }
  };

  const isLoading = !clientSecret && !error;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-hud-surface p-6 shadow-elevated space-y-4 overflow-y-auto max-h-[calc(100vh-2rem)]">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CreditCard className="size-5 text-primary" />
            <h2 className="font-semibold text-foreground">Assinar {info.label}</h2>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors" aria-label="Fechar">
            <X className="size-4" />
          </button>
        </div>

        {/* Plan badge */}
        <div className={cn("rounded-lg border px-4 py-3 space-y-1.5", info.colorClass)}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm font-bold uppercase tracking-wider flex items-center gap-1.5">
              {plan === "pro" && <Zap className="size-3.5" />}
              {info.label}
            </span>
            <span className="font-mono text-sm font-bold">{info.price}</span>
          </div>
          <ul className="space-y-0.5">
            {info.features.map((f) => (
              <li key={f} className="font-mono text-[10px] opacity-75">• {f}</li>
            ))}
          </ul>
        </div>

        {/* Success */}
        {success ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <CheckCircle2 className="size-12 text-primary" />
            <p className="text-sm font-semibold text-foreground text-center">Assinatura ativada com sucesso!</p>
            <p className="text-xs text-muted-foreground text-center">
              Seu plano {info.label} já está disponível. Redirecionando…
            </p>
          </div>

        ) : isLoading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>

        ) : error && !clientSecret ? (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5">
            <AlertCircle className="size-4 shrink-0 text-destructive mt-0.5" />
            <p className="text-xs text-destructive">{error}</p>
          </div>

        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Stripe PaymentElement mounts here — keep always in DOM */}
            <div
              id="stripe-payment-element"
              className={formMounted ? "" : "invisible h-0 overflow-hidden"}
            />

            {!formMounted && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5">
                <AlertCircle className="size-4 shrink-0 text-destructive mt-0.5" />
                <p className="text-xs text-destructive">{error}</p>
              </div>
            )}

            {formMounted && (
              <>
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:opacity-90 disabled:opacity-50"
                >
                  {submitting && <Loader2 className="size-4 animate-spin" />}
                  {submitting ? "Processando…" : `Assinar ${info.label} · ${info.price}`}
                </button>
                <p className="text-center font-mono text-[9px] text-muted-foreground">
                  Pagamento seguro via Stripe · Cancele quando quiser
                </p>
              </>
            )}
          </form>
        )}
      </div>
    </div>,
    document.body
  );
}
