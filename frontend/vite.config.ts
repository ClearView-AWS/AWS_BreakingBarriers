import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // API_URL lets a second checkout run its API on another port.
      "/api": process.env.API_URL ?? "http://127.0.0.1:8000",
    },
  },
});
