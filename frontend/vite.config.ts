import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/auth":        { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/analyze":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/study":       { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/coach":       { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/student":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/tournaments": { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/tournament/": { target: "http://127.0.0.1:5000", changeOrigin: true },  // barra final: proxia a API /tournament/results (singular) sem capturar a rota SPA /tournaments/:id
      "/history":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/replay/":     { target: "http://127.0.0.1:5000", changeOrigin: true },  // barra final: senão o prefixo /replay captura a rota SPA /replayer (404 em load direto/refresh)
      "/metrics":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/subscription": { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/admin":       { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/health":      { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/player":      { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/support":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/academy":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/profile":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/preflop-ranges": { target: "http://127.0.0.1:5000", changeOrigin: true },
    },
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
