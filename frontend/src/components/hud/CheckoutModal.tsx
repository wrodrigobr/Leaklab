import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { createPortal } from "react-dom";
import { loadStripe, type Stripe, type StripeElements } from "@stripe/stripe-js";
import { X, Loader2, CreditCard, CheckCircle2, AlertCircle, Zap } from "lucide-react";
import { subscription } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { trackPurchase } from "@/lib/analytics";
import { cn } from "@/lib/utils";

const STRIPE_KEY = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string;

// Espelha leaklab.stripe_gateway: mensal R$99 / anual R$990 (2 meses grátis).
/**
 * ── O preço vem da API, e a economia é DERIVADA (28/08) ────────────────────────────────────
 *
 * Até hoje este arquivo tinha o preço em `checkout.preco.mensal` ("R$ 99/mês"), o do anual, o
 * texto "2 meses grátis · R$ 82,50/mês" e um `-17%` cravado no JSX. Somados ao `PLAN_AMOUNTS` do
 * backend, ao `"R$ 99"` da landing e ao preço real do Stripe, eram **cinco fontes para o mesmo
 * fato** -- no campo onde divergir custa mais caro: o site anuncia um valor e o cartão é debitado
 * de outro.
 *
 * Agora `/subscription/plans` (público, sem login) entrega `price`, `monthly_equiv`,
 * `full_price`, `discount_pct` e `months_free`, todos derivados de uma constante só, que por sua
 * vez é conferida contra o Stripe por `scripts/conferir_precos_no_stripe.py` no portão de deploy.
 *
 * O i18n mantém os RÓTULOS ("Economize {{valor}} por ano") e perdeu os NÚMEROS.
 */
const BILLING = {
  monthly: { labelKey: "checkout.ciclo.mensal" },
  annual:  { labelKey: "checkout.ciclo.anual" },
} as const;

interface PlanoDaApi {
  price?: number;                 // centavos, ciclo mensal
  billing?: {
    monthly?: { price: number };
    annual?: {
      price: number; monthly_equiv: number; full_price: number;
      discount_pct: number; months_free: number;
    };
  };
}

/** Centavos -> "R$ 39,90". Uma função só: dois formatadores divergiriam no centavo. */
function brl(centavos: number | undefined | null): string {
  if (centavos == null) return "";
  return (centavos / 100).toLocaleString("pt-BR", {
    style: "currency", currency: "BRL", minimumFractionDigits: 2,
  });
}
type BillingCycle = keyof typeof BILLING;

const PLAN_INFO = {
  pro: {
    label: "Pro",
    colorClass: "text-primary border-primary/30 bg-primary/5",
    featuresKey: "checkout.features",
  },
} as const;

interface Props {
  plan: "pro";
  onClose: () => void;
  onSuccess?: (newPlan: string) => void;
}

export function CheckoutModal({ plan, onClose, onSuccess }: Props) {
  const { t } = useTranslation("dashboard");
  const { refreshUser } = useAuth();
  const info = PLAN_INFO[plan];


  const [billing,        setBilling]        = useState<BillingCycle>("annual");
  // Os preços vêm do backend, que os deriva de UMA constante conferida contra o Stripe. Enquanto
  // não chegam, os valores ficam VAZIOS em vez de mostrar um número de reserva: preço provisório
  // na tela é a forma mais cara possível de "quase certo".
  const [planos, setPlanos] = useState<PlanoDaApi | null>(null);
  const [clientSecret,   setClientSecret]   = useState<string | null>(null);
  const [subscriptionId, setSubscriptionId] = useState<string | null>(null);
  const [stripeInstance, setStripeInstance] = useState<Stripe | null>(null);
  const [formMounted,    setFormMounted]     = useState(false);
  const [submitting,     setSubmitting]      = useState(false);
  const [error,          setError]           = useState<string | null>(null);
  const [success,        setSuccess]         = useState(false);

  const elementsRef = useRef<StripeElements | null>(null);

  // Phase 1: load Stripe.js + create subscription intent in parallel.
  // Re-runs quando o ciclo (mensal/anual) muda → novo PaymentIntent com o valor certo.
  // Busca os planos ao montar. Falha em silencio de proposito: sem preco a tela mostra o rotulo
  // sem numero, que e honesto -- inventar um valor de reserva seria anunciar o que talvez nao se
  // cobre, que e exatamente o defeito que este dia inteiro perseguiu.
  useEffect(() => {
    let vivo = true;
    subscription.plans()
      .then((r) => {
        if (!vivo) return;
        setPlanos((r.plans || []).find((p) => p.id === "pro") ?? null);
      })
      .catch(() => { /* sem preco na tela, e nao um preco errado */ });
    return () => { vivo = false; };
  }, []);

  const mensal = planos?.billing?.monthly;
  const anual  = planos?.billing?.annual;

  useEffect(() => {
    let active = true;
    setClientSecret(null);
    setSubscriptionId(null);
    setFormMounted(false);
    setError(null);
    (async () => {
      try {
        const [intentResult, stripe] = await Promise.all([
          subscription.checkout(plan, billing),
          loadStripe(STRIPE_KEY),
        ]);
        if (!active) return;
        if (!stripe) throw new Error(t("checkout.erroSdk"));
        setStripeInstance(stripe);
        setClientSecret(intentResult.client_secret);
        setSubscriptionId(intentResult.subscription_id);
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Erro ao iniciar pagamento.");
      }
    })();
    return () => { active = false; };
  }, [plan, billing]);

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

    // terms: never — o aviso de cobrança recorrente é NOSSO (i18n, 3 idiomas), no lugar do
    // texto genérico do Stripe que o dono achou ruim (30/08).
    const paymentEl = elementsRef.current.create("payment", { terms: { card: "never" } });
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
        await subscription.activate(plan, paymentIntent.id, subscriptionId, billing);
        // Conversão de compra (upgrade Pro). amount vem em centavos da moeda.
        trackPurchase(
          plan,
          typeof paymentIntent.amount === "number" ? paymentIntent.amount / 100 : undefined,
          (paymentIntent.currency ?? "brl").toUpperCase(),
        );
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
      <div className="w-full max-w-md md:max-w-3xl rounded-xl border border-border bg-hud-surface p-6 shadow-elevated space-y-4 overflow-y-auto max-h-[calc(100vh-2rem)]">

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

        {/* 30/08, o dono: "popup estreito e confuso". No desktop vira 2 colunas — plano à
            esquerda, pagamento à direita — e o modal alarga. No celular empilha como antes. */}
        <div className="grid gap-4 md:grid-cols-5 md:items-start">
        <div className="space-y-4 md:col-span-2">
        {/* Toggle de ciclo (mensal / anual) — só faz sentido antes do sucesso */}
        {!success && (
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border">
            {(Object.keys(BILLING) as BillingCycle[]).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setBilling(c)}
                className={cn(
                  "relative flex flex-col items-center gap-0.5 px-3 py-2.5 transition-colors",
                  billing === c ? "bg-primary/10" : "bg-hud-surface hover:bg-primary/5"
                )}
              >
                <span className={cn("font-mono text-[11px] font-bold uppercase tracking-wider",
                  billing === c ? "text-primary" : "text-muted-foreground")}>{t(BILLING[c].labelKey)}</span>
                <span className={cn("font-mono text-xs font-bold",
                  billing === c ? "text-foreground" : "text-muted-foreground")}>
                  {c === "annual"
                    ? t("checkout.porMes", { valor: brl(anual?.monthly_equiv) })
                    : t("checkout.porMes", { valor: brl(mensal?.price) })}
                </span>
                {/* A ECONOMIA, que era o pedido: em reais e em meses, os dois derivados. Em reais
                    porque "25%" não diz quanto fica no bolso, e em meses porque é a unidade em
                    que o jogador pensa a assinatura. */}
                {c === "annual" && anual && (
                  <span className="font-mono text-[9px] text-primary">
                    {t("checkout.economia", { valor: brl(anual.full_price - anual.price) })}
                    {" · "}
                    {t("checkout.mesesGratis", { n: anual.months_free })}
                  </span>
                )}
                {/* O desconto sai da conta, não de um literal. Estava `-17%` cravado aqui, e
                    com os valores de 28/08 (R$39,90 x 12 = R$478,80 contra R$358,80) o número
                    certo é 25%. Um literal desses envelhece calado no dia em que o preço muda. */}
                {c === "annual" && anual?.discount_pct != null && (
                  <span className="absolute -top-px right-1 rounded-b bg-primary px-1 py-0.5 font-mono text-[8px] font-bold uppercase text-primary-foreground">
                    -{anual.discount_pct}%
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Plan badge */}
        <div className={cn("rounded-lg border px-4 py-3 space-y-1.5", info.colorClass)}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm font-bold uppercase tracking-wider flex items-center gap-1.5">
              {plan === "pro" && <Zap className="size-3.5" />}
              {info.label} · {t(BILLING[billing].labelKey)}
            </span>
            <span className="font-mono text-sm font-bold">
              {billing === "annual"
                ? t("checkout.porAno", { valor: brl(anual?.price) })
                : t("checkout.porMes", { valor: brl(mensal?.price) })}
            </span>
          </div>
          <ul className="space-y-0.5">
            {(t(info.featuresKey, { returnObjects: true }) as string[]).map((f) => (
              <li key={f} className="font-mono text-[10px] opacity-75">• {f}</li>
            ))}
          </ul>
        </div>
        </div>

        <div className="md:col-span-3">
        {/* Success */}
        {success ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <CheckCircle2 className="size-12 text-primary" />
            <p className="text-sm font-semibold text-foreground text-center">{t("checkout.sucesso")}</p>
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
                  {submitting ? t("checkout.processando") : t("checkout.assinar", {
                    plano: info.label,
                    preco: billing === "annual"
                      ? t("checkout.porAno", { valor: brl(anual?.price) })
                      : t("checkout.porMes", { valor: brl(mensal?.price) }),
                  })}
                </button>
                <p className="text-[10px] leading-snug text-muted-foreground">
                  {t("checkout.recorrencia", {
                    preco: billing === "annual"
                      ? t("checkout.porAno", { valor: brl(anual?.price) })
                      : t("checkout.porMes", { valor: brl(mensal?.price) }),
                  })}
                </p>
                <p className="text-center font-mono text-[9px] text-muted-foreground">
                  {t("checkout.seguro")}
                </p>
              </>
            )}
          </form>
        )}
        </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
