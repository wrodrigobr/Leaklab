import { createRoot } from "react-dom/client";
import * as Sentry from "@sentry/react";
import App from "./App.tsx";
import { captureAcquisition } from "./lib/acquisition";
import "./index.css";
import "./i18n";

// Captura ?utm_source na 1ª carga (antes do router) → guarda na sessão p/ enviar no cadastro.
captureAcquisition();

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.05,
    environment: import.meta.env.MODE,
    ignoreErrors: [
      "ResizeObserver loop limit exceeded",
      "Non-Error promise rejection captured",
    ],
  });
}

createRoot(document.getElementById("root")!).render(
  <Sentry.ErrorBoundary
    fallback={
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-center space-y-3">
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Algo deu errado
          </p>
          <button
            onClick={() => window.location.reload()}
            className="text-sm text-primary underline underline-offset-2"
          >
            Recarregar
          </button>
        </div>
      </div>
    }
  >
    <App />
  </Sentry.ErrorBoundary>
);
