/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Everything is bundled locally; the app makes no request beyond its own origin (spec 8.5).
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", proxy: { "/api": "http://127.0.0.1:8765", "/catalogue": "http://127.0.0.1:8765" } },
  build: { outDir: "dist", sourcemap: false, assetsInlineLimit: 0 },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"], setupFiles: ["src/test-setup.ts"] },
});
