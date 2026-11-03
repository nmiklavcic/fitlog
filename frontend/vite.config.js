import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the Vite server proxies API and media requests to Django, so the
// browser sees a single origin (like production behind Nginx) and cookies just work.
// changeOrigin: false keeps the browser's Host header (like Nginx's
// `proxy_set_header Host $host`), so Django's CSRF origin check sees the same origin.
const backend = { target: "http://127.0.0.1:8000", changeOrigin: false };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/media": backend,
      "/admin": backend,
      "/static": backend,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
