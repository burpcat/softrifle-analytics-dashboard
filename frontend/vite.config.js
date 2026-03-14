import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// All backend routes must use the /api prefix to be proxied correctly.
// Non-prefixed routes (e.g. /ws, /) will not reach FastAPI in development —
// they will hit the Vite dev server instead, silently.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});