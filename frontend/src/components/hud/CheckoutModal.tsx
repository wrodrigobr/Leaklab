import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X, Loader2, CreditCard, CheckCircle2, AlertCircle, Zap } from "lucide-react";
import { subscription } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

declare global {
  interface Window {
    MercadoPago: new (key: string, opts: { locale: string }) => MpInstance;
  }
}

interface MpInstance {
  cardForm: (config: object) => MpCardForm;
}

interface MpCardForm {
  getCardFormData: () => { token: string };
  unmount: () => void;
}

const MP_PUBLIC_KEY = import.meta.env.VITE_MP_PUBLIC_KEY as string;

const PLAN_INFO = {
  starter: {
    label: "Starter",
    price: "R$ 19/mês",
    amount: "19.00",
    colorClass: "text-blue-400 border-blue-400/30 bg-blue-400/5",
    features: ["10 torneios/mês", "20 análises LeakLabs IA", "Plano de estudo básico"],
  },
  pro: {
    label: "Pro",
    price: "R$ 39/mês",
    amount: "39.00",
    colorClass: "text-primary border-primary/30 bg-primary/5",
    features: ["Torneios ilimitados", "Análises ilimitadas", "Coach IA avançado + ICM"],
  },
} as const;

// PCI-secured fields: MP renders iframe inside — needs relative so absolute-positioned
// iframe is contained correctly; no overflow-hidden to avoid clipping hit-area
const iframeContainerClass =
  "relative h-10 w-full rounded-md border border-border bg-background";

// Non-PCI fields: real HTML elements styled to match
const inputClass =
  "h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

function FieldWrap({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

interface Props {
  plan: "starter" | "pro";
  onClose: () => void;
  onSuccess?: (newPlan: string) => void;
}

export function CheckoutModal({ plan, onClose, onSuccess }: Props) {
  const { refreshUser } = useAuth();
  const [sdkReady, setSdkReady] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const formRef = useRef<MpCardForm | null>(null);
  const info = PLAN_INFO[plan];

  // Load MP SDK script once
  useEffect(() => {
    if (window.MercadoPago) {
      setSdkReady(true);
      return;
    }
    if (document.getElementById("mp-sdk-script")) {
      const check = setInterval(() => {
        if (window.MercadoPago) {
          clearInterval(check);
          setSdkReady(true);
        }
      }, 100);
      return () => clearInterval(check);
    }
    const script = document.createElement("script");
    script.id = "mp-sdk-script";
    script.src = "https://sdk.mercadopago.com/js/v2";
    script.onload = () => setSdkReady(true);
    script.onerror = () => setError("Falha ao carregar SDK de pagamento. Verifique sua conexão.");
    document.head.appendChild(script);
  }, []);

  // Initialize card form after SDK is ready and divs are rendered
  useEffect(() => {
    if (!sdkReady) return;

    // Guard against React strict-mode double-invocation: callbacks from a
    // cleaned-up effect should not update state after unmount.
    let active = true;

    const mp = new window.MercadoPago(MP_PUBLIC_KEY, { locale: "pt-BR" });

    // Estilo para iframes PCI — deve combinar com o tema escuro
    const iframeStyle = {
      color: "#e2e8f0",
      fontSize: "14px",
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      placeholderColor: "#6b7a8d",
    };

    const cardForm = mp.cardForm({
      amount: info.amount,
      iframe: true,
      autoMount: true,
      form: {
        id: "mp-checkout-form",
        cardNumber:           { id: "mp-card-number",           placeholder: "0000 0000 0000 0000", style: iframeStyle },
        expirationDate:       { id: "mp-expiration-date",       placeholder: "MM/AA",               style: iframeStyle },
        securityCode:         { id: "mp-security-code",         placeholder: "CVV",                 style: iframeStyle },
        cardholderName:       { id: "mp-cardholder-name"       },
        identificationType:   { id: "mp-identification-type"   },
        identificationNumber: { id: "mp-identification-number" },
        cardholderEmail:      { id: "mp-cardholder-email"      },
        issuer:               { id: "mp-issuer"                },
        installments:         { id: "mp-installments"          },
      },
      callbacks: {
        onFormMounted: (err: unknown) => {
          if (!active) return;
          // MP passes an array of errors (empty array [] on success, which is truthy — check length)
          const hasError = Array.isArray(err) ? err.length > 0 : !!err;
          if (hasError) setError("Erro ao montar formulário. Recarregue a página.");
        },
        onSubmit: async (event: { preventDefault: () => void }) => {
          event.preventDefault();
          if (!active || !formRef.current) return;
          setSubmitting(true);
          setError(null);
          try {
            const { token, paymentMethodId, issuerId, identificationType, identificationNumber, cardholderEmail } =
              formRef.current.getCardFormData() as {
                token: string; paymentMethodId: string; issuerId: string;
                identificationType: string; identificationNumber: string; cardholderEmail: string;
              };
            if (!token) throw new Error("Token de cartão não gerado. Verifique os dados e tente novamente.");
            await subscription.checkout(plan, token, paymentMethodId, issuerId, identificationType, identificationNumber, cardholderEmail);
            if (!active) return;
            setSuccess(true);
            await refreshUser();
            setTimeout(() => { onSuccess?.(plan); onClose(); }, 2500);
          } catch (e: unknown) {
            if (!active) return;
            const msg = e instanceof Error ? e.message : "Erro ao processar pagamento. Tente novamente.";
            setError(msg);
          } finally {
            if (active) setSubmitting(false);
          }
        },
        onError: (errors: Array<{ message: string }>) => {
          if (!active) return;
          const msgs = errors?.map((e) => e.message).filter(Boolean).join(". ");
          if (msgs) setError(msgs);
        },
      },
    });

    formRef.current = cardForm;

    return () => {
      active = false;
      try { cardForm.unmount(); } catch { /* ignore */ }
      formRef.current = null;
    };
  }, [sdkReady, plan]);

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-hud-surface p-6 shadow-elevated space-y-4 overflow-y-auto max-h-[calc(100vh-2rem)]">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CreditCard className="size-5 text-primary" />
            <h2 className="font-semibold text-foreground">
              Assinar {info.label}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Fechar"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Plan summary badge */}
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

        {/* Success state */}
        {success ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <CheckCircle2 className="size-12 text-primary" />
            <p className="text-sm font-semibold text-foreground text-center">
              Assinatura ativada com sucesso!
            </p>
            <p className="text-xs text-muted-foreground text-center">
              Seu plano {info.label} já está disponível. Redirecionando…
            </p>
          </div>
        ) : !sdkReady ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <form id="mp-checkout-form" className="space-y-3.5">

            {/* PCI-secured: MP renders iframes into these div containers */}
            <FieldWrap label="Número do cartão">
              <div id="mp-card-number" className={iframeContainerClass} />
            </FieldWrap>

            <div className="grid grid-cols-2 gap-3">
              <FieldWrap label="Validade">
                <div id="mp-expiration-date" className={iframeContainerClass} />
              </FieldWrap>
              <FieldWrap label="CVV">
                <div id="mp-security-code" className={iframeContainerClass} />
              </FieldWrap>
            </div>

            {/* Non-PCI: real input elements */}
            <FieldWrap label="Nome no cartão">
              <input
                id="mp-cardholder-name"
                placeholder="Nome impresso no cartão"
                className={inputClass}
              />
            </FieldWrap>

            <div className="grid grid-cols-5 gap-3">
              <div className="col-span-2">
                <FieldWrap label="Documento">
                  <select id="mp-identification-type" className={inputClass} />
                </FieldWrap>
              </div>
              <div className="col-span-3">
                <FieldWrap label="Número">
                  <input
                    id="mp-identification-number"
                    placeholder="000.000.000-00"
                    className={inputClass}
                  />
                </FieldWrap>
              </div>
            </div>

            <FieldWrap label="E-mail do pagador">
              <input
                id="mp-cardholder-email"
                type="email"
                placeholder="email@exemplo.com"
                className={inputClass}
              />
            </FieldWrap>

            {/* Hidden selects that MP needs in the DOM */}
            <select id="mp-issuer"        className="hidden" />
            <select id="mp-installments"  className="hidden" />

            {error && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5">
                <AlertCircle className="size-4 shrink-0 text-destructive mt-0.5" />
                <p className="text-xs text-destructive">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:opacity-90 disabled:opacity-50"
            >
              {submitting && <Loader2 className="size-4 animate-spin" />}
              {submitting ? "Processando…" : `Assinar ${info.label} · ${info.price}`}
            </button>

            <p className="text-center font-mono text-[9px] text-muted-foreground">
              Pagamento seguro via Mercado Pago · Cancele quando quiser
            </p>
          </form>
        )}
      </div>
    </div>,
    document.body
  );
}
