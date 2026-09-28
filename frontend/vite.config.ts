import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo, /api se reenvia al backend FastAPI: el navegador ve un solo
// origen y no hace falta CORS. Cambiar el destino con SAAD_API_URL.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.SAAD_API_URL ?? "http://127.0.0.1:8000",
    },
  },
});
