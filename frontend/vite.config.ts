import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    exclude: ["e2e/**", "**/node_modules/**", "**/dist/**", "**/.{idea,git,cache,output,temp}/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/features/**/*.ts", "src/features/**/*.tsx"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 65,
        statements: 80,
      },
    },
  },
  server: {
    port: 4173,
    proxy: {
      "/api": "http://127.0.0.1:8008",
      "/health": "http://127.0.0.1:8008",
    },
  },
});
