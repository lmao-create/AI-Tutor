import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_TARGET = process.env.CODETUTOR_API_TARGET || "http://127.0.0.1:8123";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // All API calls go through the Vite dev server to the backend,
      // which also keeps Server-Sent Events streaming intact.
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
});
