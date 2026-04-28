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
      "/history":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/replay":      { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/metrics":     { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/subscription": { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/admin":       { target: "http://127.0.0.1:5000", changeOrigin: true },
      "/health":      { target: "http://127.0.0.1:5000", changeOrigin: true },
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
