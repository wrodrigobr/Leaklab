import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
import type { IncomingMessage } from "http";

const API = "http://127.0.0.1:5000";

/**
 * Um BYPASS só, em vez de vinte exceções (auditoria NLU-11, 15/09).
 *
 * O dev server tem dois papéis no mesmo host: servir a SPA e proxiar a API. Vários prefixos são
 * as duas coisas ao mesmo tempo (`/study`, `/admin`, `/profile`, `/subscription`, `/academy`,
 * `/tournaments`, `/coaches`, `/h`), e a lista de chaves não consegue separá-los: medido com o
 * dev server no ar e o backend desligado, dar F5 em `/tournaments/5`, `/academy/3bet`, `/study`,
 * `/subscription`, `/profile` ou `/admin` devolvia erro do BACKEND em vez da tela, e
 * `/coaches?limit=1`, `/coaches/62` e `/shared-hands/feed` recebiam 404 do próprio vite porque
 * não tinham chave.
 *
 * Quem separa não é o caminho, é o `Accept`: navegação de página pede `text/html`, chamada de
 * `lib/api.ts` (via `fetch`) nunca pede. Então toda chave usa a MESMA regra, e os prefixos que
 * colidem com tela entram como chaves normais.
 *
 * Nada disso chega a produção, onde o Cloudflare Pages serve a SPA e a API mora em outro
 * domínio. O que isto evita é alguém "consertar" o produto por um sintoma do proxy.
 */
const paraASpaQuandoEPagina = (req: IncomingMessage) =>
  (req.headers.accept ?? "").includes("text/html") ? "/index.html" : undefined;

/**
 * Prefixos de API que o front chama. `/h/` e `/tournament/` levam barra por outro motivo, que o
 * bypass não cobre: sem ela `/h` capturaria um asset `/hero.png` (que pede `Accept: image/...`)
 * e `/tournament` capturaria a tela `/tournaments`.
 *
 * FORA de propósito, e não por esquecimento: `/debug`, `/gto` e `/telegram`, que só admin e bot
 * chamam por curl, e que o front não toca.
 */
const PREFIXOS_DE_API = [
  "/auth",
  "/analyze",
  // A rota do upload ASSINCRONO (14/09). Sem esta linha o dev server trata `/uploads` como rota
  // da SPA e devolve o index.html em vez de chamar a API: o arquivo "subiria" sem nunca chegar
  // ao backend, e pareceria defeito do produto.
  "/uploads",
  "/study",
  "/coach/",        // barra final: "/coach" exato não é rota de API, só "/coach/..."
  "/coaches",       // diretório e perfil público de coach; é TAMBÉM tela, e o bypass separa
  "/student",
  "/tournaments",
  "/tournament/",   // barra final: a API é `/tournament/results` (singular)
  "/history",
  "/replay/",       // barra final: "/replay" exato não é rota de API
  "/metrics",
  "/subscription",
  "/admin",
  "/health",
  "/player",
  "/support",
  "/sample",        // decisão de exemplo (pública)
  "/academy",
  "/profile",
  "/preflop-ranges",
  "/shared-hands",  // feed de mãos compartilhadas (tela /maos)
  "/h/",            // mão compartilhada por token; é também a tela `/h/:token`
];

const proxyDaApi = Object.fromEntries(
  PREFIXOS_DE_API.map((prefixo) => [
    prefixo,
    { target: API, changeOrigin: true, bypass: paraASpaQuandoEPagina },
  ]),
);

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: proxyDaApi,
  },
  build: {
    rollupOptions: {
      input: {
        main:     path.resolve(__dirname, "index.html"),
        replayer: path.resolve(__dirname, "leaklab-replayer-v3.html"),
      },
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
}));
