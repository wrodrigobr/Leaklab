// Fundação de rastreamento de conversão (Google Analytics 4 + Google Ads), para medir aquisição
// paga (YouTube/Google Ads). ENV-GATED: sem VITE_GA_MEASUREMENT_ID nem VITE_GOOGLE_ADS_ID, tudo
// vira no-op (nada carrega em dev, nada rastreia sem configurar). O gtag cuida sozinho da
// atribuição por gclid (cookie _gcl) quando o clique vem de um anúncio.
//
// Vars (defina em produção):
//   VITE_GA_MEASUREMENT_ID   G-XXXXXXX      (GA4)
//   VITE_GOOGLE_ADS_ID       AW-XXXXXXXXX   (Google Ads)
//   VITE_ADS_SIGNUP_LABEL    rótulo da conversão de cadastro   (o AW-.../<label>)
//   VITE_ADS_PURCHASE_LABEL  rótulo da conversão de compra
//
// LGPD: rodar isto para tráfego BR/EU exige um banner de consentimento (Consent Mode). Ver o
// follow-up de consentimento antes de ligar campanhas.
import { getAcquisition } from "./acquisition";

const GA_ID = (import.meta.env.VITE_GA_MEASUREMENT_ID as string | undefined)?.trim() || null;
const ADS_ID = (import.meta.env.VITE_GOOGLE_ADS_ID as string | undefined)?.trim() || null;
const ADS_SIGNUP_LABEL = (import.meta.env.VITE_ADS_SIGNUP_LABEL as string | undefined)?.trim() || null;
const ADS_PURCHASE_LABEL = (import.meta.env.VITE_ADS_PURCHASE_LABEL as string | undefined)?.trim() || null;

const ENABLED = !!(GA_ID || ADS_ID);
let started = false;

const CONSENT_KEY = "gl_consent";   // "granted" | "denied"

type GtagArgs = [string, ...unknown[]];
declare global {
  interface Window { dataLayer?: unknown[]; gtag?: (...args: GtagArgs) => void; }
}

function gtag(...args: GtagArgs) {
  if (!window.dataLayer) return;
  window.dataLayer.push(args);
}

/** true se há IDs configurados (o banner de cookies só aparece se o tracking existe). */
export function analyticsEnabled(): boolean {
  return ENABLED;
}

/** Decisão de consentimento já registrada, ou null (ainda não decidiu → mostrar banner). */
export function getStoredConsent(): "granted" | "denied" | null {
  try {
    const v = localStorage.getItem(CONSENT_KEY);
    return v === "granted" || v === "denied" ? v : null;
  } catch {
    return null;
  }
}

const CONSENT_SIGNALS = ["ad_storage", "analytics_storage", "ad_user_data", "ad_personalization"] as const;

function consentState(granted: boolean): Record<string, string> {
  const v = granted ? "granted" : "denied";
  return Object.fromEntries(CONSENT_SIGNALS.map((k) => [k, v]));
}

/** Grava a decisão e AVISA o gtag (Consent Mode v2). Chamado pelo banner de cookies. */
export function setConsent(granted: boolean): void {
  try { localStorage.setItem(CONSENT_KEY, granted ? "granted" : "denied"); } catch { /* ignore */ }
  if (ENABLED && window.dataLayer) {
    gtag("consent", "update", consentState(granted));
  }
}

/** Carrega o gtag.js uma vez e configura GA4 + Ads, com Consent Mode v2 (default negado até o
 *  aceite). No-op se nada configurado. */
export function initAnalytics(): void {
  if (started || !ENABLED || typeof window === "undefined") return;
  started = true;

  window.dataLayer = window.dataLayer || [];
  window.gtag = (...args: GtagArgs) => window.dataLayer!.push(args);

  // Consent Mode: default = a decisão salva, ou NEGADO até o usuário aceitar no banner. Com
  // consentimento negado o gtag não grava cookies (LGPD), só envia pings sem identificador.
  const granted = getStoredConsent() === "granted";
  gtag("consent", "default", { ...consentState(granted), wait_for_update: 500 });

  const primary = GA_ID || ADS_ID!;
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${primary}`;
  document.head.appendChild(s);

  gtag("js", new Date());
  if (GA_ID) gtag("config", GA_ID);
  if (ADS_ID) gtag("config", ADS_ID);
}

function withSource(params: Record<string, unknown> = {}): Record<string, unknown> {
  const src = getAcquisition();
  return src ? { ...params, acquisition_source: src } : params;
}

/** Conversão de CADASTRO. Dispara o `sign_up` do GA4 + a conversão do Google Ads (se rotulada). */
export function trackSignup(method: "email" | string = "email"): void {
  if (!ENABLED) return;
  gtag("event", "sign_up", withSource({ method }));
  if (ADS_ID && ADS_SIGNUP_LABEL) {
    gtag("event", "conversion", { send_to: `${ADS_ID}/${ADS_SIGNUP_LABEL}` });
  }
}

/** Conversão de COMPRA (upgrade Pro). `value` na moeda real (não em centavos). */
export function trackPurchase(plan: string, value?: number, currency = "BRL"): void {
  if (!ENABLED) return;
  gtag("event", "purchase", withSource({
    value,
    currency,
    items: [{ item_name: plan }],
  }));
  if (ADS_ID && ADS_PURCHASE_LABEL) {
    gtag("event", "conversion", { send_to: `${ADS_ID}/${ADS_PURCHASE_LABEL}`, value, currency });
  }
}

/** Evento genérico (ex.: início de análise, clique em CTA). No-op se desligado. */
export function trackEvent(name: string, params?: Record<string, unknown>): void {
  if (!ENABLED) return;
  gtag("event", name, withSource(params));
}
