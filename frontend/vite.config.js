import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the Vite server proxies API and media requests to Django, so the
// browser sees a single origin (like production behind Nginx) and cookies just work.
const backend = "http://127.0.0.1:8000";

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
